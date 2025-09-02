from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import requests
import psycopg2
from psycopg2.extras import RealDictCursor
import math
from datetime import datetime, timedelta
import time

app = Flask(__name__)
app.secret_key = "supersecretkey"  # For flash messages
BASE_URL = "http://127.0.0.1:8000/alarms/"
SCHEDULER_URL = "http://localhost:8002"  # Direct scheduler service URL

# Database configuration - Using PostgreSQL to match microservices
DB_HOST = "localhost"
DB_NAME = "alarms_db"  # Match the microservices database name
DB_USER = "admin"
DB_PASSWORD = "ZZ4charlie"

# Pagination settings
ALARMS_PER_PAGE = 20

# Database connection helper
def get_db_connection():
    conn = psycopg2.connect(
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST
    )
    return conn

# Initialize Database with code descriptions table
def init_db():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS code_descriptions (
                code_id TEXT PRIMARY KEY,
                description TEXT NOT NULL
            )
        """)
        conn.commit()
        cursor.close()
        conn.close()
        print("✅ Database initialized successfully")
    except psycopg2.OperationalError as e:
        print(f"❌ Database connection failed: {e}")
        print("Please ensure PostgreSQL is running and the 'alarms_db' database exists.")
        print("You can start the microservices with: cd microservices && docker-compose up -d")
    except Exception as e:
        print(f"❌ Database initialization error: {e}")

# Initialize database on startup
init_db()

# Home Page - List Alarms with Pagination
@app.route("/")
@app.route("/page/<int:page>")
def index(page=1):
    # Get per_page parameter from query string
    per_page = request.args.get('per_page', ALARMS_PER_PAGE, type=int)
    if per_page not in [10, 20, 50, 100]:
        per_page = ALARMS_PER_PAGE
    
    # Validate page number
    if page < 1:
        page = 1
    
    # Get alarms from scheduler service
    try:
        response = requests.get(f"{SCHEDULER_URL}/jobs/")
        if response.status_code == 200:
            scheduler_data = response.json()
            all_alarms = scheduler_data.get('jobs', [])
            total_alarms = len(all_alarms)
            
            # Apply pagination
            start_idx = (page - 1) * per_page
            end_idx = start_idx + per_page
            alarms = all_alarms[start_idx:end_idx]
        else:
            alarms = []
            total_alarms = 0
    except Exception as e:
        print(f"Error getting alarms from scheduler: {e}")
        alarms = []
        total_alarms = 0
    
    # Calculate pagination
    total_pages = math.ceil(total_alarms / per_page)
    if page > total_pages and total_pages > 0:
        page = total_pages
    
    # Debug logging
    start_idx = (page - 1) * per_page
    print(f"DEBUG: per_page={per_page}, page={page}, start_idx={start_idx}, total_alarms={total_alarms}, alarms_returned={len(alarms)}")
    
    # Pagination info
    pagination = {
        'page': page,
        'per_page': per_page,
        'total': total_alarms,
        'pages': total_pages,
        'has_prev': page > 1,
        'has_next': page < total_pages,
        'prev_page': page - 1 if page > 1 else None,
        'next_page': page + 1 if page < total_pages else None,
        'start_item': start_idx + 1 if total_alarms > 0 else 0,
        'end_item': min(start_idx + per_page, total_alarms)
    }
    
    return render_template("index.html", alarms=alarms, pagination=pagination)

# Add Alarm
@app.route("/add", methods=["GET", "POST"])
def add_alarm():
    if request.method == "POST":
        try:
            # Generate unique ID if not provided
            code_id = request.form.get('code_id', '').strip()
            if not code_id:
                import time
                import random
                timestamp = int(time.time())
                random_suffix = ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=6))
                code_id = f"ALARM_{timestamp}_{random_suffix}"
            
            alarm_data = {
                "code_id": code_id,
                "email": request.form['email'],
                "time": request.form['time'],
                "is_recurring": 'is_recurring' in request.form
            }
            
            # Add test alarm flag if present
            if 'is_test_alarm' in request.form:
                alarm_data["code_id"] = f"TEST_{alarm_data['code_id']}"
            
            # Debug: Print the alarm data being sent
            print(f"DEBUG: Sending alarm data to scheduler: {alarm_data}")
            
            # Check if scheduler service is running
            try:
                health_response = requests.get(f"{SCHEDULER_URL}/health", timeout=5)
                if health_response.status_code != 200:
                    flash(f"Scheduler service is not responding. Status: {health_response.status_code}", "danger")
                    return redirect(url_for("add_alarm"))
            except requests.exceptions.RequestException as e:
                flash(f"Cannot connect to scheduler service: {str(e)}", "danger")
                return redirect(url_for("add_alarm"))
            
            # Use scheduler service directly like performance_dashboard.py
            response = requests.post(f"{SCHEDULER_URL}/schedule/", json=alarm_data)

            if response.status_code == 200:
                result = response.json()
                flash(f"Alarm added successfully! ID: {result.get('alarm_id', 'Unknown')}", "success")
            else:
                error_detail = response.text if response.text else f"HTTP {response.status_code}"
                flash(f"Failed to add alarm: {error_detail}", "danger")

            return redirect(url_for("index"))
        except Exception as e:
            flash(f"Error adding alarm: {str(e)}", "danger")
            return redirect(url_for("add_alarm"))

    return render_template("add_alarm.html")

@app.route('/test_alarm', methods=['POST'])
def test_alarm():
    """Create a test alarm for current time"""
    try:
        current_time = datetime.now()
        test_time = f"{current_time.hour:02d}:{current_time.minute:02d}:{current_time.second:02d}"
        
        alarm_data = {
            "code_id": f"TEST_{int(time.time())}",
            "email": "test@example.com",
            "time": test_time,
            "is_recurring": False
        }
        
        response = requests.post(f"{SCHEDULER_URL}/schedule/", json=alarm_data)
        if response.status_code == 200:
            flash("Test alarm created successfully!", "success")
        else:
            flash("Failed to create test alarm.", "danger")
    except Exception as e:
        flash(f"Error creating test alarm: {str(e)}", "danger")
    
    return redirect(url_for("index"))

@app.route('/bulk_alarms', methods=['POST'])
def bulk_alarms():
    """Create multiple test alarms for performance testing"""
    try:
        count = request.form.get('count', 10, type=int)
        time_offset = request.form.get('time_offset', 2, type=int)  # minutes from now
        
        created_count = 0
        failed_count = 0
        
        for i in range(count):
            try:
                # Create alarm for future time
                future_time = datetime.now() + timedelta(minutes=time_offset + i)
                test_time = f"{future_time.hour:02d}:{future_time.minute:02d}:{future_time.second:02d}"
                
                alarm_data = {
                    "code_id": f"BULK_TEST_{int(time.time())}_{i}",
                    "email": f"bulk_test_{i}@example.com",
                    "time": test_time,
                    "is_recurring": False
                }
                
                response = requests.post(f"{SCHEDULER_URL}/schedule/", json=alarm_data)
                if response.status_code == 200:
                    created_count += 1
                else:
                    failed_count += 1
                    
            except Exception as e:
                failed_count += 1
        
        flash(f"Created {created_count} alarms, {failed_count} failed", "success" if created_count > 0 else "warning")
        
    except Exception as e:
        flash(f"Error creating bulk alarms: {str(e)}", "danger")
    
    return redirect(url_for("index"))

@app.route('/clear_alarms', methods=['POST'])
def clear_alarms():
    """Clear all alarms"""
    try:
        # Use scheduler service directly like performance_dashboard.py
        response = requests.delete(f"{SCHEDULER_URL}/jobs/clear")
        if response.status_code == 200:
            flash("Alarms cleared successfully!", "success")
        else:
            flash("Failed to clear alarms", "danger")
    except Exception as e:
        flash(f"Error clearing alarms: {str(e)}", "danger")
    
    return redirect(url_for("index"))

@app.route('/reload_alarms', methods=['POST'])
def reload_alarms():
    """Reload alarms from database"""
    try:
        response = requests.post(f"{SCHEDULER_URL}/reload")
        if response.status_code == 200:
            flash("Alarms reloaded successfully!", "success")
        else:
            flash("Failed to reload alarms", "danger")
    except Exception as e:
        flash(f"Error reloading alarms: {str(e)}", "danger")
    
    return redirect(url_for("index"))

# Remove Alarm
@app.route("/delete/<code_id>/<email>/<time>")
def delete_alarm(code_id, email, time):
    try:
        # Use scheduler service to delete alarm
        response = requests.delete(f"{SCHEDULER_URL}/unschedule/", params={
            "code_id": code_id,
            "email": email,
            "time": time
        })

        if response.status_code == 200:
            flash("Alarm deleted successfully!", "success")
        else:
            flash("Failed to delete alarm.", "danger")
    except Exception as e:
        flash(f"Error deleting alarm: {str(e)}", "danger")

    # Redirect back to the same page with preserved parameters
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', ALARMS_PER_PAGE, type=int)
    return redirect(url_for("index", page=page, per_page=per_page))

# Code Description Management Routes

@app.route("/codes")
def code_index():
    """Display all code descriptions"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT code_id, description FROM code_descriptions ORDER BY code_id")
    codes = [{"code_id": row[0], "description": row[1]} for row in cursor.fetchall()]
    cursor.close()
    conn.close()
    return render_template("code_index.html", codes=codes)

