from fastapi import APIRouter, Depends, HTTPException, status, Query
from supabase import Client
from typing import List, Optional
from uuid import UUID
import traceback
from postgrest import APIError
import datetime

from app.database import get_db
from app.dependencies import StudentUser
from app.models.user import UserInDB
from app.models.student import (
    StudentProfile, GradeReport, CurrentCourse, GpaReport
)
from app.models.course import EnrollmentCreate, CourseInDB
from app.models.attendance import CourseAttendanceSummary, CourseAttendanceDetail
from app.services.recommendation_service import (
    RecommendationService, StudentHistoryRequest, CompletedCourse
)

router = APIRouter(
    prefix="/api/student",
    tags=["Student"],
    dependencies=[StudentUser]
)

def _print_error(e: Exception):
    """Helper function to print a formatted error traceback."""
    print("\n" + "="*50)
    print(f"--- FATAL ERROR IN STUDENT ROUTER ---")
    print(f"Error Type: {type(e)}")
    print(f"Error Details: {e}")
    print("\n--- FULL TRACEBACK ---")
    traceback.print_exc()
    print("="*50 + "\n")

# --- 1. Profile, GPA, and History Endpoints ---

@router.get("/profile", response_model=StudentProfile)
async def get_student_profile(
    current_user: UserInDB = StudentUser,
    db: Client = Depends(get_db)
):
    try:
        response = (
            db.table("students")
            .select("*, users!inner(email, full_name, role, created_at)")
            .eq("student_id", str(current_user.user_id))
            .single().execute()
        )
        if not response.data:
            raise HTTPException(status_code=404, detail="Student profile not found.")
        
        gpa_resp = db.rpc(
            'get_student_cgpa', 
            {'s_id': str(current_user.user_id), 'max_sem_date': None}
        ).execute()
        calculated_cgpa = gpa_resp.data if gpa_resp.data else 0.0
        
        student_data = response.data
        user_data = student_data.pop('users')
        profile_data = {
            **student_data, **user_data, "cgpa": calculated_cgpa
        }
        profile_data['user_id'] = profile_data['student_id']
        return StudentProfile(**profile_data)
    except Exception as e:
        _print_error(e)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/grades", response_model=List[GradeReport])
async def get_student_grades(
    semester_id: Optional[UUID] = Query(None),
    current_user: UserInDB = StudentUser,
    db: Client = Depends(get_db)
):
    try:
        params = {
            's_id': str(current_user.user_id),
            'target_sem_id': semester_id
        }
        response = db.rpc('get_student_course_history', params).execute()
        return response.data
    except Exception as e:
        _print_error(e)
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")

@router.get("/gpa", response_model=GpaReport)
async def get_gpa_for_semester(
    semester_id: UUID = Query(...),
    current_user: UserInDB = StudentUser,
    db: Client = Depends(get_db)
):
    try:
        student_id = str(current_user.user_id)
        sgpa_resp = db.rpc(
            'get_student_sgpa', 
            {'s_id': student_id, 'target_sem_id': str(semester_id)}
        ).execute()
        
        sem_date_resp = db.table("semesters").select("start_date").eq("semester_id", str(semester_id)).single().execute()
        max_date = sem_date_resp.data['start_date'] if sem_date_resp.data else None
        
        cgpa_resp = db.rpc(
            'get_student_cgpa',
            {'s_id': student_id, 'max_sem_date': max_date}
        ).execute()
        
        return GpaReport(
            sgpa=sgpa_resp.data if sgpa_resp.data else 0.0,
            cgpa_till_semester=cgpa_resp.data if cgpa_resp.data else 0.0
        )
    except Exception as e:
        _print_error(e)
        raise HTTPException(status_code=500, detail=str(e))

# --- 2. Current Semester Endpoints ---

@router.get("/courses/current", response_model=List[CurrentCourse])
async def get_current_courses(
    current_user: UserInDB = StudentUser,
    db: Client = Depends(get_db)
):
    try:
        response = db.rpc(
            'get_student_current_courses',
            {'s_id': str(current_user.user_id)}
        ).execute()
        return response.data
    except Exception as e:
        _print_error(e)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/attendance", response_model=List[CourseAttendanceSummary])
async def get_overall_attendance(
    current_user: UserInDB = StudentUser,
    db: Client = Depends(get_db)
):
    try:
        response = db.rpc(
            'get_student_current_attendance',
            {'s_id': str(current_user.user_id)}
        ).execute()
        return response.data
    except Exception as e:
        _print_error(e)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/offerings/{offering_id}/attendance", response_model=List[CourseAttendanceDetail])
async def get_attendance_for_course(
    offering_id: UUID,
    current_user: UserInDB = StudentUser,
    db: Client = Depends(get_db)
):
    try:
        response = db.table("attendance_records").select("date, status").eq("offering_id", str(offering_id)).eq("student_id", str(current_user.user_id)).order("date", desc=True).execute()
        return response.data
    except Exception as e:
        _print_error(e)
        raise HTTPException(status_code=500, detail=str(e))

# --- 3. Enrollment and Recommendation Endpoints ---

