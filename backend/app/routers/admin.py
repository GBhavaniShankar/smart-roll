from fastapi import (
    APIRouter, Depends, HTTPException, status, 
    UploadFile, File, Query, Response, Form
)
from supabase import Client
from typing import List, Optional, Literal
from uuid import UUID
import datetime
import traceback

from app.database import get_db
from app.dependencies import AdminUser
from app.models.user import UserInDB, TeacherCreate, TeacherProfile
from app.models.student import StudentCreate, StudentProfile
from app.models.course import RegistrationPeriodCreate, RegistrationPeriodInDB
from app.services.auth_service import AuthService
from app.utils.image_processing import upload_image_to_supabase
from app.utils.face_embedding import extract_face_embedding

router = APIRouter(
    prefix="/api/admin",
    tags=["Admin"],
    dependencies=[AdminUser] 
)

# --- User Management ---

@router.get("/users", response_model=List[UserInDB])
async def list_all_users(
    role: Optional[str] = Query(None, enum=["student", "teacher", "ta", "admin"]),
    page: int = Query(1, gt=0),
    limit: int = Query(20, gt=0, le=100),
    db: Client = Depends(get_db)
):
    try:
        query = db.table("users").select("*")
        if role:
            query = query.eq("role", role)
        offset = (page - 1) * limit
        query = query.range(offset, offset + limit - 1)
        response = query.execute()
        return response.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/students", response_model=StudentProfile, status_code=status.HTTP_201_CREATED)
async def add_new_student(
    profile_picture: UploadFile = File(...),
    full_name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    roll_number: str = Form(...),
    stream: str = Form(...),
    cgpa: Optional[float] = Form(None),
    db: Client = Depends(get_db)
):
    auth_service = AuthService(db)
    new_user = None
    try:
        student_data = StudentCreate(
            full_name=full_name, email=email, password=password,
            roll_number=roll_number, stream=stream,
            current_semester=1, # Default to 1
            cgpa=cgpa
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=f"Invalid form data: {e}")

    if db.table("users").select("user_id").eq("email", student_data.email).execute().data:
        raise HTTPException(status_code=400, detail="User with this email already exists.")
    if db.table("students").select("student_id").eq("roll_number", student_data.roll_number).execute().data:
        raise HTTPException(status_code=400, detail="User with this roll number already exists.")

    try:
        new_user = await auth_service.create_supabase_user(
            email=student_data.email,
            password=student_data.password,
            full_name=student_data.full_name,
            role="student"
        )
        image_bytes = await profile_picture.read()
        profile_pic_url = await upload_image_to_supabase(
            db, image_bytes, "profile_pictures", f"{new_user.id}.jpg"
        )
        face_embed = await extract_face_embedding(image_bytes)
        student_profile_data = {
            "student_id": new_user.id, "roll_number": student_data.roll_number,
            "stream": student_data.stream, "current_semester": 1,
            "cgpa": student_data.cgpa, "profile_picture_url": profile_pic_url,
            "face_embedding": face_embed
        }
        student_resp = db.table("students").insert(student_profile_data).execute()
        response_data = {
            **student_resp.data[0], "user_id": new_user.id,
            "email": new_user.email, "full_name": student_data.full_name,
            "role": "student", "created_at": new_user.created_at.isoformat()
        }
        return StudentProfile(**response_data)
    except Exception as e:
        traceback.print_exc()
        if new_user:
            admin_auth = db.auth.admin
            admin_auth.delete_user(new_user.id)
            print(f"Cleanup: Rolled back (deleted) auth user {new_user.id}")
        raise HTTPException(status_code=500, detail=f"Failed to create student: {str(e)}")

@router.post("/teachers", response_model=TeacherProfile, status_code=status.HTTP_201_CREATED)
async def add_new_teacher(
    teacher_data: TeacherCreate,
    db: Client = Depends(get_db)
):
    auth_service = AuthService(db)
    new_user = None
    try:
        new_user = await auth_service.create_supabase_user(
            email=teacher_data.email, password=teacher_data.password,
            full_name=teacher_data.full_name, role="teacher"
        )
        teacher_profile_data = {
            "teacher_id": new_user.id, "employee_id": teacher_data.employee_id,
            "department": teacher_data.department, "specialization": teacher_data.specialization,
        }
        teacher_resp = db.table("teachers").insert(teacher_profile_data).execute()
        response_data = {
            **teacher_resp.data[0], "user_id": new_user.id,
            "email": new_user.email, "full_name": teacher_data.full_name,
            "role": "teacher", "created_at": new_user.created_at.isoformat()
        }
        return TeacherProfile(**response_data)
    except Exception as e:
        if new_user:
            admin_auth = db.auth.admin
            admin_auth.delete_user(new_user.id)
        raise HTTPException(status_code=500, detail=f"Failed to create teacher: {str(e)}")

