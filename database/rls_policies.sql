DO $$
DECLARE
    policy_name TEXT;
    table_name TEXT;
BEGIN
    FOR table_name IN 
        SELECT tablename FROM pg_tables 
        WHERE schemaname = 'public' AND tablename IN (
            'users', 'students', 'teachers', 'teaching_assistants', 
            'courses', 'course_offerings', 'semesters', 'course_prerequisites', 
            'course_tas', 'enrollments', 'attendance_records', 'course_recommendations'
        )
    LOOP
        FOR policy_name IN 
            SELECT policyname FROM pg_policies
            WHERE schemaname = 'public' AND tablename = table_name
        LOOP
            EXECUTE 'DROP POLICY IF EXISTS "' || policy_name || '" ON public."' || table_name || '";';
        END LOOP;
    END LOOP;
END $$;

CREATE OR REPLACE FUNCTION public.current_user_role()
RETURNS TEXT AS $$
DECLARE
    role_value TEXT;
BEGIN
    SELECT raw_user_meta_data->>'role'
    INTO role_value
    FROM auth.users
    WHERE id = auth.uid();
    RETURN role_value;
EXCEPTION
    WHEN OTHERS THEN
        RETURN NULL;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DO $$
BEGIN
    ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
    ALTER TABLE public.students ENABLE ROW LEVEL SECURITY;
    ALTER TABLE public.teachers ENABLE ROW LEVEL SECURITY;
    ALTER TABLE public.teaching_assistants ENABLE ROW LEVEL SECURITY;
    ALTER TABLE public.courses ENABLE ROW LEVEL SECURITY;
    ALTER TABLE public.course_offerings ENABLE ROW LEVEL SECURITY;
    ALTER TABLE public.semesters ENABLE ROW LEVEL SECURITY;
    ALTER TABLE public.course_prerequisites ENABLE ROW LEVEL SECURITY;
    ALTER TABLE public.course_tas ENABLE ROW LEVEL SECURITY;
    ALTER TABLE public.enrollments ENABLE ROW LEVEL SECURITY;
    ALTER TABLE public.attendance_records ENABLE ROW LEVEL SECURITY;
    ALTER TABLE public.course_recommendations ENABLE ROW LEVEL SECURITY;
END $$;

-- 1. users table
CREATE OR REPLACE POLICY "Admins can manage all users" ON public.users
    FOR ALL USING (public.current_user_role() = 'admin');
CREATE OR REPLACE POLICY "Users can view their own data" ON public.users
    FOR SELECT USING (user_id = auth.uid());

-- 2. students table
CREATE OR REPLACE POLICY "Admins can manage all students" ON public.students
    FOR ALL USING (public.current_user_role() = 'admin');
CREATE OR REPLACE POLICY "Students can see/update their own profile" ON public.students
    FOR ALL USING (student_id = auth.uid()) WITH CHECK (student_id = auth.uid());
CREATE OR REPLACE POLICY "Teachers can see their students" ON public.students
    FOR SELECT USING (EXISTS (
        SELECT 1 FROM public.enrollments e
        JOIN public.course_offerings co ON e.offering_id = co.offering_id
        WHERE e.student_id = public.students.student_id AND co.teacher_id = auth.uid()
    ));
CREATE OR REPLACE POLICY "TAs can see their students" ON public.students
    FOR SELECT USING (EXISTS (
        SELECT 1 FROM public.enrollments e
        JOIN public.course_tas ct ON e.offering_id = ct.offering_id
        WHERE e.student_id = public.students.student_id AND ct.ta_id = auth.uid()
    ));

-- 3. teachers table
CREATE OR REPLACE POLICY "Admins can manage all teachers" ON public.teachers
    FOR ALL USING (public.current_user_role() = 'admin');
CREATE OR REPLACE POLICY "Teachers can see/update their own profile" ON public.teachers
    FOR ALL USING (teacher_id = auth.uid()) WITH CHECK (teacher_id = auth.uid());
CREATE OR REPLACE POLICY "Authenticated users can view teacher profiles" ON public.teachers
    FOR SELECT USING (auth.role() = 'authenticated');

-- 4. teaching_assistants table
CREATE OR REPLACE POLICY "Admins can manage TAs" ON public.teaching_assistants
    FOR ALL USING (public.current_user_role() = 'admin');
CREATE OR REPLACE POLICY "TAs can see their own record" ON public.teaching_assistants
    FOR SELECT USING (ta_id = auth.uid());
CREATE OR REPLACE POLICY "Teachers can see TAs" ON public.teaching_assistants
    FOR SELECT USING (public.current_user_role() = 'teacher');

