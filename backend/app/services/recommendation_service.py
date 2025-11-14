import httpx
import base64
from typing import List, Dict
from uuid import UUID
from datetime import date
from supabase import Client
from app.config import settings
from fastapi import HTTPException

class RecommendationService:
    def __init__(self, db: Client):
        self.db = db
        self.ml_api_endpoint = settings.RECOMMENDATION_API_ENDPOINT

    async def get_recommendations_for_student(
        self,
        student_id: UUID,
        student_profile: Dict, 
        available_courses: List[Dict] 
    ) -> Dict[str, Dict]: 
        """
        Enriches a list of available courses with recommendation scores.
        Returns a dictionary mapping course_id to its score data.
        [FIXED] Defaults score to 50.0 on failure.
        """
        
        try:
            # 1. Fetch student's academic history
            # [THIS IS THE FIX] It is 'self.db', not 'db'
            history_resp = self.db.table("enrollments").select(
                "grade, "
                "offering:course_offerings!inner(course:courses!inner(course_id))"
            ).eq("student_id", str(student_id)
            ).eq("status", "completed").execute()
            
            prerequisite_courses = []
            if history_resp.data:
                for item in history_resp.data:
                    if item.get('offering') and item['offering'].get('course'):
                        prerequisite_courses.append({
                            "course_id": item['offering']['course']['course_id'],
                            "grade": item['grade'],
                            "attendance_percentage": 85 # MOCK
                        })

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"DB error fetching student history: {e}")

        student_data = {
            "stream": student_profile['stream'],
            "current_semester": student_profile['current_semester'],
            "cgpa": float(student_profile['cgpa']),
            "prerequisite_courses": prerequisite_courses
        }

        scored_courses_dict = {}
        recommendations_to_cache = []

        async with httpx.AsyncClient(timeout=10.0) as client:
            for course in available_courses:
                course_id_str = str(course['course_id'])
                course_data = {
                    "stream": course['stream'],
                    "domain": course['domain'],
                    "category": course['category'],
                    "difficulty_level": course['difficulty_level'],
                    "prerequisites": [] 
                }
                
                payload = {
                    "student_id": str(student_id),
                    "course_id": course_id_str,
                    "student_data": student_data,
                    "course_data": course_data
                }
                
                score_data = {"recommendation_score": 50.0, "reasoning": "N/A (default score)"}
                
                try:
                    response = await client.post(self.ml_api_endpoint, json=payload)
                    if response.status_code == 200:
                        ml_data = response.json()
                        score = ml_data.get("recommendation_score")
                        reason = ml_data.get("reasoning", "")
                        
                        if score is not None:
                             score_data = {"recommendation_score": score, "reasoning": reason}
                        
                        recommendations_to_cache.append({
                            "student_id": str(student_id),
                            "course_id": course_id_str,
                            "recommendation_score": score_data["recommendation_score"],
                            "semester": student_profile['current_semester']
                        })
                
                except httpx.RequestError:
                    # If API is down, just keep score as 50.0
                    pass
                
                scored_courses_dict[course_id_str] = score_data

        if recommendations_to_cache:
            try:
                self.db.table("course_recommendations").upsert(
                    recommendations_to_cache,
                    on_conflict="student_id, course_id, semester"
                ).execute()
            except Exception as e:
                print(f"Warning: Failed to cache recommendations: {e}")

        return scored_courses_dict