@router.get("/courses/available", response_model=List[dict])
async def get_available_courses_with_recommendations(
    current_user: UserInDB = StudentUser,
    db: Client = Depends(get_db)
):
    """
    1. Builds the student's full history.
    2. Calls the ML API *once* to get all scores.
    3. Finds available offerings and enriches them with the scores.
    """
    try:
        # 1. Get Student's profile
        student_resp = db.table("students").select("current_semester, stream, cgpa").eq("student_id", str(current_user.user_id)).single().execute()
        if not student_resp.data:
            raise HTTPException(status_code=404, detail="Student profile not found.")
        
        student_profile = student_resp.data
        
        # 2. Get Student's *full* academic history
        history_resp = db.rpc(
            'get_student_course_history', 
            {'s_id': str(current_user.user_id)}
        ).execute()

        completed_courses_list = []
        if history_resp.data:
            for course in history_resp.data:
                completed_courses_list.append(
                    CompletedCourse(
                        course_id=course['course_code'],
                        domain=course['domain'],
                        grade_points=course['grade_point'],
                        semester_taken=course['logical_semester'], # This can now be None
                        attendance_percentage=int(course['attendance_percentage'])
                    )
                )

        # 3. Build the single request object for the ML API
        student_data_blob = StudentHistoryRequest(
            student_id=str(current_user.user_id),
            stream=student_profile['stream'],
            current_semester=student_profile['current_semester'],
            cgpa_at_time_x=float(student_profile['cgpa']),
            completed_course_history_up_to_x=completed_courses_list
        )

        # 4. Call the ML API *ONCE*
        reco_service = RecommendationService(db)
        scored_courses_dict = await reco_service.get_recommendation_scores(student_data_blob)
        
        # 5. Get available offerings from the database
        offerings_resp = db.rpc(
            'get_available_offerings_for_student',
            {'s_id': str(current_user.user_id)}
        ).execute()
        
        if not offerings_resp.data:
            return []
            
        available_offerings = offerings_resp.data

        # 6. Enrich the offerings with the scores
        enriched_offerings = []
        for offering in available_offerings:
            course_code = offering['course']['course_code']
            
            # Get the score from the dict, or use a default
            score_data = scored_courses_dict.get(course_code, {
                "score": 50.0,
                "relative_score": 0.5,
                "reason": "N/A (default score)"
            })
            
            enriched_offerings.append({
                "offering_id": offering['offering_id'],
                "course_name": offering['course']['course_name'],
                "course_code": course_code,
                "credits": offering['course']['credits'],
                "domain": offering['course']['domain'],
                "semester": offering['course']['logical_semester'],
                "recommendation_score": score_data.get('score'),
                "relative_score": score_data.get('relative_score'),
                "reasoning": score_data.get('reason', 'N/A')
            })

        return enriched_offerings
        
    except APIError as e:
        _print_error(e)
        if e.code == "PGRST116": # 0 rows found (no registration period)
            return [] 
        raise HTTPException(status_code=500, detail=f"Database error: {e.message}")
    except Exception as e:
        _print_error(e)
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")

@router.post("/enroll", status_code=status.HTTP_201_CREATED)
async def enroll_in_course(
    enroll_data: EnrollmentCreate,
    current_user: UserInDB = StudentUser,
    db: Client = Depends(get_db)
):
    """ Enrolls the student in a course *offering*. """
    try:
        offering_id = str(enroll_data.offering_id)
        student_id = str(current_user.user_id)
        
        # 1. Check if registration is active
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        reg_resp = db.table("semesters").select(
            "semester_id"
        ).eq("is_active", True
        ).gt("registration_end_date", now
        ).lt("registration_start_date", now
        ).limit(1).execute()
        
        if not reg_resp.data:
            raise HTTPException(status_code=400, detail="Registration is not currently open.")

        # 2. Check if already enrolled
        enrolled_resp = db.table("enrollments").select("enrollment_id").eq("student_id", student_id).eq("offering_id", offering_id).execute()
        if enrolled_resp.data:
            raise HTTPException(status_code=400, detail="You are already enrolled in this offering.")

        # 3. Check prerequisites
        course_resp = db.table("course_offerings").select("course_id").eq("offering_id", offering_id).single().execute()
        if not course_resp.data:
            raise HTTPException(status_code=404, detail="Course offering not found.")
        course_id = course_resp.data['course_id']

        prereqs_resp = db.table("course_prerequisites").select("prerequisite_course_id, is_mandatory").eq("course_id", course_id).execute()
        
        if prereqs_resp.data:
            completed_resp = db.table("enrollments").select("course:course_offerings!inner(course_id)").eq("student_id", student_id).eq("status", "completed").execute()
            completed_course_ids = {c['course']['course_id'] for c in completed_resp.data if c.get('course')}
            
            for prereq in prereqs_resp.data:
                if prereq['is_mandatory'] and prereq['prerequisite_course_id'] not in completed_course_ids:
                    missing_course_resp = db.table("courses").select("course_name, course_code").eq("course_id", prereq['prerequisite_course_id']).single().execute()
                    missing_course_name = missing_course_resp.data.get('course_name', 'Unknown')
                    raise HTTPException(status_code=400, detail=f"Missing mandatory prerequisite: {missing_course_name}")

        # 4. Enroll
        enrollment_data = {
            "student_id": student_id,
            "offering_id": offering_id,
            "status": "enrolled"
        }
        response = db.table("enrollments").insert(enrollment_data).execute()
            
        return {"message": "Enrollment successful", "data": response.data[0]}
        
    except Exception as e:
        _print_error(e)
        raise HTTPException(status_code=500, detail=str(e))

#
# --- [THIS IS THE NEW, MISSING FUNCTION] ---
#
@router.get("/semesters/list", response_model=List[dict])
async def get_all_semesters_list_for_student(
    current_user: UserInDB = StudentUser,
    db: Client = Depends(get_db)
):
    """
    Gets a list of all *completed* semesters for the student's grade history.
    """
    try:
        response = db.rpc(
            'get_student_semesters', 
            {'s_id': str(current_user.user_id)}
        ).execute()
        return response.data
    except Exception as e:
        _print_error(e)
        raise HTTPException(status_code=500, detail=str(e))