@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_user(
    user_id: UUID,
    db: Client = Depends(get_db)
):
    try:
        admin_auth = db.auth.admin
        admin_auth.delete_user(str(user_id))
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        if "User not found" in str(e):
            raise HTTPException(status_code=404, detail="User not found.")
        raise HTTPException(status_code=500, detail=f"Failed to delete user: {str(e)}")

@router.post("/promote-to-ta/{student_id}", status_code=status.HTTP_200_OK)
async def promote_to_ta(
    student_id: UUID,
    current_user: UserInDB = AdminUser,
    db: Client = Depends(get_db)
):
    try:
        user_update_response = (
            db.table("users").update({"role": "ta"})
            .eq("user_id", str(student_id)).eq("role", "student").execute()
        )
        if not user_update_response.data:
            raise HTTPException(status_code=404, detail="User not found or is not a student.")
        ta_insert_data = {"ta_id": str(student_id), "student_id": str(student_id)}
        db.table("teaching_assistants").upsert(ta_insert_data, on_conflict="ta_id").execute()
        db.auth.admin.update_user_by_id(
            str(student_id), {"user_metadata": {"role": "ta"}}
        )
        return {"message": f"User {student_id} successfully promoted to TA."}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")

# --- Semester Management ---

@router.post("/registration/start")
async def start_course_registration(
    period: RegistrationPeriodCreate,
    current_user: UserInDB = AdminUser,
    db: Client = Depends(get_db)
):
    """
    Creates or updates a semester record to open registration.
    """
    try:
        # 1. Deactivate all other registration periods
        # We do this by setting 'is_active' to false
        # (This assumes 'is_active' is our flag for registration)
        db.table("semesters").update(
            {"is_active": False}
        ).eq("is_active", True).execute()
        
        # 2. Create the new active semester/registration period
        new_period_data = {
            "academic_year": period.academic_year,
            "season": period.season,
            "registration_start_date": period.registration_start_date.isoformat(),
            "registration_end_date": period.registration_end_date.isoformat(),
            "start_date": period.start_date, # Optional, can be null
            "end_date": period.end_date,     # Optional, can be null
            "created_by": str(current_user.user_id),
            "is_active": True
        }
        
        # Upsert in case this Year/Season already exists
        response = db.table("semesters").upsert(
            new_period_data, 
            on_conflict="academic_year, season"
        ).execute()
        
        if not response.data:
            raise HTTPException(status_code=500, detail="Failed to start registration.")
        
        db_data = response.data[0]
        
        # Manually build response to handle datetimes
        response_dict = {
            "semester_id": db_data["semester_id"],
            "academic_year": db_data["academic_year"],
            "season": db_data["season"],
            "registration_start_date": db_data["registration_start_date"],
            "registration_end_date": db_data["registration_end_date"],
            "start_date": db_data["start_date"],
            "end_date": db_data["end_date"],
            "is_active": db_data["is_active"],
            "created_by": db_data["created_by"]
        }
        
        return response_dict
            
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")

@router.post("/registration/stop", status_code=status.HTTP_200_OK)
async def stop_course_registration(db: Client = Depends(get_db)):
    """
    This stops ALL active registration periods by setting is_active=false.
    """
    try:
        response = db.table("semesters").update(
            {"is_active": False}
        ).eq("is_active", True).execute()
        
        return {"message": f"Deactivated {len(response.data)} registration period(s)."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/semester/advance", status_code=status.HTTP_200_OK)
async def advance_all_student_semesters(
    current_user: UserInDB = AdminUser,
    db: Client = Depends(get_db)
):
    try:
        db.rpc('increment_all_student_semesters').execute()
        return {"message": "Successfully advanced semester for all students."}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")