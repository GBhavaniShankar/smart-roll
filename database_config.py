# db_models.py
from datetime import datetime
from sqlalchemy import (
    create_engine, Column, Integer, String, Float, Boolean, 
    ForeignKey, DateTime, Enum, LargeBinary, TIMESTAMP, text
)
from sqlalchemy.orm import relationship, declarative_base, sessionmaker
import enum

# -----------------------------------
# Database Config
# -----------------------------------
DB_USER = "postgres"
DB_PASS = "password"
DB_HOST = "localhost"
DB_NAME = "attendance_db"

DATABASE_URL = f"postgresql+psycopg2://{DB_USER}:{DB_PASS}@{DB_HOST}:5432/{DB_NAME}"

# -----------------------------------
# Base & Engine
# -----------------------------------
engine = create_engine(DATABASE_URL, echo=True)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

# -----------------------------------
# ENUM: Semester
# -----------------------------------
class SemesterEnum(enum.Enum):
    JAN_MAY = "Jan - May"
    AUG_DEC = "Aug - Dec"

# -----------------------------------
# TABLE: Department
# -----------------------------------
class Department(Base):
    __tablename__ = "department"

    dept_id = Column(Integer, primary_key=True)
    dept_name = Column(String, nullable=False)

    instructors = relationship("Instructor", back_populates="department")
    courses = relationship("Course", back_populates="department")

# -----------------------------------
# TABLE: AcademicYear
# -----------------------------------
class AcademicYear(Base):
    __tablename__ = "academic_year"

    ay_id = Column(Integer, primary_key=True)
    ay_name = Column(String, nullable=False)

    course_offerings = relationship("CourseOffering", back_populates="academic_year")

# -----------------------------------
# TABLE: Instructor
# -----------------------------------
class Instructor(Base):
    __tablename__ = "instructor"

    instr_id = Column(Integer, primary_key=True)
    instr_name = Column(String, nullable=False)
    dept_id = Column(Integer, ForeignKey("department.dept_id"), nullable=False)

    department = relationship("Department", back_populates="instructors")
    course_offerings = relationship("CourseOffering", back_populates="instructor")

# -----------------------------------
# TABLE: Course
# -----------------------------------
class Course(Base):
    __tablename__ = "course"

    course_id = Column(String, primary_key=True)
    course_name = Column(String, nullable=False)
    dept_id = Column(Integer, ForeignKey("department.dept_id"), nullable=False)

    department = relationship("Department", back_populates="courses")
    offerings = relationship("CourseOffering", back_populates="course")

# -----------------------------------
# TABLE: CourseOffering
# -----------------------------------
class CourseOffering(Base):
    __tablename__ = "course_offering"

    offering_id = Column(Integer, primary_key=True)
    semester = Column(Enum(SemesterEnum), nullable=False)
    course_id = Column(String, ForeignKey("course.course_id"), nullable=False)
    ay_id = Column(Integer, ForeignKey("academic_year.ay_id"), nullable=False)
    instr_id = Column(Integer, ForeignKey("instructor.instr_id"), nullable=False)

    course = relationship("Course", back_populates="offerings")
    academic_year = relationship("AcademicYear", back_populates="course_offerings")
    instructor = relationship("Instructor", back_populates="course_offerings")

    student_courses = relationship("StudentCourse", back_populates="course_offering")
    sessions = relationship("Session", back_populates="course_offering")

# -----------------------------------
# TABLE: Students
# -----------------------------------
class Students(Base):
    __tablename__ = "students"

    student_id = Column(Integer, primary_key=True)
    student_name = Column(String, nullable=False)
    face_embeddings = Column(LargeBinary)  # optional: use pgvector
    face = Column(LargeBinary)

    student_courses = relationship("StudentCourse", back_populates="student")
    attendance_records = relationship("Attendance", back_populates="student")

# -----------------------------------
# TABLE: StudentCourse
# -----------------------------------
class StudentCourse(Base):
    __tablename__ = "student_course"

    sc_id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey("students.student_id"), nullable=False)
    course_offering_id = Column(Integer, ForeignKey("course_offering.offering_id"), nullable=False)
    marks = Column(Float)
    grade = Column(String(2))

    student = relationship("Students", back_populates="student_courses")
    course_offering = relationship("CourseOffering", back_populates="student_courses")

# -----------------------------------
# TABLE: Session
# -----------------------------------
class Session(Base):
    __tablename__ = "session"

    session_id = Column(Integer, primary_key=True, autoincrement=True)
    course_id = Column(Integer, ForeignKey("course_offering.offering_id"), nullable=False)
    session_time = Column(DateTime, default=datetime.utcnow)

    course_offering = relationship("CourseOffering", back_populates="sessions")
    attendances = relationship("Attendance", back_populates="session")

# -----------------------------------
# TABLE: Attendance
# -----------------------------------
class Attendance(Base):
    __tablename__ = "attendance"

    attendance_id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("session.session_id"), nullable=False)
    student_id = Column(Integer, ForeignKey("students.student_id"), nullable=False)
    present = Column(Boolean, default=False)
    face = Column(LargeBinary)
    confidence = Column(Float)
    marked_by = Column(String)
    marked_at = Column(TIMESTAMP, default=datetime.utcnow)

    session = relationship("Session", back_populates="attendances")
    student = relationship("Students", back_populates="attendance_records")

# -----------------------------------
# CREATE DATABASE IF NOT EXISTS
# -----------------------------------
def create_database_if_not_exists(user, password, host, dbname):
    """Creates the PostgreSQL database if it does not exist."""
    temp_engine = create_engine(f"postgresql+psycopg2://{user}:{password}@{host}/postgres")
    with temp_engine.connect() as conn:
        conn.execute(text("COMMIT"))  # end transaction block
        result = conn.execute(text(f"SELECT 1 FROM pg_database WHERE datname = '{dbname}'"))
        if not result.scalar():
            conn.execute(text(f"CREATE DATABASE {dbname}"))
            print(f"Database '{dbname}' created successfully.")
        else:
            print(f"Database '{dbname}' already exists.")
    temp_engine.dispose()

# -----------------------------------
# INITIALIZE ALL TABLES
# -----------------------------------
def init_db():
    """Creates all tables inside the target database."""
    Base.metadata.create_all(engine)
    print("All tables created successfully!")

# -----------------------------------
# MAIN EXECUTION
# -----------------------------------
if __name__ == "__main__":
    create_database_if_not_exists(DB_USER, DB_PASS, DB_HOST, DB_NAME)
    init_db()
