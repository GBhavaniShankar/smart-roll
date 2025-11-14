from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Literal
from uuid import UUID
import datetime
from app.models.course import CourseInDB

Stream = Literal['CSE', 'DSE', 'EE']

class StudentCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    roll_number: str
    stream: Stream
    # current_semester is set to 1 by default in admin router
    cgpa: Optional[float] = Field(None, ge=0.0, le=10.0)

class StudentProfile(BaseModel):
    user_id: UUID
    email: EmailStr
    full_name: str
    role: Literal['admin', 'teacher', 'student', 'ta']
    roll_number: str
    stream: Stream
    current_semester: int
    cgpa: float
    profile_picture_url: Optional[str]
    created_at: datetime.datetime

    class Config:
        from_attributes = True
        
# [UPDATED] This model now matches the SQL function
class GradeReport(BaseModel):
    course_code: str
    course_name: str
    semester_id: UUID
    academic_year: str
    season: str
    logical_semester: Optional[int]
    grade: str
    grade_point: Optional[float]
    domain: Optional[str]
    attendance_percentage: float
    
    class Config:
        from_attributes = True

class CurrentCourse(BaseModel):
    course_id: UUID
    course_code: str
    course_name: str
    teacher: Optional[dict]
    
    class Config:
        from_attributes = True

class GpaReport(BaseModel):
    sgpa: float
    cgpa_till_semester: float