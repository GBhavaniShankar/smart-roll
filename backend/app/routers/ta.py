from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query
from supabase import Client
from typing import List, Optional
from uuid import UUID
import traceback
from postgrest import APIError
import datetime

from app.database import get_db
from app.dependencies import TAUser, TAOrTeacherUser
from app.models.user import UserInDB
from app.models.attendance import AttendanceManualFix
from app.models.course import SimpleStudent
from app.services.attendance_service import AttendanceService

router = APIRouter(
    prefix="/api/ta",
    tags=["Teaching Assistant"],
    dependencies=[TAUser]
)

def _print_error(e: Exception):
    """Helper function to print a formatted error traceback."""
    print("\n" + "="*50)
    print(f"--- FATAL ERROR IN TA ROUTER ---")
    print(f"Error Type: {type(e)}")
    print(f"Error Details: {e}")
    print("\n--- FULL TRACEBACK ---")
    traceback.print_exc()
    print("="*50 + "\n")

@router.post("/attendance/mark", status_code=status.HTTP_201_CREATED)
async def mark_attendance_with_cv(
    offering_id: UUID = Query(..., description="The ID of the course offering"),
    class_photo: UploadFile = File(...),
    current_user: UserInDB = TAUser,
    db: Client = Depends(get_db)
):
    """ Marks attendance for a specific course *offering*. """
    try:
        # Verify TA is assigned to this offering
        ta_assignment = db.table("course_tas").select("id").eq("offering_id", str(offering_id)).eq("ta_id", str(current_user.user_id)).execute()
        if not ta_assignment.data:
            raise HTTPException(status_code=403, detail="You are not a TA for this course offering.")
            
        image_bytes = await class_photo.read()
        
        attn_service = AttendanceService(db)
        result = await attn_service.mark_attendance_from_image(
            offering_id=offering_id,
            class_image_bytes=image_bytes,
            marked_by_id=current_user.user_id
        )
        
        return result
        
    except Exception as e:
        _print_error(e)
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")

@router.put("/attendance/fix", status_code=status.HTTP_200_OK)
async def fix_attendance_manually(
    fix_data: AttendanceManualFix, # This model now uses offering_id
    current_user: UserInDB = TAOrTeacherUser,
    db: Client = Depends(get_db)
):
    """ Manually updates an attendance record for an offering. """
    try:
        # Verify TA/Teacher is assigned to this course
        if current_user.role == 'ta':
            assignment = db.table("course_tas").select("id").eq("offering_id", str(fix_data.offering_id)).eq("ta_id", str(current_user.user_id)).execute()
        else: # 'teacher'
            assignment = db.table("course_offerings").select("offering_id").eq("offering_id", str(fix_data.offering_id)).eq("teacher_id", str(current_user.user_id)).execute()
            
        if not assignment.data:
            raise HTTPException(status_code=403, detail="You are not authorized to modify attendance for this course offering.")

        record_to_upsert = {
            "offering_id": str(fix_data.offering_id),
            "student_id": str(fix_data.student_id),
            "date": str(fix_data.date),
            "status": fix_data.status,
            "marked_by": str(current_user.user_id)
        }
        
        response = db.table("attendance_records").upsert(
            record_to_upsert,
            on_conflict="offering_id, student_id, date"
        ).execute()
        
        if not response.data:
            raise HTTPException(status_code=500, detail="Failed to update attendance record.")
            
        return {"message": "Attendance record updated successfully", "data": response.data[0]}
        
    except Exception as e:
        _print_error(e)
        raise HTTPException(status_code=500, detail=str(e))

#
# --- [THIS IS THE FIXED FUNCTION] ---
#
@router.get("/courses", response_model=List[dict])
async def get_assigned_ta_courses(
    current_user: UserInDB = TAUser,
    db: Client = Depends(get_db)
):
    """ Gets all course *offerings* the TA is assigned to. """
    try:
        # [FIX] This query now joins all the way to semesters and courses
        response = db.table("course_tas").select(
            "offering:course_offerings!inner("
            "   offering_id, "
            "   semester:semesters!inner(academic_year, season), "
            "   course:courses!inner(course_code, course_name, logical_semester)"
            ")"
        ).eq("ta_id", str(current_user.user_id)).execute()
        
        # Flatten the complex response
        offerings = []
        for item in response.data:
            if not item.get('offering'): continue
            offering_data = item['offering']
            course_data = offering_data.pop('course', {})
            semester_data = offering_data.pop('semester', {})
            
            offerings.append({
                "offering_id": offering_data.get('offering_id'),
                "logical_semester": course_data.get('logical_semester'),
                "academic_year": semester_data.get('academic_year'),
                "season": semester_data.get('season'),
                "course_code": course_data.get('course_code'),
                "course_name": course_data.get('course_name')
            })
        return offerings
    except Exception as e:
        _print_error(e)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/offerings/{offering_id}/students", response_model=List[SimpleStudent])
async def get_students_for_ta_course(
    offering_id: UUID,
    current_user: UserInDB = TAUser,
    db: Client = Depends(get_db)
):
    """ Gets the student roster for a specific course *offering*. """
    try:
        # Verify TA is assigned
        ta_assignment = db.table("course_tas").select("id").eq("offering_id", str(offering_id)).eq("ta_id", str(current_user.user_id)).execute()
        if not ta_assignment.data:
            raise HTTPException(status_code=403, detail="You are not a TA for this course offering.")
            
        # Get enrolled students
        response = db.table("enrollments").select(
            "students!inner(student_id, roll_number, users!inner(full_name), profile_picture_url)"
        ).eq("offering_id", str(offering_id)).eq("status", "enrolled").execute()
        
        student_list = []
        for item in response.data:
            student_data = item['students']
            student_list.append(
                SimpleStudent(
                    student_id=student_data['student_id'],
                    full_name=student_data['users']['full_name'],
                    roll_number=student_data['roll_number'],
                    profile_picture_url=student_data['profile_picture_url']
                )
            )
        return student_list
    except Exception as e:
        _print_error(e)
        raise HTTPException(status_code=500, detail=str(e))