-- 5. courses (The "Catalog")
CREATE OR REPLACE POLICY "Admins/Teachers can manage course catalog" ON public.courses
    FOR ALL USING (public.current_user_role() IN ('admin', 'teacher'));
CREATE OR REPLACE POLICY "Authenticated users can view course catalog" ON public.courses
    FOR SELECT USING (auth.role() = 'authenticated');

-- 6. course_offerings
CREATE OR REPLACE POLICY "Admins can manage all offerings" ON public.course_offerings
    FOR ALL USING (public.current_user_role() = 'admin');
CREATE OR REPLACE POLICY "Teachers can manage their own offerings" ON public.course_offerings
    FOR ALL USING (teacher_id = auth.uid()) WITH CHECK (teacher_id = auth.uid());
CREATE OR REPLACE POLICY "Authenticated users can view offerings" ON public.course_offerings
    FOR SELECT USING (auth.role() = 'authenticated');

-- 7. semesters
CREATE OR REPLACE POLICY "Admins can manage semesters" ON public.semesters
    FOR ALL USING (public.current_user_role() = 'admin');
CREATE OR REPLACE POLICY "Authenticated users can view semesters" ON public.semesters
    FOR SELECT USING (auth.role() = 'authenticated');

-- 8. enrollments
CREATE OR REPLACE POLICY "Admins can see all enrollments" ON public.enrollments
    FOR SELECT USING (public.current_user_role() = 'admin');
CREATE OR REPLACE POLICY "Students can manage their own enrollments" ON public.enrollments
    FOR ALL USING (student_id = auth.uid()) WITH CHECK (student_id = auth.uid());
CREATE OR REPLACE POLICY "Teachers can manage enrollments for their offerings" ON public.enrollments
    FOR ALL USING (EXISTS (
        SELECT 1 FROM public.course_offerings co
        WHERE co.offering_id = public.enrollments.offering_id AND co.teacher_id = auth.uid()
    ));
CREATE OR REPLACE POLICY "TAs can manage enrollments for their offerings" ON public.enrollments
    FOR ALL USING (EXISTS (
        SELECT 1 FROM public.course_tas ct
        WHERE ct.offering_id = public.enrollments.offering_id AND ct.ta_id = auth.uid()
    ));

-- 9. attendance_records
CREATE OR REPLACE POLICY "Admins can see all attendance" ON public.attendance_records
    FOR SELECT USING (public.current_user_role() = 'admin');
CREATE OR REPLACE POLICY "Students can see their own attendance" ON public.attendance_records
    FOR SELECT USING (student_id = auth.uid());
CREATE OR REPLACE POLICY "Teachers can manage attendance for their offerings" ON public.attendance_records
    FOR ALL USING (EXISTS (
        SELECT 1 FROM public.course_offerings co
        WHERE co.offering_id = public.attendance_records.offering_id AND co.teacher_id = auth.uid()
    ));
CREATE OR REPLACE POLICY "TAs can manage attendance for their offerings" ON public.attendance_records
    FOR ALL USING (EXISTS (
        SELECT 1 FROM public.course_tas ct
        WHERE ct.offering_id = public.attendance_records.offering_id AND ct.ta_id = auth.uid()
    ));

-- 10. course_tas
CREATE OR REPLACE POLICY "Admins can manage all TAs" ON public.course_tas
    FOR ALL USING (public.current_user_role() = 'admin');
CREATE OR REPLACE POLICY "Teachers can manage TAs for their offerings" ON public.course_tas
    FOR ALL USING (EXISTS (
        SELECT 1 FROM public.course_offerings co
        WHERE co.offering_id = public.course_tas.offering_id AND co.teacher_id = auth.uid()
    ));
CREATE OR REPLACE POLICY "Authenticated users can view TAs" ON public.course_tas
    FOR SELECT USING (auth.role() = 'authenticated');

-- 11. course_prerequisites
CREATE OR REPLACE POLICY "Admins/Teachers can manage prerequisites" ON public.course_prerequisites
    FOR ALL USING (public.current_user_role() IN ('admin', 'teacher'));
CREATE OR REPLACE POLICY "Authenticated users can view prerequisites" ON public.course_prerequisites
    FOR SELECT USING (auth.role() = 'authenticated');

-- 12. course_recommendations
CREATE OR REPLACE POLICY "Admins can see all recommendations" ON public.course_recommendations
    FOR SELECT USING (public.current_user_role() = 'admin');
CREATE OR REPLACE POLICY "Students can see their own recommendations" ON public.course_recommendations
    FOR SELECT USING (student_id = auth.uid());