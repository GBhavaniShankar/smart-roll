from pydantic import BaseModel, EmailStr, Field
from typing import Literal, Optional
from uuid import UUID
import datetime

Role = Literal['admin', 'teacher', 'student', 'ta']
Stream = Literal['CSE', 'DSE', 'EE', 'COMMON']

class UserBase(BaseModel):
    email: EmailStr
    full_name: str

class UserCreate(UserBase):
    password: str
    role: Role

class UserInDB(UserBase):
    user_id: UUID
    role: Role
    created_at: datetime.datetime

    class Config:
        orm_mode = True

class UserLogin(BaseModel):
    email: EmailStr
    password: str
    
class TeacherCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    employee_id: str
    department: Stream = Field(..., description="Use 'CSE', 'DSE', or 'EE'")
    specialization: Optional[str] = None

class TeacherProfile(UserBase):
    user_id: UUID
    role: Role = "teacher"
    employee_id: str
    department: Stream
    specialization: Optional[str] = None
    created_at: datetime.datetime

    class Config:
        orm_mode = True