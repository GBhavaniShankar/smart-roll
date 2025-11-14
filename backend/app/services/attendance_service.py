import httpx
import base64
from typing import List, Dict
from uuid import UUID
from datetime import date
from supabase import Client
from app.config import settings
from fastapi import HTTPException

class AttendanceService:
    def __init__(self, db: Client):
        self.db = db
        self.cv_api_endpoint = settings.CV_API_ENDPOINT

    async def mark_attendance_from_image(
        self,
        offering_id: UUID, 
        class_image_bytes: bytes,
        marked_by_id: UUID
    ) -> Dict:
        """
        Core service to mark attendance for a specific offering.
        1. Fetches enrolled students and their embeddings.
        2. Calls the external CV API.
        3. Parses the new, richer response and updates the database.
        """
        
        # 1. Fetch enrolled students and their face embeddings
        try:
            enrolled_students_resp = (
                self.db.table("enrollments")
                .select("students(student_id, face_embedding)")
                .eq("offering_id", str(offering_id))
                .eq("status", "enrolled")
                .execute()
            )
            
            if not enrolled_students_resp.data:
                raise ValueError("No students are enrolled in this course offering.")

            enrolled_list = []
            student_id_map = {}
            for item in enrolled_students_resp.data:
                student_data = item.get('students')
                if student_data and student_data.get('face_embedding'):
                    enrolled_list.append({
                        "student_id": student_data['student_id'],
                        "face_embedding": student_data['face_embedding']
                    })
                    student_id_map[student_data['student_id']] = student_data
            
            if not enrolled_list:
                raise ValueError("No enrolled students have face embeddings registered.")

        except Exception as e:
            print(f"DB Error fetching students: {e}")
            raise HTTPException(status_code=500, detail=f"Database error: {e}")

        # 2. Call External CV API
        cv_api_payload = {
            "class_image": base64.b64encode(class_image_bytes).decode('utf-8'),
            "course_id": str(offering_id), # Send offering_id as the identifier
            "enrolled_students": enrolled_list
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(self.cv_api_endpoint, json=cv_api_payload)
                response.raise_for_status() 
                cv_data = response.json() # This is the new, rich response
                
                # --- [THIS IS THE UPDATED LOGIC] ---
                # Core logic (still works)
                present_student_ids = set(cv_data.get("present_students", []))
                
                # [NEW] Get the extra data from the new response model
                metrics = cv_data.get("metrics", {})
                unknown_faces = cv_data.get("unknown_faces", [])
                # --- [END OF UPDATE] ---
        
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail=f"CV API Error: {e.response.text}")
        except httpx.RequestError as e:
            raise HTTPException(status_code=503, detail=f"Could not connect to CV API: {e}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error processing CV API response: {e}")

        # 3. Update Database (This logic is unchanged)
        today = date.today()
        attendance_records_to_insert = []
        
        all_student_ids = set(student_id_map.keys())
        absent_student_ids = all_student_ids - present_student_ids
        
        for student_id in all_student_ids:
            status = "present" if student_id in present_student_ids else "absent"
            attendance_records_to_insert.append({
                "offering_id": str(offering_id),
                "student_id": student_id,
                "date": str(today),
                "status": status,
                "marked_by": str(marked_by_id)
            })
            
        try:
            self.db.table("attendance_records").upsert(
                attendance_records_to_insert,
                on_conflict="offering_id, student_id, date"
            ).execute()
        
        except Exception as e:
            print(f"DB Error inserting attendance: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to save attendance records: {e}")

        # 4. [UPDATED] Return the richer response to the frontend
        return {
            "message": "Attendance marked successfully",
            "offering_id": str(offering_id),
            "date": str(today),
            "present_count": len(present_student_ids),
            "absent_count": len(absent_student_ids),
            "metrics": metrics, # <-- NEW
            "unknown_faces": unknown_faces # <-- NEW
        }