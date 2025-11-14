from fastapi import APIRouter, Depends, HTTPException, status
from supabase import Client
from typing import List, Optional
from uuid import UUID
import traceback
from postgrest import APIError 
import datetime

from app.database import get_db
from app.dependencies import TeacherUser
from app.models.user import UserInDB
from app.models.course import (
    CourseCreate, CourseInDB,
    CourseOfferingCreate,
    PrerequisiteCreate, PrerequisiteInDB,
    AssignTACreate, GradeCreate, SimpleStudent
)
from app.models.attendance import TeacherAttendanceStat

GRADE_TO_POINT_MAP = {
    "S": 10.0, "A": 9.0, "B": 8.0, "C+": 7.0,
    "D": 6.0, "E": 4.0, "F": 0.0, "U": 0.0,
}

router = APIRouter(
    prefix="/api/teacher",
    tags=["Teacher"],
    dependencies=[TeacherUser]
)

# --- 1. Master Course Catalog Management ---
@router.post("/courses/catalog", response_model=CourseInDB, status_code=status.HTTP_201_CREATED)
async def create_new_catalog_course(
    course: CourseCreate, # <-- Now contains logical_semester
    current_user: UserInDB = TeacherUser,
    db: Client = Depends(get_db)
):
    """
    Creates a new *abstract course* in the main course catalog.
    """
    try:
        # course.logical_semester is now included
        course_data = course.model_dump()
        response = db.table("courses").insert(course_data).execute()
        
        if not response.data:
            raise HTTPException(status_code=500, detail="Failed to create course in catalog.")
            
        return response.data[0]
        
    except Exception as e:
        if 'duplicate key value violates unique constraint "courses_course_code_key"' in str(e):
            raise HTTPException(status_code=400, detail=f"Course code '{course.course_code}' already exists.")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/courses/catalog", response_model=List[CourseInDB])
# ... (this function is unchanged) ...
async def get_all_courses_from_catalog(db: Client = Depends(get_db)):
    try:
        response = db.table("courses").select("*").order("course_code").execute()
        return response.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/courses/{course_id}/prerequisites", response_model=PrerequisiteInDB)
# ... (this function is unchanged) ...
async def add_course_prerequisite(course_id: UUID, prereq: PrerequisiteCreate, current_user: UserInDB = TeacherUser, db: Client = Depends(get_db)):
    try:
        prereq_data = prereq.model_dump()
        prereq_data["course_id"] = str(course_id)
        prereq_data["prerequisite_course_id"] = str(prereq_data["prerequisite_course_id"])
        response = db.table("course_prerequisites").insert(prereq_data).execute()
        if not response.data:
            raise HTTPException(status_code=500, detail="Failed to add prerequisite.")
        return response.data[0]
    except Exception as e:
        if "duplicate key" in str(e):
            raise HTTPException(status_code=400, detail="This prerequisite link already exists.")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")

# --- 2. Course Offering Management ---
@router.post("/courses/offer", status_code=status.HTTP_201_CREATED)
async def offer_new_course(
    offering: CourseOfferingCreate, # <-- Model now ONLY has course_id
    current_user: UserInDB = TeacherUser,
    db: Client = Depends(get_db)
):
    """
    Creates a new *offering* of an existing course for the
    CURRENTLY ACTIVE registration period.
    """
    try:
        # 1. Find the *one* active registration period
        reg_resp = db.table("semesters").select(
            "semester_id" # We just need the ID to link
        ).eq("is_active", True).limit(1).single().execute()
        
        active_semester_id = reg_resp.data['semester_id']
        
        # 2. Build the new offering data
        offering_data = {
            "course_id": str(offering.course_id),
            "teacher_id": str(current_user.user_id),
            "semester_id": active_semester_id # <-- LINK to the active semester
            # logical_semester is no longer needed here
        }

        # 3. Insert the new offering
        response = db.table("course_offerings").insert(offering_data).execute()
        if not response.data:
            raise HTTPException(status_code=500, detail="Failed to create course offering.")
        return response.data[0]
        
    except Exception as e:
        if "duplicate key" in str(e):
            raise HTTPException(status_code=400, detail="This course has already been offered for this semester.")
        if "PGRST116" in str(e):
             raise HTTPException(status_code=400, detail="No active registration period found. An Admin must start a registration period first.")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/offerings", response_model=List[dict])
# ... (this function is unchanged, it uses the SQL function) ...
async def get_offerings_taught_by_teacher(current_user: UserInDB = TeacherUser, db: Client = Depends(get_db)):
    try:
        response = db.rpc(
            'get_teacher_offerings_with_status',
            {'t_id': str(current_user.user_id)}
        ).execute()
        return response.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/offerings/{offering_id}/assign-ta")
