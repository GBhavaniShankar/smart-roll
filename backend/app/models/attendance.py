from pydantic import BaseModel
from typing import Literal, Optional, List
from uuid import UUID
from datetime import date
import datetime

Status = Literal['present', 'absent']

class AttendanceRecord(BaseModel):
    attendance_id: UUID
    offering_id: UUID  # <-- Was course_id
    student_id: UUID
    date: date
    status: Status
    marked_by: Optional[UUID]
    class_image_url: Optional[str]
    created_at: datetime.datetime

    class Config:
        from_attributes = True

class AttendanceManualFix(BaseModel):
    student_id: UUID
    offering_id: UUID  # <-- CHANGED from course_id
    date: date
    status: Status

class CourseAttendanceSummary(BaseModel):
    course_id: UUID # Note: In student.py, we pass offering_id as this
    course_name: str
    total_classes: int
    attended_classes: int
    attendance_percentage: float
    
    class Config:
        from_attributes = True

class CourseAttendanceDetail(BaseModel):
    date: date
    status: Status
    
    class Config:
        from_attributes = True

class TeacherAttendanceStat(BaseModel):
    student_id: UUID
    full_name: str
    roll_number: str
    total_classes: int
    attended_classes: int
    attendance_percentage: float
    
    class Config:
        from_attributes = True