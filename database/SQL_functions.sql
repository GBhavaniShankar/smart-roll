-- This file contains all helper functions (RPCs) for the application.
-- Run this entire script once.

-- 1. increment_all_student_semesters
CREATE OR REPLACE FUNCTION public.increment_all_student_semesters()
RETURNS void AS $$
BEGIN
    UPDATE public.students
    SET current_semester = current_semester + 1
    WHERE current_semester < 8;
END;
$$ LANGUAGE plpgsql;

-- 2. get_total_class_days (uses offering_id)
CREATE OR REPLACE FUNCTION public.get_total_class_days(o_id UUID)
RETURNS BIGINT AS $$
    SELECT COUNT(DISTINCT date)
    FROM public.attendance_records
    WHERE offering_id = o_id;
$$ LANGUAGE sql;

-- 3. get_course_attendance_stats (uses offering_id)
CREATE OR REPLACE FUNCTION public.get_course_attendance_stats(o_id UUID)
RETURNS TABLE (
    student_id UUID, full_name TEXT, roll_number TEXT,
    total_classes BIGINT, attended_classes BIGINT, attendance_percentage DECIMAL
) AS $$
DECLARE
    total_class_days BIGINT;
BEGIN
    SELECT public.get_total_class_days(o_id) INTO total_class_days;
    RETURN QUERY
    SELECT
        s.student_id, u.full_name::TEXT, s.roll_number::TEXT,
        COALESCE(total_class_days, 0) AS total_classes,
        COUNT(ar.status) FILTER (WHERE ar.status = 'present') AS attended_classes,
        CASE
            WHEN COALESCE(total_class_days, 0) > 0 THEN
                TRUNC((COUNT(ar.status) FILTER (WHERE ar.status = 'present') * 100.0) / total_class_days, 2)
            ELSE 0.0
        END
    FROM public.enrollments e
    JOIN public.students s ON e.student_id = s.student_id
    JOIN public.users u ON s.student_id = u.user_id
    LEFT JOIN public.attendance_records ar ON e.offering_id = ar.offering_id AND e.student_id = ar.student_id
    WHERE e.offering_id = o_id AND e.status = 'enrolled'
    GROUP BY s.student_id, u.full_name, s.roll_number, total_class_days;
END;
$$ LANGUAGE plpgsql;

-- 4. get_student_sgpa
CREATE OR REPLACE FUNCTION public.get_student_sgpa(s_id UUID, target_sem_id UUID)
RETURNS DECIMAL AS $$
    SELECT COALESCE(SUM(c.credits * e.grade_point) / SUM(c.credits), 0.0)
    FROM public.enrollments e
    JOIN public.course_offerings co ON e.offering_id = co.offering_id
    JOIN public.courses c ON co.course_id = c.course_id
    WHERE e.student_id = s_id
      AND e.status = 'completed'
      AND e.grade_point IS NOT NULL
      AND co.semester_id = target_sem_id;
$$ LANGUAGE sql;

-- 5. get_student_cgpa
CREATE OR REPLACE FUNCTION public.get_student_cgpa(s_id UUID, max_sem_date DATE DEFAULT NULL)
RETURNS DECIMAL AS $$
    SELECT COALESCE(SUM(c.credits * e.grade_point) / SUM(c.credits), 0.0)
    FROM public.enrollments e
    JOIN public.course_offerings co ON e.offering_id = co.offering_id
    JOIN public.semesters s ON co.semester_id = s.semester_id
    JOIN public.courses c ON co.course_id = c.course_id
    WHERE e.student_id = s_id
      AND e.status = 'completed'
      AND e.grade_point IS NOT NULL
      AND (max_sem_date IS NULL OR s.start_date <= max_sem_date);
$$ LANGUAGE sql;

