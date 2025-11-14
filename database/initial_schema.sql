-- TechNova Institute of Technology - Final Schema

-- 1. Create custom ENUM types
CREATE TYPE public.user_role AS ENUM ('admin', 'teacher', 'student', 'ta');
CREATE TYPE public.stream_type AS ENUM ('CSE', 'DSE', 'EE', 'COMMON');
CREATE TYPE public.course_category AS ENUM ('core', 'professional_elective', 'open_elective', 'minor');
CREATE TYPE public.enrollment_status AS ENUM ('enrolled', 'completed', 'dropped');
CREATE TYPE public.attendance_status AS ENUM ('present', 'absent');
CREATE TYPE public.semester_season AS ENUM ('Fall', 'Spring', 'Summer');

-- 2. Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 3. Users Table
CREATE TABLE public.users (
    user_id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    role public.user_role NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 4. Students Table
CREATE TABLE public.students (
    student_id UUID PRIMARY KEY REFERENCES public.users(user_id) ON DELETE CASCADE,
    roll_number VARCHAR(50) UNIQUE NOT NULL,
    stream public.stream_type NOT NULL,
    current_semester INTEGER CHECK (current_semester > 0 AND current_semester <= 8),
    cgpa DECIMAL(4, 2) CHECK (cgpa >= 0.0 AND cgpa <= 10.0),
    profile_picture_url TEXT,
    face_embedding REAL[],
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 5. Teachers Table
CREATE TABLE public.teachers (
    teacher_id UUID PRIMARY KEY REFERENCES public.users(user_id) ON DELETE CASCADE,
    employee_id VARCHAR(50) UNIQUE NOT NULL,
    department public.stream_type NOT NULL,
    specialization VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 6. Teaching Assistants Table
CREATE TABLE public.teaching_assistants (
    ta_id UUID PRIMARY KEY REFERENCES public.users(user_id) ON DELETE CASCADE,
    student_id UUID UNIQUE REFERENCES public.students(student_id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 7. Courses Table (The "Catalog")
CREATE TABLE public.courses (
    course_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    course_code VARCHAR(20) UNIQUE NOT NULL,
    course_name VARCHAR(255) NOT NULL,
    stream public.stream_type NOT NULL,
    credits INTEGER CHECK (credits > 0),
    domain VARCHAR(100),
    category public.course_category NOT NULL,
    difficulty_level INTEGER CHECK (difficulty_level >= 1 AND difficulty_level <= 10),
    description TEXT,
    logical_semester INTEGER CHECK (logical_semester > 0 AND logical_semester <= 8), -- Can be NULL
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 8. Course Prerequisites Table
CREATE TABLE public.course_prerequisites (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    course_id UUID NOT NULL REFERENCES public.courses(course_id) ON DELETE CASCADE,
    prerequisite_course_id UUID NOT NULL REFERENCES public.courses(course_id) ON DELETE CASCADE,
    is_mandatory BOOLEAN DEFAULT TRUE,
    UNIQUE(course_id, prerequisite_course_id)
);

-- 9. Semesters Table
CREATE TABLE public.semesters (
    semester_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    academic_year VARCHAR(10) NOT NULL,
    season public.semester_season NOT NULL,
    start_date DATE, -- Actual semester start
    end_date DATE,   -- Actual semester end
    registration_start_date TIMESTAMPTZ NOT NULL,
    registration_end_date TIMESTAMPTZ NOT NULL,
    is_active BOOLEAN DEFAULT FALSE, -- Is registration currently active?
    created_by UUID REFERENCES public.users(user_id) ON DELETE SET NULL,
    CONSTRAINT semesters_academic_year_season_unique UNIQUE(academic_year, season)
);

-- 10. Course Offerings Table
CREATE TABLE public.course_offerings (
    offering_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    course_id UUID NOT NULL REFERENCES public.courses(course_id) ON DELETE CASCADE,
    teacher_id UUID NOT NULL REFERENCES public.teachers(teacher_id) ON DELETE SET NULL,
    semester_id UUID REFERENCES public.semesters(semester_id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(course_id, semester_id) 
);

-- 11. Enrollments Table
CREATE TABLE public.enrollments (
    enrollment_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    student_id UUID NOT NULL REFERENCES public.students(student_id) ON DELETE CASCADE,
    offering_id UUID NOT NULL REFERENCES public.course_offerings(offering_id) ON DELETE CASCADE,
    enrolled_at TIMESTAMPTZ DEFAULT NOW(),
    grade VARCHAR(2),
    grade_point DECIMAL(4, 2),
    status public.enrollment_status NOT NULL DEFAULT 'enrolled',
    UNIQUE(student_id, offering_id)
);

-- 12. Attendance Records Table
CREATE TABLE public.attendance_records (
    attendance_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    offering_id UUID NOT NULL REFERENCES public.course_offerings(offering_id) ON DELETE CASCADE,
    student_id UUID NOT NULL REFERENCES public.students(student_id) ON DELETE CASCADE,
    date DATE NOT NULL,
    status public.attendance_status NOT NULL,
    marked_by UUID REFERENCES public.users(user_id) ON DELETE SET NULL,
    class_image_url TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(offering_id, student_id, date)
);

-- 13. Course TAs Table
CREATE TABLE public.course_tas (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    offering_id UUID NOT NULL REFERENCES public.course_offerings(offering_id) ON DELETE CASCADE,
    ta_id UUID NOT NULL REFERENCES public.teaching_assistants(ta_id) ON DELETE CASCADE,
    assigned_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(offering_id, ta_id)
);

-- 14. Course Recommendations Table
CREATE TABLE public.course_recommendations (
    recommendation_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    student_id UUID NOT NULL REFERENCES public.students(student_id) ON DELETE CASCADE,
    course_id UUID NOT NULL REFERENCES public.courses(course_id) ON DELETE CASCADE,
    recommendation_score DECIMAL(5, 2) NOT NULL,
    semester INTEGER NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(student_id, course_id, semester)
);

-- 15. Add Indexes
CREATE INDEX idx_users_email ON public.users(email);
CREATE INDEX idx_students_roll_number ON public.students(roll_number);
CREATE INDEX idx_courses_course_code ON public.courses(course_code);
CREATE INDEX idx_offerings_course_id ON public.course_offerings(course_id);
CREATE INDEX idx_offerings_teacher_id ON public.course_offerings(teacher_id);
CREATE INDEX idx_enrollments_student_id ON public.enrollments(student_id);
CREATE INDEX idx_enrollments_offering_id ON public.enrollments(offering_id);
CREATE INDEX idx_attendance_student_id_offering_id ON public.attendance_records(student_id, offering_id);
CREATE INDEX idx_recommendations_student_id ON public.course_recommendations(student_id);