from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Literal
from uuid import UUID
import datetime
from app.models.user import Role

Stream = Literal['CSE', 'DSE', 'EE']

class StudentCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    roll_number: str
    stream: Stream
    current_semester: int = Field(..., gt=0, le=8)
    cgpa: Optional[float] = Field(None, ge=0.0, le=10.0)

class StudentProfile(BaseModel):
    user_id: UUID
    email: EmailStr
    full_name: str
    role: Role
    roll_number: str
    stream: Stream
    current_semester: int
    cgpa: Optional[float]
    profile_picture_url: Optional[str]
    created_at: datetime.datetime

    class Config:
        orm_mode = True
        
class GradeReport(BaseModel):
    course_code: str
    course_name: str
    grade: str
    attendance_percentage: float

    class Config:
        from_attributes = True

# ... (imports)
from app.models.course import CourseInDB # <-- Add this if not present

# ... (StudentCreate)

class StudentProfile(BaseModel):
    user_id: UUID
    email: EmailStr
    full_name: str
    role: Role
    roll_number: str
    stream: Stream
    current_semester: int
    cgpa: float # <-- Change from Optional[float] to float
    profile_picture_url: Optional[str]
    created_at: datetime.datetime

    class Config:
        from_attributes = True

class GradeReport(BaseModel):
    course_code: str
    course_name: str
    semester: Optional[int] # <-- ADD THIS
    grade: str
    attendance_percentage: float 

    class Config:
        from_attributes = True

# NEW: Model for the new "Current Courses" card
class CurrentCourse(BaseModel):
    course_id: UUID
    course_code: str
    course_name: str
    teacher: Optional[dict] # Will contain teacher's name
    
    class Config:
        from_attributes = True

# NEW: Model for the GPA/SGPA response
class GpaReport(BaseModel):
    sgpa: float
    cgpa_till_semester: float