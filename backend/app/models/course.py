from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from uuid import UUID
import datetime

Stream = Literal['CSE', 'DSE', 'EE', 'COMMON']
Category = Literal['core', 'professional_elective', 'open_elective', 'minor']
EnrollStatus = Literal['enrolled', 'completed', 'dropped']

class CourseBase(BaseModel):
    course_code: str
    course_name: str
    stream: Stream
    credits: int = Field(..., gt=0)
    domain: Optional[str] = None
    category: Category
    difficulty_level: int = Field(..., ge=1, le=10)
    description: Optional[str] = None
    logical_semester: Optional[int] = Field(None, gt=0, le=8) # <-- MOVED HERE

class CourseCreate(CourseBase):
    pass

class CourseInDB(CourseBase):
    course_id: UUID
    created_at: datetime.datetime
    class Config:
        from_attributes = True

# UPDATED: Teacher only needs to provide the course_id.
# The backend will find the active semester_id.
class CourseOfferingCreate(BaseModel):
    course_id: UUID

class PrerequisiteCreate(BaseModel):
    prerequisite_course_id: UUID
    is_mandatory: bool = True

class PrerequisiteInDB(PrerequisiteCreate):
    id: UUID
    course_id: UUID
    class Config:
        from_attributes = True

class AssignTACreate(BaseModel):
    ta_id: UUID
    
class GradeCreate(BaseModel):
    student_id: UUID
    grade: str = Field(..., max_length=2)

class RegistrationPeriodCreate(BaseModel):
    academic_year: str = Field(..., example="2025-26")
    season: Literal['Fall', 'Spring', 'Summer']
    registration_start_date: datetime.datetime
    registration_end_date: datetime.datetime
    start_date: Optional[datetime.date] = None
    end_date: Optional[datetime.date] = None

class RegistrationPeriodInDB(RegistrationPeriodCreate):
    semester_id: UUID
    is_active: bool
    created_by: UUID
    class Config:
        from_attributes = True
        
class EnrollmentCreate(BaseModel):
    offering_id: UUID
    
class EnrollmentInDB(BaseModel):
    enrollment_id: UUID
    student_id: UUID
    offering_id: UUID
    enrolled_at: datetime.datetime
    grade: Optional[str]
    status: EnrollStatus
    class Config:
        from_attributes = True

class SimpleStudent(BaseModel):
    student_id: UUID
    full_name: str
    roll_number: str
    profile_picture_url: Optional[str]
    class Config:
        from_attributes = True