-- 6. get_student_course_history
CREATE OR REPLACE FUNCTION public.get_student_course_history(s_id UUID, target_sem_id UUID DEFAULT NULL)
RETURNS TABLE (
    course_code TEXT, course_name TEXT, semester_id UUID, 
    academic_year TEXT, season TEXT, logical_semester INT,
    grade VARCHAR(2), attendance_percentage DECIMAL
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        c.course_code::TEXT,
        c.course_name::TEXT,
        s.semester_id,
        s.academic_year::TEXT,
        s.season::TEXT,
        c.logical_semester,
        e.grade,
        (
            SELECT
                CASE
                    WHEN (SELECT public.get_total_class_days(e.offering_id)) > 0 THEN
                        TRUNC(((SELECT COUNT(*) FROM public.attendance_records ar 
                                WHERE ar.student_id = e.student_id 
                                  AND ar.offering_id = e.offering_id 
                                  AND ar.status = 'present') * 100.0) / 
                              (SELECT public.get_total_class_days(e.offering_id)), 2)
                    ELSE 0.0
                END
        ) AS attendance_percentage
    FROM public.enrollments e
    JOIN public.course_offerings co ON e.offering_id = co.offering_id
    JOIN public.semesters s ON co.semester_id = s.semester_id
    JOIN public.courses c ON co.course_id = c.course_id
    WHERE e.student_id = s_id
      AND e.status = 'completed'
      AND e.grade IS NOT NULL
      AND (target_sem_id IS NULL OR co.semester_id = target_sem_id);
END;
$$ LANGUAGE plpgsql;

-- 7. get_teacher_offerings_with_status
CREATE OR REPLACE FUNCTION public.get_teacher_offerings_with_status(t_id UUID)
RETURNS TABLE (
    offering_id UUID, course_id UUID, teacher_id UUID,
    semester_id UUID, logical_semester INTEGER, academic_year TEXT,
    season TEXT, course_code TEXT, course_name TEXT,
    stream stream_type, is_completed BOOLEAN
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        co.offering_id, co.course_id, co.teacher_id,
        co.semester_id,
        c.logical_semester,
        s.academic_year::TEXT,
        s.season::TEXT,
        c.course_code::TEXT,
        c.course_name::TEXT,
        c.stream,
        EXISTS (
            SELECT 1
            FROM public.enrollments e
            WHERE e.offering_id = co.offering_id
            AND e.status = 'completed'
        ) AS is_completed
    FROM
        public.course_offerings co
    JOIN
        public.courses c ON co.course_id = c.course_id
    JOIN
        public.semesters s ON co.semester_id = s.semester_id
    WHERE
        co.teacher_id = t_id
    ORDER BY
        s.start_date DESC;
END;
$$ LANGUAGE plpgsql;

-- 8. get_available_offerings_for_student
CREATE OR REPLACE FUNCTION public.get_available_offerings_for_student(s_id UUID)
RETURNS JSON AS $$
DECLARE
    student_semester INT;
    active_sem_id UUID;
    student_stream stream_type;
BEGIN
    SELECT s.current_semester, s.stream INTO student_semester, student_stream
    FROM public.students s WHERE s.student_id = s_id;
    
    SELECT semester_id INTO active_sem_id
    FROM public.semesters
    WHERE is_active = true
      AND registration_start_date < NOW()
      AND registration_end_date > NOW()
    LIMIT 1;
    
    IF active_sem_id IS NULL THEN
        RETURN '[]'::json;
    END IF;

    RETURN (
        SELECT COALESCE(json_agg(row_to_json(t)), '[]')
        FROM (
            SELECT 
                co.*,
                json_build_object(
                    'course_id', c.course_id,
                    'course_code', c.course_code,
                    'course_name', c.course_name,
                    'stream', c.stream,
                    'credits', c.credits,
                    'domain', c.domain,
                    'category', c.category,
                    'difficulty_level', c.difficulty_level,
                    'description', c.description,
                    'created_at', c.created_at,
                    'logical_semester', c.logical_semester
                ) AS course
            FROM public.course_offerings co
            JOIN public.courses c ON co.course_id = c.course_id
            WHERE co.semester_id = active_sem_id
              AND c.stream IN (student_stream, 'COMMON')
              AND (c.logical_semester = student_semester OR c.logical_semester IS NULL)
              AND NOT EXISTS (
                  SELECT 1 FROM public.enrollments e
                  WHERE e.student_id = s_id AND e.offering_id = co.offering_id
              )
        ) t
    );
END;
$$ LANGUAGE plpgsql;

-- 9. get_student_current_courses
CREATE OR REPLACE FUNCTION public.get_student_current_courses(s_id UUID)
RETURNS JSON AS $$
DECLARE
    student_semester INT;
BEGIN
    SELECT current_semester INTO student_semester
    FROM public.students WHERE student_id = s_id;

    RETURN (
        SELECT COALESCE(json_agg(row_to_json(t)), '[]'::json)
        FROM (
            SELECT
                c.course_id,
                c.course_code,
                c.course_name,
                json_build_object('full_name', u.full_name) AS teacher
            FROM public.enrollments e
            JOIN public.course_offerings co ON e.offering_id = co.offering_id
            JOIN public.courses c ON co.course_id = c.course_id
            JOIN public.teachers t ON co.teacher_id = t.teacher_id
            JOIN public.users u ON t.teacher_id = u.user_id
            WHERE e.student_id = s_id
              AND e.status = 'enrolled'
              AND (c.logical_semester = student_semester OR c.logical_semester IS NULL)
        ) t
    );
END;
$$ LANGUAGE plpgsql;

-- 10. get_student_current_attendance
CREATE OR REPLACE FUNCTION public.get_student_current_attendance(s_id UUID)
RETURNS TABLE (
    course_id UUID, -- This will be the offering_id
    course_name TEXT,
    total_classes BIGINT,
    attended_classes BIGINT,
    attendance_percentage DECIMAL
) AS $$
DECLARE
    student_semester INT;
BEGIN
    SELECT current_semester INTO student_semester
    FROM public.students WHERE student_id = s_id;

    RETURN QUERY
    SELECT
        e.offering_id AS course_id,
        c.course_name::TEXT,
        public.get_total_class_days(e.offering_id) AS total_classes,
        COUNT(ar.status) FILTER (WHERE ar.status = 'present') AS attended_classes,
        CASE
            WHEN public.get_total_class_days(e.offering_id) > 0 THEN
                TRUNC((COUNT(ar.status) FILTER (WHERE ar.status = 'present') * 100.0) / public.get_total_class_days(e.offering_id), 2)
            ELSE 0.0
        END AS attendance_percentage
    FROM public.enrollments e
    JOIN public.course_offerings co ON e.offering_id = co.offering_id
    JOIN public.courses c ON co.course_id = c.course_id
    LEFT JOIN public.attendance_records ar ON e.offering_id = ar.offering_id AND e.student_id = ar.student_id
    WHERE e.student_id = s_id
      AND e.status = 'enrolled'
      AND (c.logical_semester = student_semester OR c.logical_semester IS NULL)
    GROUP BY e.offering_id, c.course_name;
END;
$$ LANGUAGE plpgsql;