# app.py
import os
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import sqlite3
from datetime import datetime
import numpy as np # For numerical operations (e.g., mean)

app = Flask(__name__)
app.secret_key = 'your_super_secret_key' # IMPORTANT: Replace with a strong, random key in production!

DATABASE = 'database.db'

# --- Database Initialization ---
def init_db():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    # --- IMPORTANT DEVELOPMENT TIP: To reset your database schema during development ---
    # If you add new columns or change table structures, your existing database.db
    # might not update automatically due to 'CREATE TABLE IF NOT EXISTS'.
    # To force a schema update and resolve "no such column" errors:
    # 1. STOP your Flask application (if running).
    # 2. MANUALLY DELETE the 'database.db' file from your 'backend' directory.
    #    (e.g., in your file explorer, navigate to C:\Users\ADMIN\Documents\isp\backend\ and delete database.db)
    # 3. RESTART your Flask application. The init_db() function will then create a fresh database.
    #    You should see "Creating new database..." in your console.
    # Alternatively, for quick resets (use with caution as it deletes all data):
    # cursor.execute("DROP TABLE IF EXISTS feedback")
    # cursor.execute("DROP TABLE IF EXISTS tasks")
    # cursor.execute("DROP TABLE IF EXISTS attendance")
    # cursor.execute("DROP TABLE IF EXISTS students")
    # cursor.execute("DROP TABLE IF EXISTS courses")
    # cursor.execute("DROP TABLE IF EXISTS users")
    # cursor.execute("DROP TABLE IF EXISTS behaviour_ratings")
    # cursor.execute("DROP TABLE IF EXISTS student_feedback_to_admin") # New table to drop


    # Check if database file exists to print appropriate message
    if not os.path.exists(DATABASE):
        print("Creating new database...")
    else:
        print("Database already exists, checking schema...")


    # Create tables if they don't exist
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS courses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            total_expected_tasks INTEGER DEFAULT 10 -- New: For course completion calculation
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            unique_student_id TEXT UNIQUE NOT NULL, -- e.g., INT001, for display and internal reference
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL, -- Email should also be unique
            course_id INTEGER,
            user_id INTEGER UNIQUE, -- Link to users table for login, UNIQUE as one user per student
            FOREIGN KEY (course_id) REFERENCES courses(id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL, -- FK to students.id
            course_id INTEGER, -- New: Link task to a course
            title TEXT NOT NULL,
            description TEXT,
            due_date TEXT,
            status TEXT DEFAULT 'pending', -- 'pending', 'completed', 'overdue'
            mark REAL DEFAULT 0, -- Task mark (0-100)
            FOREIGN KEY (student_id) REFERENCES students(id),
            FOREIGN KEY (course_id) REFERENCES courses(id)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL, -- FK to students.id
            date TEXT NOT NULL, -- YYYY-MM-DD
            status TEXT NOT NULL, -- 'present', 'absent'
            FOREIGN KEY (student_id) REFERENCES students(id),
            UNIQUE(student_id, date) -- Ensure only one attendance record per student per day
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER, -- Can be NULL if general feedback
            student_id INTEGER NOT NULL, -- Link to student
            admin_id INTEGER NOT NULL, -- FK to users.id (admin)
            score REAL, -- e.g., 1-10 (general feedback score) - this might be redundant with category now
            comments TEXT,
            feedback_date TEXT NOT NULL, -- YYYY-MM-DD
            feedback_category TEXT, -- Re-added: 'Excellent', 'Good', 'Average', 'Poor'
            FOREIGN KEY (task_id) REFERENCES tasks(id),
            FOREIGN KEY (student_id) REFERENCES students(id),
            FOREIGN KEY (admin_id) REFERENCES users(id)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS behaviour_ratings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            date TEXT NOT NULL, -- YYYY-MM-DD
            rating INTEGER NOT NULL, -- 1-5 (1=Poor, 2=Average, 3=Good, 4=Very Good, 5=Excellent)
            admin_id INTEGER NOT NULL, -- FK to users.id (admin)
            FOREIGN KEY (student_id) REFERENCES students(id),
            FOREIGN KEY (admin_id) REFERENCES users(id),
            UNIQUE(student_id, date) -- One behaviour rating per student per day
        )
    ''')
    # NEW TABLE: For student feedback to admin
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS student_feedback_to_admin (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL, -- FK to students.id
            subject TEXT NOT NULL,
            message TEXT NOT NULL,
            timestamp TEXT NOT NULL, -- YYYY-MM-DD HH:MM:SS
            FOREIGN KEY (student_id) REFERENCES students(id)
        )
    ''')
    
    # Add some initial data (for testing)
    cursor.execute("INSERT OR IGNORE INTO users (username, password, role) VALUES (?, ?, ?)", ('admin', 'adminpass', 'admin'))
    
    # If 'intern1' user doesn't exist, create it and a corresponding student entry
    cursor.execute("SELECT id FROM users WHERE username = 'intern1'")
    intern1_user_id = cursor.fetchone()
    if not intern1_user_id:
        cursor.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", ('intern1', 'internpass', 'intern'))
        intern1_user_id = cursor.lastrowid
        cursor.execute("INSERT INTO students (unique_student_id, name, email, user_id) VALUES (?, ?, ?, ?)",
                       ('INT001', 'Intern One', 'intern1@example.com', intern1_user_id))
    
    # Add sample courses if they don't exist, with total_expected_tasks
    cursor.execute("INSERT OR IGNORE INTO courses (name, total_expected_tasks) VALUES (?, ?)", ('Web Development Basics', 10))
    cursor.execute("INSERT OR IGNORE INTO courses (name, total_expected_tasks) VALUES (?, ?)", ('Data Science Fundamentals', 8))
    cursor.execute("INSERT OR IGNORE INTO courses (name, total_expected_tasks) VALUES (?, ?)", ('Mobile App Development', 12))
    cursor.execute("INSERT OR IGNORE INTO courses (name, total_expected_tasks) VALUES (?, ?)", ('Cloud Computing Essentials', 7))
    cursor.execute("INSERT OR IGNORE INTO courses (name, total_expected_tasks) VALUES (?, ?)", ('Cybersecurity Basics', 9))
    
    # Get course IDs for sample tasks
    cursor.execute("SELECT id FROM courses WHERE name = 'Web Development Basics'")
    web_dev_course_id = cursor.fetchone()[0]
    cursor.execute("SELECT id FROM courses WHERE name = 'Data Science Fundamentals'")
    data_science_course_id = cursor.fetchone()[0]

    # Update Intern One to be assigned to 'Web Development Basics'
    cursor.execute("SELECT id FROM students WHERE unique_student_id = 'INT001'")
    int001_student_id = cursor.fetchone()
    if int001_student_id:
        int001_student_id = int001_student_id[0]
        cursor.execute("UPDATE students SET course_id = ? WHERE id = ?", (web_dev_course_id, int001_student_id))
        
        # Add sample tasks for Intern One if they don't exist, linked to course
        cursor.execute("SELECT id FROM tasks WHERE student_id = ? AND title = ?", (int001_student_id, 'Complete Flask Tutorial'))
        if not cursor.fetchone():
            cursor.execute("INSERT INTO tasks (student_id, course_id, title, description, due_date, status, mark) VALUES (?, ?, ?, ?, ?, ?, ?)",
                           (int001_student_id, web_dev_course_id, 'Complete Flask Tutorial', 'completed', '2025-08-10', 'completed', 90)) # Marked completed with a mark
        
        cursor.execute("SELECT id FROM tasks WHERE student_id = ? AND title = ?", (int001_student_id, 'Research ML Models'))
        if not cursor.fetchone():
            cursor.execute("INSERT INTO tasks (student_id, course_id, title, description, due_date, status, mark) VALUES (?, ?, ?, ?, ?, ?, ?)",
                           (int001_student_id, web_dev_course_id, 'Research ML Models', 'Research different ML models for performance prediction.', '2025-08-05', 'completed', 85)) # Marked completed with a mark

        cursor.execute("SELECT id FROM tasks WHERE student_id = ? AND title = ?", (int001_student_id, 'Build Simple API'))
        if not cursor.fetchone():
            cursor.execute("INSERT INTO tasks (student_id, course_id, title, description, due_date, status, mark) VALUES (?, ?, ?, ?, ?, ?, ?)",
                           (int001_student_id, web_dev_course_id, 'Build Simple API', 'Develop a basic REST API using Flask.', '2025-08-15', 'pending', 0))
        
        # Add sample attendance for Intern One
        cursor.execute("SELECT id FROM attendance WHERE student_id = ? AND date = '2025-07-20'", (int001_student_id,))
        if not cursor.fetchone():
            cursor.execute("INSERT INTO attendance (student_id, date, status) VALUES (?, ?, ?)", (int001_student_id, '2025-07-20', 'present'))
        cursor.execute("SELECT id FROM attendance WHERE student_id = ? AND date = '2025-07-21'", (int001_student_id,))
        if not cursor.fetchone():
            cursor.execute("INSERT INTO attendance (student_id, date, status) VALUES (?, ?, ?)", (int001_student_id, '2025-07-21', 'present'))
        cursor.execute("SELECT id FROM attendance WHERE student_id = ? AND date = '2025-07-22'", (int001_student_id,))
        if not cursor.fetchone():
            cursor.execute("INSERT INTO attendance (student_id, date, status) VALUES (?, ?, ?)", (int001_student_id, '2025-07-22', 'absent'))

        # Add sample feedback for Intern One (admin-to-student)
        cursor.execute("SELECT id FROM users WHERE username = 'admin'")
        admin_user_id = cursor.fetchone()[0]
        
        cursor.execute("SELECT id FROM feedback WHERE student_id = ? AND comments LIKE '%Good work on Flask%'", (int001_student_id,))
        if not cursor.fetchone():
            cursor.execute("INSERT INTO feedback (student_id, admin_id, score, comments, feedback_date, feedback_category) VALUES (?, ?, ?, ?, ?, ?)",
                           (int001_student_id, admin_user_id, 8.5, 'Good work on Flask tutorial, keep it up!', '2025-07-20', 'Good'))
        cursor.execute("SELECT id FROM feedback WHERE student_id = ? AND comments LIKE '%Excellent research skills%'", (int001_student_id,))
        if not cursor.fetchone():
            cursor.execute("INSERT INTO feedback (student_id, admin_id, score, comments, feedback_date, feedback_category) VALUES (?, ?, ?, ?, ?, ?)",
                           (int001_student_id, admin_user_id, 9.0, 'Excellent research skills demonstrated.', '2025-07-25', 'Excellent'))

        # Add sample behaviour ratings for Intern One
        cursor.execute("SELECT id FROM behaviour_ratings WHERE student_id = ? AND date = '2025-07-20'", (int001_student_id,))
        if not cursor.fetchone():
            cursor.execute("INSERT INTO behaviour_ratings (student_id, date, rating, admin_id) VALUES (?, ?, ?, ?)",
                           (int001_student_id, '2025-07-20', 4, admin_user_id))
        cursor.execute("SELECT id FROM behaviour_ratings WHERE student_id = ? AND date = '2025-07-21'", (int001_student_id,))
        if not cursor.fetchone():
            cursor.execute("INSERT INTO behaviour_ratings (student_id, date, rating, admin_id) VALUES (?, ?, ?, ?)",
                           (int001_student_id, '2025-07-21', 5, admin_user_id))

        # Add sample student-to-admin feedback
        cursor.execute("SELECT id FROM student_feedback_to_admin WHERE student_id = ? AND subject = 'Website UI Suggestion'", (int001_student_id,))
        if not cursor.fetchone():
            cursor.execute("INSERT INTO student_feedback_to_admin (student_id, subject, message, timestamp) VALUES (?, ?, ?, ?)",
                           (int001_student_id, 'Website UI Suggestion', 'Consider making the navigation menu more prominent.', datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        cursor.execute("SELECT id FROM student_feedback_to_admin WHERE student_id = ? AND subject = 'Query about Task 3'", (int001_student_id,))
        if not cursor.fetchone():
            cursor.execute("INSERT INTO student_feedback_to_admin (student_id, subject, message, timestamp) VALUES (?, ?, ?, ?)",
                           (int001_student_id, 'Query about Task 3', 'Could you provide more examples for Task 3 requirements?', datetime.now().strftime('%Y-%m-%d %H:%M:%S')))


    conn.commit()
    conn.close()

# --- Initialize database immediately when the script runs ---
init_db()

# --- Helper function to check admin login ---
def is_admin_logged_in():
    return 'role' in session and session['role'] == 'admin'

# --- Helper function to check intern login ---
def is_intern_logged_in():
    return 'role' in session and session['role'] == 'intern'

# --- Feature Calculation Functions ---
def calculate_attendance_rate(student_db_id):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM attendance WHERE student_id = ?", (student_db_id,))
    total_days = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM attendance WHERE student_id = ? AND status = 'present'", (student_db_id,))
    present_days = cursor.fetchone()[0]
    conn.close()
    return present_days / total_days if total_days > 0 else 0.0

def calculate_average_task_mark(student_db_id):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    # Only consider marks for completed tasks
    cursor.execute("SELECT AVG(mark) FROM tasks WHERE student_id = ? AND status = 'completed'", (student_db_id,))
    avg_mark = cursor.fetchone()[0]
    conn.close()
    return avg_mark if avg_mark is not None else 0.0

def calculate_average_feedback_score_numeric(student_db_id):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    # Map qualitative feedback to numerical values for averaging
    # Using a 0-3 scale for Poor-Excellent, then normalizing to 0-100 later if needed
    feedback_category_map = {'Poor': 0, 'Average': 1, 'Good': 2, 'Excellent': 3}
    
    cursor.execute("SELECT feedback_category FROM feedback WHERE student_id = ?", (student_db_id,))
    feedback_categories = cursor.fetchall()
    
    numeric_values = []
    for category_tuple in feedback_categories:
        category = category_tuple[0]
        if category in feedback_category_map:
            numeric_values.append(feedback_category_map[category])
            
    conn.close()
    # Convert average numeric category back to a 0-100 scale for consistency with other metrics
    # Max category value is 3 (Excellent). So (avg / 3) * 100
    avg_numeric = np.mean(numeric_values) if numeric_values else 0.0
    return (avg_numeric / 3.0) * 100.0 # Scale to 0-100

def calculate_average_behaviour_rating(student_db_id):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("SELECT AVG(rating) FROM behaviour_ratings WHERE student_id = ?", (student_db_id,))
    avg_rating = cursor.fetchone()[0]
    conn.close()
    # Behaviour rating is 1-5. Scale to 0-100. (avg - 1) / 4 * 100
    return ((avg_rating - 1) / 4.0) * 100.0 if avg_rating is not None else 0.0

def calculate_course_completion_percentage(student_db_id):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    # Get the course_id for the student
    cursor.execute("SELECT course_id FROM students WHERE id = ?", (student_db_id,))
    student_course_id = cursor.fetchone()
    
    if not student_course_id or student_course_id[0] is None:
        conn.close()
        return 0.0 # Student not assigned to a course

    student_course_id = student_course_id[0]

    # Get total expected tasks for that course
    cursor.execute("SELECT total_expected_tasks FROM courses WHERE id = ?", (student_course_id,))
    total_expected_tasks = cursor.fetchone()[0]

    if total_expected_tasks == 0:
        conn.close()
        return 0.0 # Avoid division by zero

    # Get completed tasks for this student for this course
    cursor.execute("SELECT COUNT(*) FROM tasks WHERE student_id = ? AND course_id = ? AND status = 'completed'", 
                   (student_db_id, student_course_id))
    completed_tasks = cursor.fetchone()[0]
    
    conn.close()
    return (completed_tasks / total_expected_tasks) * 100.0

# --- Overall Performance Calculation ---
def calculate_overall_performance_score(student_db_id):
    # Weights for each metric (adjust as needed)
    weights = {
        'attendance': 0.20, # 20%
        'task_mark': 0.30,  # 30%
        'behaviour': 0.15,  # 15%
        'feedback': 0.20,   # 20%
        'course_completion': 0.15 # 15%
    }

    # Calculate individual scaled scores (all are already 0-100)
    attendance_score = calculate_attendance_rate(student_db_id) * 100
    task_mark_score = calculate_average_task_mark(student_db_id)
    behaviour_score = calculate_average_behaviour_rating(student_db_id)
    feedback_score = calculate_average_feedback_score_numeric(student_db_id)
    course_completion_score = calculate_course_completion_percentage(student_db_id)

    # Handle cases where a metric might be N/A (e.g., no tasks, no feedback)
    # If a metric is N/A, we can treat it as 0 for score calculation, but report it as N/A in breakdown
    
    # Sum weighted scores
    overall_score = (
        attendance_score * weights['attendance'] +
        task_mark_score * weights['task_mark'] +
        behaviour_score * weights['behaviour'] +
        feedback_score * weights['feedback'] +
        course_completion_score * weights['course_completion']
    )
    
    # Ensure score is within 0-100 range
    overall_score = max(0, min(100, overall_score))

    # Determine performance category
    if overall_score >= 90:
        category = "Excellent"
    elif overall_score >= 75:
        category = "Good"
    elif overall_score >= 50:
        category = "Average"
    else:
        category = "Poor"
        
    return {
        'overall_score': round(overall_score, 2),
        'category': category,
        'breakdown': {
            'attendance': {'value': round(attendance_score, 2), 'weight': weights['attendance']},
            'task_mark': {'value': round(task_mark_score, 2), 'weight': weights['task_mark']},
            'behaviour': {'value': round(behaviour_score, 2), 'weight': weights['behaviour']},
            'feedback': {'value': round(feedback_score, 2), 'weight': weights['feedback']},
            'course_completion': {'value': round(course_completion_score, 2), 'weight': weights['course_completion']}
        }
    }


# --- Routes ---

@app.route('/')
def index():
    # Clear session on root access to ensure a fresh start for login
    session.clear()
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        # Clear session on GET request to login page to prevent automatic redirection
        session.clear()
    
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        selected_role = request.form['role'] # Get the selected role from the form

        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        # Check credentials and selected role
        cursor.execute("SELECT id, username, role FROM users WHERE username = ? AND password = ? AND role = ?", (username, password, selected_role))
        user = cursor.fetchone()
        conn.close()

        if user:
            session['user_id'] = user[0]
            session['username'] = user[1]
            session['role'] = user[2] # This will be the role from the DB, matching selected_role
            if session['role'] == 'admin':
                return redirect(url_for('admin_dashboard'))
            elif session['role'] == 'intern': # Using 'intern' as the role in DB for students
                return redirect(url_for('intern_dashboard'))
        else:
            flash('Invalid credentials or role mismatch', 'error') # More specific error message
            return render_template('login.html')
    return render_template('login.html')

@app.route('/admin/dashboard')
def admin_dashboard():
    if not is_admin_logged_in():
        return redirect(url_for('login'))

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    # Total Students
    cursor.execute("SELECT COUNT(*) FROM students")
    total_students = cursor.fetchone()[0]

    # Pending Tasks
    cursor.execute("SELECT COUNT(*) FROM tasks WHERE status = 'pending'")
    pending_tasks_count = cursor.fetchone()[0]

    # Total Courses
    cursor.execute("SELECT COUNT(*) FROM courses")
    total_courses = cursor.fetchone()[0]

    # Attendance Summary for Today
    today_date = datetime.now().strftime('%Y-%m-%d')
    cursor.execute("SELECT COUNT(*) FROM attendance WHERE date = ? AND status = 'present'", (today_date,))
    today_present_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM attendance WHERE date = ? AND status = 'absent'", (today_date,))
    today_absent_count = cursor.fetchone()[0]
    
    conn.close()
    return render_template('admin_dashboard.html', 
                           username=session['username'], 
                           total_students=total_students, 
                           pending_tasks=pending_tasks_count,
                           total_courses=total_courses, # Pass total courses
                           today_present_count=today_present_count, # Pass present count
                           today_absent_count=today_absent_count) # Pass absent count

@app.route('/admin/profile')
def admin_profile():
    if not is_admin_logged_in():
        return redirect(url_for('login'))
    return render_template('admin_profile.html', username=session['username'])

@app.route('/admin/add-course', methods=['GET', 'POST'])
def add_courses():
    if not is_admin_logged_in():
        return redirect(url_for('login'))
    
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    if request.method == 'POST':
        course_name = request.form['course_name']
        total_expected_tasks = request.form.get('total_expected_tasks', 10) # New: Get expected tasks
        try:
            cursor.execute("INSERT INTO courses (name, total_expected_tasks) VALUES (?, ?)", (course_name, total_expected_tasks))
            conn.commit()
            flash(f'Course "{course_name}" added successfully!', 'success')
        except sqlite3.IntegrityError:
            flash(f'Error: Course "{course_name}" already exists.', 'error')
        except Exception as e:
            flash(f'An unexpected error occurred: {e}', 'error')
        finally:
            conn.close()
            return redirect(url_for('add_courses')) # Redirect to clear form and show message
    
    # For GET request, fetch existing courses to display
    cursor.execute("SELECT name, total_expected_tasks FROM courses ORDER BY name")
    existing_courses = cursor.fetchall()
    conn.close()

    return render_template('add_courses.html', username=session['username'], existing_courses=existing_courses)

@app.route('/admin/get_course_suggestions')
def get_course_suggestions():
    if not is_admin_logged_in():
        return jsonify([]) # Return empty list if not logged in

    query = request.args.get('q', '').lower()
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM courses WHERE LOWER(name) LIKE ? ORDER BY name LIMIT 10", (f'%{query}%',))
    suggestions = [row[0] for row in cursor.fetchall()]
    conn.close()
    return jsonify(suggestions)


@app.route('/admin/course-validity')
def course_validity():
    if not is_admin_logged_in():
        return redirect(url_for('login'))
    return render_template('course_validity.html', username=session['username'])

@app.route('/admin/assignment')
def assignment():
    if not is_admin_logged_in():
        return redirect(url_for('login'))
    return render_template('assignment.html', username=session['username'])

@app.route('/admin/add-task', methods=['GET', 'POST'])
def add_task():
    if not is_admin_logged_in():
        return redirect(url_for('login'))

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    if request.method == 'POST':
        task_title = request.form['task_title']
        task_description = request.form['task_description']
        assigned_student_id = request.form['assigned_to'] # This is unique_student_id from form
        due_date = request.form['due_date']
        task_mark = request.form.get('task_mark', 0)
        task_course_name = request.form.get('task_course') # New: Get course name for task

        try:
            # Get the internal student_id (PK) from the unique_student_id
            cursor.execute("SELECT id FROM students WHERE unique_student_id = ?", (assigned_student_id,))
            student_db_id = cursor.fetchone()
            
            if not student_db_id:
                flash(f'Error: Student with ID "{assigned_student_id}" not found.', 'error')
                conn.close()
                return redirect(url_for('add_task'))
            student_db_id = student_db_id[0]

            # Get course_id for the task
            course_db_id = None
            if task_course_name:
                cursor.execute("SELECT id FROM courses WHERE name = ?", (task_course_name,))
                course_result = cursor.fetchone()
                if course_result:
                    course_db_id = course_result[0]
                else:
                    flash(f'Warning: Course "{task_course_name}" not found for task. Task added without course link.', 'warning')


            cursor.execute("INSERT INTO tasks (student_id, course_id, title, description, due_date, status, mark) VALUES (?, ?, ?, ?, ?, ?, ?)",
                           (student_db_id, course_db_id, task_title, task_description, due_date, 'pending', task_mark))
            conn.commit()
            flash('Task added successfully!', 'success')
        except Exception as e:
            conn.rollback()
            flash(f'An unexpected error occurred: {e}', 'error')
        finally:
            conn.close()
        return redirect(url_for('add_task')) # Redirect to clear form and show message

    # For GET request, fetch students and courses for the dropdowns
    cursor.execute("SELECT unique_student_id, name FROM students ORDER BY name")
    students = cursor.fetchall()
    cursor.execute("SELECT name FROM courses ORDER BY name")
    courses = [row[0] for row in cursor.fetchall()]
    conn.close()

    return render_template('add_task.html', username=session['username'], students=students, courses=courses)


@app.route('/admin/announcement')
def announcement():
    if not is_admin_logged_in():
        return redirect(url_for('login'))
    return render_template('announcement.html', username=session['username'])

@app.route('/admin/add-student', methods=['GET', 'POST'])
def add_student():
    if not is_admin_logged_in():
        return redirect(url_for('login'))

    if request.method == 'POST':
        unique_student_id = request.form['unique_student_id']
        name = request.form['student_name']
        email = request.form['student_email']
        temp_password = request.form['temp_password']
        assigned_course_name = request.form.get('assigned_course') # Get course name from form

        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        try:
            # Check if username (unique_student_id) or email already exists in users/students table
            cursor.execute("SELECT id FROM users WHERE username = ?", (unique_student_id,))
            if cursor.fetchone():
                flash('Error: Student ID (username) already exists.', 'error')
                conn.close()
                return redirect(url_for('add_student'))

            cursor.execute("SELECT id FROM students WHERE email = ?", (email,))
            if cursor.fetchone():
                flash('Error: Student email already exists.', 'error')
                conn.close()
                return redirect(url_for('add_student'))

            # 1. Create a user entry for the new intern
            cursor.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                           (unique_student_id, temp_password, 'intern'))
            new_user_id = cursor.lastrowid

            # 2. Get course_id if a course was selected
            course_db_id = None
            if assigned_course_name:
                cursor.execute("SELECT id FROM courses WHERE name = ?", (assigned_course_name,))
                course_result = cursor.fetchone()
                if course_result:
                    course_db_id = course_result[0]
                else:
                    flash(f'Warning: Course "{assigned_course_name}" not found. Student added without course.', 'warning')


            # 3. Add the student entry, linking to the new user
            cursor.execute("INSERT INTO students (unique_student_id, name, email, course_id, user_id) VALUES (?, ?, ?, ?, ?)",
                           (unique_student_id, name, email, course_db_id, new_user_id))
            conn.commit()
            flash('Student added successfully!', 'success')
            return redirect(url_for('student_list')) # Redirect to student list after adding
        except sqlite3.IntegrityError as e: # Catch specific integrity errors if any other unique constraint fails
            conn.rollback()
            flash(f'Database error: A unique entry already exists. Details: {e}', 'error')
        except Exception as e:
            conn.rollback()
            flash(f'An unexpected error occurred: {e}', 'error')
        finally:
            conn.close()

    # For GET request, fetch courses for the dropdown
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM courses ORDER BY name")
    courses = [row[0] for row in cursor.fetchall()]
    conn.close()

    return render_template('add_student.html', username=session['username'], courses=courses)

@app.route('/admin/student-list')
def student_list():
    if not is_admin_logged_in():
        return redirect(url_for('login'))

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    # Join students with courses to display course name
    cursor.execute('''
        SELECT s.unique_student_id, s.name, s.email, c.name AS course_name, s.id as student_db_id
        FROM students s
        LEFT JOIN courses c ON s.course_id = c.id
        ORDER BY s.name
    ''')
    students_data = cursor.fetchall()
    conn.close()
    return render_template('student_list.html', username=session['username'], students=students_data)

# New route for Pending Tasks
@app.route('/admin/pending-tasks')
def pending_tasks():
    if not is_admin_logged_in():
        return redirect(url_for('login'))
    
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    # Fetch pending tasks, joining with students to get student name
    cursor.execute("SELECT t.title, s.name, t.due_date, t.status FROM tasks t JOIN students s ON t.student_id = s.id WHERE t.status = 'pending' ORDER BY t.due_date")
    pending_tasks_data = cursor.fetchall()
    conn.close()
    return render_template('pending_tasks.html', username=session['username'], pending_tasks=pending_tasks_data)

# Removed predict_performance as it was for ML model.
# The overall performance calculation is now done in calculate_overall_performance_score.

@app.route('/admin/attendance', methods=['GET', 'POST'])
def attendance():
    if not is_admin_logged_in():
        return redirect(url_for('login'))
    
    # Determine the date for which to display attendance
    selected_date = request.args.get('selected_date', datetime.now().strftime('%Y-%m-%d'))

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    # Fetch all students and their attendance status for the selected date (if recorded)
    # Note: s.id is included as record[0] for use in forms
    cursor.execute(f'''
        SELECT s.id, s.unique_student_id, s.name, a.status
        FROM students s
        LEFT JOIN attendance a ON s.id = a.student_id AND a.date = ?
        ORDER BY s.name
    ''', (selected_date,))
    attendance_records = cursor.fetchall()
    conn.close()

    return render_template('attendance.html', username=session['username'], current_date=selected_date, attendance_records=attendance_records)

@app.route('/admin/mark-attendance', methods=['POST'])
def mark_attendance():
    if not is_admin_logged_in():
        return redirect(url_for('login'))

    student_db_id = request.form['student_id'] # This is the internal DB ID
    # Use .get() to avoid KeyError if 'attendance_date' is somehow missing
    date = request.form.get('attendance_date', datetime.now().strftime('%Y-%m-%d')) 
    status = request.form['status'] # 'present', 'absent', or 'not_recorded'

    if not date: # If date is still None or empty after .get()
        flash('Error: Attendance date was not provided.', 'error')
        return redirect(url_for('attendance'))

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    try:
        if status == 'not_recorded':
            # Delete the attendance record if 'Clear Status' is clicked
            cursor.execute("DELETE FROM attendance WHERE student_id = ? AND date = ?", (student_db_id, date))
            flash(f'Attendance for student ID {student_db_id} on {date} cleared.', 'info')
        else:
            # Check if an attendance record for this student and date already exists
            cursor.execute("SELECT id FROM attendance WHERE student_id = ? AND date = ?", (student_db_id, date))
            existing_record = cursor.fetchone()

            if existing_record:
                # Update existing record
                cursor.execute("UPDATE attendance SET status = ? WHERE id = ?", (status, existing_record[0]))
                flash(f'Attendance for student ID {student_db_id} on {date} updated to {status}.', 'success')
            else:
                # Insert new record
                cursor.execute("INSERT INTO attendance (student_id, date, status) VALUES (?, ?, ?)", (student_db_id, date, status))
                flash(f'Attendance for student ID {student_db_id} on {date} marked as {status}.', 'success')
        conn.commit()
    except Exception as e:
        conn.rollback()
        flash(f'Error marking attendance: {e}', 'error')
    finally:
        conn.close()
    return redirect(url_for('attendance', selected_date=date)) # Redirect back to the attendance page, preserving date


@app.route('/admin/add-feedback', methods=['GET', 'POST'])
def add_feedback():
    if not is_admin_logged_in():
        return redirect(url_for('login'))

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    if request.method == 'POST':
        student_unique_id = request.form['student_id']
        feedback_comments = request.form['comments']
        feedback_category = request.form['feedback_category']
        admin_id = session['user_id']
        feedback_date = datetime.now().strftime('%Y-%m-%d')
        task_id = request.form.get('task_id') # Optional: link to a specific task

        try:
            cursor.execute("SELECT id FROM students WHERE unique_student_id = ?", (student_unique_id,))
            student_db_id = cursor.fetchone()
            if not student_db_id:
                flash(f'Error: Student with ID "{student_unique_id}" not found.', 'error')
                conn.close()
                return redirect(url_for('add_feedback'))
            student_db_id = student_db_id[0]

            # Optional: Get actual task_id if provided and valid
            actual_task_id = None
            if task_id:
                cursor.execute("SELECT id FROM tasks WHERE id = ? AND student_id = ?", (task_id, student_db_id))
                task_result = cursor.fetchone()
                if task_result:
                    actual_task_id = task_result[0]
                else:
                    flash(f'Warning: Task ID {task_id} not found or does not belong to student {student_unique_id}. Feedback will be general.', 'warning')

            cursor.execute("INSERT INTO feedback (student_id, admin_id, comments, feedback_date, feedback_category, task_id) VALUES (?, ?, ?, ?, ?, ?)",
                           (student_db_id, admin_id, feedback_comments, feedback_date, feedback_category, actual_task_id))
            conn.commit()
            flash('Feedback added successfully!', 'success')
        except Exception as e:
            conn.rollback()
            flash(f'An unexpected error occurred: {e}', 'error')
        finally:
            conn.close()
        return redirect(url_for('add_feedback'))
    
    cursor.execute("SELECT unique_student_id, name FROM students ORDER BY name")
    students = cursor.fetchall()
    conn.close()
    return render_template('add_feedback.html', username=session['username'], students=students)

@app.route('/admin/add-behaviour-rating', methods=['GET', 'POST'])
def add_behaviour_rating():
    if not is_admin_logged_in():
        return redirect(url_for('login'))

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    if request.method == 'POST':
        student_unique_id = request.form['student_id']
        rating = int(request.form['rating'])
        rating_date = request.form.get('rating_date', datetime.now().strftime('%Y-%m-%d'))
        admin_id = session['user_id']

        try:
            cursor.execute("SELECT id FROM students WHERE unique_student_id = ?", (student_unique_id,))
            student_db_id = cursor.fetchone()
            if not student_db_id:
                flash(f'Error: Student with ID "{student_unique_id}" not found.', 'error')
                conn.close()
                return redirect(url_for('add_behaviour_rating'))
            student_db_id = student_db_id[0]

            # Check if rating for this student and date already exists
            cursor.execute("SELECT id FROM behaviour_ratings WHERE student_id = ? AND date = ?", (student_db_id, rating_date))
            existing_rating = cursor.fetchone()

            if existing_rating:
                cursor.execute("UPDATE behaviour_ratings SET rating = ? WHERE id = ?", (rating, existing_rating[0]))
                flash(f'Behaviour rating for {student_unique_id} on {rating_date} updated to {rating}.', 'success')
            else:
                cursor.execute("INSERT INTO behaviour_ratings (student_id, date, rating, admin_id) VALUES (?, ?, ?, ?)",
                               (student_db_id, rating_date, rating, admin_id))
                flash(f'Behaviour rating for {student_unique_id} on {rating_date} added as {rating}.', 'success')
            conn.commit()
        except Exception as e:
            conn.rollback()
            flash(f'An unexpected error occurred: {e}', 'error')
        finally:
            conn.close()
        return redirect(url_for('add_behaviour_rating'))

    cursor.execute("SELECT unique_student_id, name FROM students ORDER BY name")
    students = cursor.fetchall()
    conn.close()
    return render_template('add_behaviour_rating.html', username=session['username'], students=students, today_date=datetime.now().strftime('%Y-%m-%d'))


@app.route('/admin/performance') # This route will now link to the overall performance analysis for ALL students
def admin_performance_overview():
    if not is_admin_logged_in():
        return redirect(url_for('login'))
    
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("SELECT id, unique_student_id, name FROM students ORDER BY name")
    all_students_data = cursor.fetchall()
    conn.close()

    performance_summaries = []
    for student in all_students_data:
        student_db_id = student[0]
        unique_student_id = student[1]
        student_name = student[2]
        
        overall_performance = calculate_overall_performance_score(student_db_id)
        performance_summaries.append({
            'unique_student_id': unique_student_id,
            'name': student_name,
            'overall_score': overall_performance['overall_score'],
            'category': overall_performance['category']
        })

    return render_template('admin_performance_overview.html', 
                           username=session['username'], 
                           performance_summaries=performance_summaries)

@app.route('/admin/view-student-feedback')
def admin_view_student_feedback():
    if not is_admin_logged_in():
        return redirect(url_for('login'))
    
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT sf.subject, sf.message, sf.timestamp, s.name AS student_name, s.unique_student_id
        FROM student_feedback_to_admin sf
        JOIN students s ON sf.student_id = s.id
        ORDER BY sf.timestamp DESC
    ''')
    student_feedback_records = cursor.fetchall()
    conn.close()
    return render_template('admin_view_student_feedback.html', 
                           username=session['username'], 
                           student_feedback_records=student_feedback_records)

# --- NEW ROUTE: Admin Task Completion ---
@app.route('/admin/complete-tasks', methods=['GET', 'POST'])
def admin_complete_tasks():
    if not is_admin_logged_in():
        return redirect(url_for('login'))

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    if request.method == 'POST':
        tasks_to_update = 0
        for key, value in request.form.items():
            if key.startswith('completed_task_') and value == 'on':
                task_id = key.replace('completed_task_', '')
                mark_key = f'mark_{task_id}'
                mark = request.form.get(mark_key, 0) # Get mark, default to 0 if not provided
                
                try:
                    mark = float(mark)
                    if not (0 <= mark <= 100):
                        flash(f'Warning: Mark for task {task_id} must be between 0 and 100. Not updated.', 'warning')
                        continue # Skip this task if mark is invalid
                except ValueError:
                    flash(f'Warning: Invalid mark for task {task_id}. Not updated.', 'warning')
                    continue # Skip if mark is not a valid number

                try:
                    cursor.execute("UPDATE tasks SET status = 'completed', mark = ? WHERE id = ? AND status = 'pending'", (mark, task_id))
                    if cursor.rowcount > 0:
                        tasks_to_update += 1
                except Exception as e:
                    flash(f'Error updating task {task_id}: {e}', 'error')
        
        conn.commit()
        if tasks_to_update > 0:
            flash(f'{tasks_to_update} task(s) marked as completed and marks assigned!', 'success')
        else:
            flash('No tasks were updated.', 'info')
        
        conn.close()
        return redirect(url_for('admin_complete_tasks'))

    # GET request: Display all pending tasks
    cursor.execute('''
        SELECT t.id, t.title, t.description, t.due_date, s.name AS student_name, s.unique_student_id
        FROM tasks t
        JOIN students s ON t.student_id = s.id
        WHERE t.status = 'pending'
        ORDER BY t.due_date, s.name
    ''')
    pending_tasks = cursor.fetchall()
    conn.close()
    return render_template('complete_tasks.html', username=session['username'], pending_tasks=pending_tasks)


@app.route('/student/dashboard')
def intern_dashboard():
    if not is_intern_logged_in():
        return redirect(url_for('login'))

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    # Get the student_id associated with the logged-in intern's user_id
    cursor.execute("SELECT id, name, email FROM students WHERE user_id = ?", (session['user_id'],))
    student_data_row = cursor.fetchone()
    
    assigned_tasks = []
    suggested_courses = []
    today_attendance_status = "Not Recorded"
    overall_performance_data = {'overall_score': 0, 'category': 'N/A'}
    student_profile_data = {} # To hold profile details

    if student_data_row:
        current_student_db_id = student_data_row[0]
        student_profile_data = {
            'id': current_student_db_id, # Use actual DB ID here for consistency
            'name': student_data_row[1],
            'email': student_data_row[2]
        }
        
        # Fetch assigned tasks for the intern
        cursor.execute("SELECT title, description, due_date, status, mark FROM tasks WHERE student_id = ?", (current_student_db_id,))
        assigned_tasks = cursor.fetchall()

        # Fetch suggested courses (all courses for now, can be refined later)
        cursor.execute("SELECT name FROM courses ORDER BY name")
        suggested_courses = [row[0] for row in cursor.fetchall()]

        # Fetch today's attendance status for the intern
        today_date = datetime.now().strftime('%Y-%m-%d')
        cursor.execute("SELECT status FROM attendance WHERE student_id = ? AND date = ?", (current_student_db_id, today_date))
        attendance_result = cursor.fetchone()
        if attendance_result:
            today_attendance_status = attendance_result[0]

        # Calculate overall performance score and breakdown
        overall_performance_data = calculate_overall_performance_score(current_student_db_id)
        
    conn.close()
    return render_template('intern_dashboard.html', 
                           username=session['username'], 
                           tasks=assigned_tasks,
                           suggested_courses=suggested_courses,
                           today_attendance_status=today_attendance_status,
                           predicted_performance=overall_performance_data['category'], # Pass category for card
                           overall_score=overall_performance_data['overall_score'], # Pass score for progress bar
                           student_profile_data=student_profile_data)

# --- Student-specific Routes for Navigation ---

@app.route('/student/tasks')
def intern_tasks():
    if not is_intern_logged_in():
        return redirect(url_for('login'))
    
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM students WHERE user_id = ?", (session['user_id'],))
    student_id_row = cursor.fetchone()
    tasks = []
    if student_id_row:
        current_student_db_id = student_id_row[0]
        cursor.execute("SELECT title, description, due_date, status, mark FROM tasks WHERE student_id = ? ORDER BY due_date", (current_student_db_id,))
        tasks = cursor.fetchall()
    conn.close()
    return render_template('intern_tasks.html', username=session['username'], tasks=tasks)

@app.route('/student/attendance')
def intern_attendance():
    if not is_intern_logged_in():
        return redirect(url_for('login'))
    
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM students WHERE user_id = ?", (session['user_id'],))
    student_id_row = cursor.fetchone()
    attendance_records = []
    if student_id_row:
        current_student_db_id = student_id_row[0]
        # Fetch all attendance records for the student
        cursor.execute("SELECT date, status FROM attendance WHERE student_id = ? ORDER BY date DESC", (current_student_db_id,))
        attendance_records = cursor.fetchall()
    conn.close()
    return render_template('intern_attendance.html', username=session['username'], attendance_records=attendance_records)

@app.route('/student/courses')
def intern_courses():
    if not is_intern_logged_in():
        return redirect(url_for('login'))
    
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM courses ORDER BY name")
    suggested_courses = [row[0] for row in cursor.fetchall()]
    conn.close()
    return render_template('intern_courses.html', username=session['username'], suggested_courses=suggested_courses)

@app.route('/student/performance') # This is now the factor-wise analysis page for the intern
def intern_performance():
    if not is_intern_logged_in():
        return redirect(url_for('login'))
    
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM students WHERE user_id = ?", (session['user_id'],))
    student_id_row = cursor.fetchone()
    
    performance_data = None
    average_task_mark = 0.0 # Initialize
    if student_id_row:
        current_student_db_id = student_id_row[0]
        performance_data = calculate_overall_performance_score(current_student_db_id)
        average_task_mark = calculate_average_task_mark(current_student_db_id)
        
    conn.close()
    return render_template('intern_performance.html', 
                           username=session['username'], 
                           performance_data=performance_data,
                           average_task_mark=round(average_task_mark, 2)) # Pass average task mark

@app.route('/student/profile')
def intern_profile():
    if not is_intern_logged_in():
        return redirect(url_for('login'))
    
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    # Fetch student's profile details
    cursor.execute("SELECT s.unique_student_id, s.name, s.email, c.name FROM students s LEFT JOIN courses c ON s.course_id = c.id WHERE s.user_id = ?", (session['user_id'],))
    profile_data = cursor.fetchone()
    conn.close()

    student_profile = {}
    if profile_data:
        student_profile = {
            'unique_student_id': profile_data[0],
            'name': profile_data[1],
            'email': profile_data[2],
            'course': profile_data[3] if profile_data[3] else 'Not Assigned'
        }
    return render_template('intern_profile.html', username=session['username'], student_profile=student_profile)

@app.route('/student/feedback') # This is for admin-to-student feedback
def intern_feedback():
    if not is_intern_logged_in():
        return redirect(url_for('login'))
    
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM students WHERE user_id = ?", (session['user_id'],))
    student_id_row = cursor.fetchone()
    feedback_records = []
    if student_id_row:
        current_student_db_id = student_id_row[0]
        cursor.execute('''
            SELECT f.comments, f.score, f.feedback_date, t.title AS task_title, u.username AS admin_username, f.id AS feedback_id, f.feedback_category
            FROM feedback f
            LEFT JOIN tasks t ON f.task_id = t.id
            JOIN users u ON f.admin_id = u.id
            WHERE f.student_id = ? ORDER BY f.feedback_date DESC
        ''', (current_student_db_id,))
        feedback_records = cursor.fetchall()
    conn.close()
    return render_template('intern_feedback.html', username=session['username'], feedback_records=feedback_records)

@app.route('/student/send-feedback', methods=['GET', 'POST'])
def intern_send_feedback():
    if not is_intern_logged_in():
        return redirect(url_for('login'))
    
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    if request.method == 'POST':
        subject = request.form['subject']
        message = request.form['message']
        student_id = None
        
        cursor.execute("SELECT id FROM students WHERE user_id = ?", (session['user_id'],))
        student_id_row = cursor.fetchone()
        if student_id_row:
            student_id = student_id_row[0]
        
        if student_id:
            try:
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute("INSERT INTO student_feedback_to_admin (student_id, subject, message, timestamp) VALUES (?, ?, ?, ?)",
                               (student_id, subject, message, timestamp))
                conn.commit()
                flash('Your feedback has been sent to the admin successfully!', 'success')
                return redirect(url_for('intern_send_feedback'))
            except Exception as e:
                conn.rollback()
                flash(f'An error occurred while sending feedback: {e}', 'error')
        else:
            flash('Could not find your student profile. Please contact support.', 'error')
        conn.close()
        return redirect(url_for('intern_send_feedback'))

    conn.close()
    return render_template('intern_send_feedback.html', username=session['username'])


@app.route('/student/leave-permission')
def intern_leave_permission():
    if not is_intern_logged_in():
        return redirect(url_for('login'))
    # This route would typically handle displaying leave requests and a form to submit new ones.
    # For now, it's a placeholder.
    return render_template('intern_leave_permission.html', username=session['username'])

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)

