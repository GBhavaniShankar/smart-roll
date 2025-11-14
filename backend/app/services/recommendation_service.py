import httpx
from typing import List, Dict, Optional
from uuid import UUID
from pydantic import BaseModel
from supabase import Client
from app.config import settings
from fastapi import HTTPException

# --- 1. Define the Request Models (as you specified) ---

# [THIS IS THE FIX] semester_taken is now Optional[int]
class CompletedCourse(BaseModel):
    course_id: str # This is the course_code, e.g., "CS101"
    domain: Optional[str]
    grade_points: float
    semester_taken: Optional[int] # <-- CHANGED
    attendance_percentage: int

class StudentHistoryRequest(BaseModel):
    student_id: str
    stream: str
    current_semester: int
    cgpa_at_time_x: float
    completed_course_history_up_to_x: List[CompletedCourse]

# --- 2. Define the Response Models (as you specified) ---

class CourseScore(BaseModel):
    course_id: str # e.g., "CS5001"
    score: float
    relative_score: float

class RecommendationService:
    def __init__(self, db: Client):
        self.db = db
        self.ml_api_endpoint = settings.RECOMMENDATION_API_ENDPOINT

    async def get_recommendation_scores(
        self, student_data: StudentHistoryRequest
    ) -> Dict[str, Dict]:
        """
        [NEW LOGIC]
        Sends the student's entire history to the ML API in one request
        and gets back a list of scores.
        """
        
        scores_dict: Dict[str, Dict] = {}

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    self.ml_api_endpoint, 
                    json=student_data.model_dump()
                )
            
            if response.status_code == 200:
                response_data = response.json()
                scores_list = [CourseScore(**item) for item in response_data]
                
                for item in scores_list:
                    scores_dict[item.course_id] = {
                        "score": item.score,
                        "relative_score": item.relative_score
                    }
            else:
                print(f"--- WARNING: Recommendation API failed (Status {response.status_code}) ---")
                return {}
                
        except (httpx.RequestError, Exception) as e:
            print(f"--- WARNING: Recommendation API connection failed --- {e}")
            return {}
        
        return scores_dict