@app.route("/codes/add", methods=["POST"])
def add_code():
    """Add a new code description"""
    code_id = request.form["code_id"]
    description = request.form["description"]
    
    if not code_id or not description:
        flash("Code ID and description are required.", "danger")
        return redirect(url_for("code_index"))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO code_descriptions (code_id, description) VALUES (%s, %s)",
                       (code_id, description))
        conn.commit()
        flash("Code description added successfully!", "success")
    except psycopg2.IntegrityError:
        flash("Code ID already exists.", "danger")
    except Exception as e:
        flash(f"Error adding code description: {str(e)}", "danger")
    finally:
        cursor.close()
        conn.close()
    
    return redirect(url_for("code_index"))

@app.route("/codes/edit/<code_id>")
def edit_code(code_id):
    """Edit code description form"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT code_id, description FROM code_descriptions WHERE code_id = %s", (code_id,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    
    if not row:
        flash("Code not found.", "danger")
        return redirect(url_for("code_index"))
    
    code = {"code_id": row[0], "description": row[1]}
    return render_template("code_edit.html", code=code)

@app.route("/codes/update/<code_id>", methods=["POST"])
def update_code(code_id):
    """Update code description"""
    description = request.form["description"]
    
    if not description:
        flash("Description is required.", "danger")
        return redirect(url_for("edit_code", code_id=code_id))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE code_descriptions SET description = %s WHERE code_id = %s",
                       (description, code_id))
        conn.commit()
        if cursor.rowcount > 0:
            flash("Code description updated successfully!", "success")
        else:
            flash("Code not found.", "danger")
    except Exception as e:
        flash(f"Error updating code description: {str(e)}", "danger")
    finally:
        cursor.close()
        conn.close()
    
    return redirect(url_for("code_index"))

@app.route("/codes/delete/<code_id>")
def delete_code(code_id):
    """Delete code description"""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM code_descriptions WHERE code_id = %s", (code_id,))
        conn.commit()
        if cursor.rowcount > 0:
            flash("Code description deleted successfully!", "success")
        else:
            flash("Code not found.", "danger")
    except Exception as e:
        flash(f"Error deleting code description: {str(e)}", "danger")
    finally:
        cursor.close()
        conn.close()
    
    return redirect(url_for("code_index"))

# API endpoint for FastAPI server to get code descriptions
@app.route("/code-descriptions/<code_id>")
def get_code_description(code_id):
    """API endpoint to get code description by code_id"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT description FROM code_descriptions WHERE code_id = %s", (code_id,))
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    
    if result:
        return jsonify({"description": result[0]})
    else:
        return jsonify({"description": "No description available"}), 404

if __name__ == "__main__":
    app.run(debug=True)