# ... (this function is unchanged) ...
async def assign_ta_to_course(offering_id: UUID, ta_data: AssignTACreate, current_user: UserInDB = TeacherUser, db: Client = Depends(get_db)):
    try:
        offering_resp = db.table("course_offerings").select("offering_id").eq("offering_id", str(offering_id)).eq("teacher_id", str(current_user.user_id)).execute()
        if not offering_resp.data:
            raise HTTPException(status_code=403, detail="You are not the teacher for this offering.")
        ta_resp = db.table("teaching_assistants").select("ta_id").eq("ta_id", str(ta_data.ta_id)).execute()
        if not ta_resp.data:
            raise HTTPException(status_code=404, detail="Teaching Assistant not found.")
        completed_check = db.table("enrollments").select("enrollment_id", count="exact") \
                            .eq("offering_id", str(offering_id)) \
                            .eq("status", "completed") \
                            .execute()
        if completed_check.count > 0:
            raise HTTPException(status_code=400, detail="Cannot assign TA. This course offering is already completed and graded.")
        assignment_data = {"offering_id": str(offering_id), "ta_id": str(ta_data.ta_id)}
        response = db.table("course_tas").insert(assignment_data).execute()
        return {"message": "TA assigned successfully", "data": response.data[0]}
    except Exception as e:
        if isinstance(e, HTTPException): raise e
        if "duplicate key" in str(e):
            raise HTTPException(status_code=400, detail="This TA is already assigned to this offering.")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/offerings/{offering_id}/attendance", response_model=List[TeacherAttendanceStat])
# ... (this function is unchanged) ...
async def get_course_attendance_statistics(offering_id: UUID, current_user: UserInDB = TeacherUser, db: Client = Depends(get_db)):
    try:
        offering_resp = db.table("course_offerings").select("offering_id").eq("offering_id", str(offering_id)).eq("teacher_id", str(current_user.user_id)).execute()
        if not offering_resp.data:
            raise HTTPException(status_code=403, detail="You are not the teacher for this offering.")
        stats = db.rpc('get_course_attendance_stats', {'o_id': str(offering_id)}).execute()
        return stats.data
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")

@router.post("/offerings/{offering_id}/grades")
# ... (this function is unchanged) ...
async def assign_grades(offering_id: UUID, grades: List[GradeCreate], current_user: UserInDB = TeacherUser, db: Client = Depends(get_db)):
    try:
        offering_resp = db.table("course_offerings").select("offering_id").eq("offering_id", str(offering_id)).eq("teacher_id", str(current_user.user_id)).execute()
        if not offering_resp.data:
            raise HTTPException(status_code=403, detail="You are not the teacher for this offering.")
        updates_to_perform = []
        for grade_entry in grades:
            grade_str = grade_entry.grade.upper()
            grade_point = GRADE_TO_POINT_MAP.get(grade_str, 0.0)
            updates_to_perform.append({
                "student_id": str(grade_entry.student_id), "offering_id": str(offering_id),
                "grade": grade_str, "grade_point": grade_point, "status": "completed"
            })
        response = db.table("enrollments").upsert(updates_to_perform, on_conflict="student_id, offering_id").execute()
        return {"message": f"Successfully updated grades for {len(response.data)} students."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/offerings/{offering_id}/students", response_model=List[SimpleStudent])
# ... (this function is unchanged) ...
async def get_students_for_course(offering_id: UUID, current_user: UserInDB = TeacherUser, db: Client = Depends(get_db)):
    try:
        offering_resp = db.table("course_offerings").select("offering_id").eq("offering_id", str(offering_id)).eq("teacher_id", str(current_user.user_id)).execute()
        if not offering_resp.data:
            raise HTTPException(status_code=403, detail="You are not the teacher for this offering.")
        response = db.table("enrollments").select(
            "students!inner(student_id, roll_number, users!inner(full_name), profile_picture_url)"
        ).eq("offering_id", str(offering_id)).eq("status", "enrolled").execute()
        student_list = []
        for item in response.data:
            student_data = item['students']
            student_list.append(
                SimpleStudent(
                    student_id=student_data['student_id'], full_name=student_data['users']['full_name'],
                    roll_number=student_data['roll_number'], profile_picture_url=student_data['profile_picture_url']
                )
            )
        return student_list
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- 3. Other Endpoints ---
@router.get("/registration/active", response_model=dict)
async def get_active_registration_period(
    db: Client = Depends(get_db)
):
    """
    Gets the currently active registration period (semester_id, season, year).
    """
    try:
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        response = db.table("semesters").select(
            "semester_id, academic_year, season"
        ).eq("is_active", True
        ).gt("registration_end_date", now
        ).lt("registration_start_date", now
        ).limit(1).single().execute()
        
        return response.data
    
    except APIError as e:
        if e.code == "PGRST116": # "0 rows found"
            return {"semester_id": None, "academic_year": None, "season": None} 
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/available-tas", response_model=List[UserInDB])
# ... (this function is unchanged) ...
async def get_available_tas(db: Client = Depends(get_db)):
    try:
        response = db.table("users").select("*").eq("role", "ta").execute()
        return response.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))