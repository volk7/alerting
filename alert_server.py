from fastapi import FastAPI, HTTPException
import threading
import psycopg2
import smtplib
import requests
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
from pydantic import BaseModel
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging
import queue
import time
import click
import random
from collections import defaultdict
from typing import Dict, List, Set, Optional

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database & Server Config
DB_HOST = "localhost"
DB_NAME = "alarms_db"
DB_USER = "admin"
DB_PASSWORD = "ZZ4charlie"
SMTP_SERVER = "smtp.mail.yahoo.com"
SMTP_PORT = 587
SMTP_USER = "kluge7@yahoo.com"
SMTP_PASSWORD = "kpjlmwqsslhbecpq!"
DESCRIPTION_API_URL = "http://localhost:5000/code-descriptions"

# Simulation Mode - Set to True to simulate emails instead of sending real ones
SIMULATION_MODE = True

# FastAPI App
app = FastAPI()

@click.group()
def cli():
    pass

@click.command()
def reset_db():
    """Drops and recreates the database tables."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        click.echo("Dropping existing 'alarms' table...")
        cursor.execute("DROP TABLE IF EXISTS alarms;")
        
        click.echo("Re-initializing database...")
        init_db()
        
        conn.commit()
        cursor.close()
        conn.close()
        
        click.echo("✅ Database reset successfully.")
    except Exception as e:
        click.echo(f"❌ Error resetting database: {e}")

@click.command()
def run_server():
    """Runs the Uvicorn server."""
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

@click.command()
def clear_jobs():
    """Clear all scheduled jobs from the scheduler."""
    try:
        job_count = len(time_wheel.get_all_jobs())
        time_wheel.clear_all_jobs()
        click.echo(f"✅ Cleared {job_count} scheduled jobs from the time wheel.")
    except Exception as e:
        click.echo(f"❌ Error clearing jobs: {e}")

cli.add_command(reset_db)
cli.add_command(run_server)
cli.add_command(clear_jobs)

# Email queue for batch processing
email_queue = queue.Queue(maxsize=10000)  # Larger queue for high load
email_worker_running = False

# Time Wheel Implementation
class TimeWheel:
    def __init__(self, wheel_size: int = 60, tick_interval: float = 1.0):
        """
        Initialize time wheel scheduler
        wheel_size: number of slots in the wheel (default 60 for seconds)
        tick_interval: time interval between ticks in seconds (default 1.0)
        """
        self.wheel_size = wheel_size
        self.tick_interval = tick_interval
        self.current_slot = 0
        self.wheel = defaultdict(list)  # slot -> list of jobs
        self.job_map = {}  # job_id -> (slot, job_data)
        self.running = False
        self.lock = threading.Lock()
        self.thread = None
        
    def start(self):
        """Start the time wheel scheduler"""
        if self.running:
            return
            
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        logger.info(f"Time wheel started with {self.wheel_size} slots, {self.tick_interval}s intervals")
        
    def stop(self):
        """Stop the time wheel scheduler"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        logger.info("Time wheel stopped")
        
    def _run(self):
        """Main time wheel loop"""
        while self.running:
            try:
                with self.lock:
                    # Process current slot
                    current_jobs = self.wheel[self.current_slot].copy()
                    self.wheel[self.current_slot].clear()
                    
                    # Execute jobs in current slot
                    for job_data in current_jobs:
                        job_id = job_data['job_id']
                        if job_id in self.job_map:
                            del self.job_map[job_id]
                            try:
                                # Execute job in thread pool to avoid blocking
                                job_executor.submit(self._execute_job, job_data)
                            except Exception as e:
                                logger.error(f"Error executing job {job_id}: {e}")
                    
                    # Move to next slot
                    self.current_slot = (self.current_slot + 1) % self.wheel_size
                    
                # Sleep for tick interval
                time.sleep(self.tick_interval)
                
            except Exception as e:
                logger.error(f"Time wheel error: {e}")
                time.sleep(self.tick_interval)
                
    def _execute_job(self, job_data: dict):
        """Execute a job"""
        try:
            job_id = job_data['job_id']
            func = job_data['func']
            args = job_data.get('args', [])
            kwargs = job_data.get('kwargs', {})
            
            logger.info(f"🔔 EXECUTING JOB: {job_id}")
            func(*args, **kwargs)
            logger.info(f"✅ JOB COMPLETED: {job_id}")
            
        except Exception as e:
            logger.error(f"Job execution error for {job_data.get('job_id', 'unknown')}: {e}")
            
    def add_job(self, job_id: str, func, args: list = None, kwargs: dict = None, 
                delay_seconds: int = None, target_time: datetime = None):
        """
        Add a job to the time wheel
        delay_seconds: delay in seconds from now
        target_time: specific datetime to execute
        """
        with self.lock:
            if job_id in self.job_map:
                # Remove existing job
                old_slot, _ = self.job_map[job_id]
                self.wheel[old_slot] = [j for j in self.wheel[old_slot] if j['job_id'] != job_id]
            
            # Calculate target slot
            if target_time:
                now = datetime.now()
                delay_seconds = int((target_time - now).total_seconds())
            elif delay_seconds is None:
                raise ValueError("Either delay_seconds or target_time must be provided")
                
            if delay_seconds < 0:
                delay_seconds = 0
                
            target_slot = (self.current_slot + delay_seconds) % self.wheel_size
            
            # Create job data
            job_data = {
                'job_id': job_id,
                'func': func,
                'args': args or [],
                'kwargs': kwargs or {}
            }
            
            # Add to wheel
            self.wheel[target_slot].append(job_data)
            self.job_map[job_id] = (target_slot, job_data)
            
            logger.info(f"Added job {job_id} to slot {target_slot} (delay: {delay_seconds}s)")
            
    def remove_job(self, job_id: str):
        """Remove a job from the time wheel"""
        with self.lock:
            if job_id in self.job_map:
                slot, _ = self.job_map[job_id]
                self.wheel[slot] = [j for j in self.wheel[slot] if j['job_id'] != job_id]
                del self.job_map[job_id]
                logger.info(f"Removed job {job_id}")
                return True
            return False
            
    def clear_all_jobs(self):
        """Clear all jobs from the time wheel"""
        with self.lock:
            self.wheel.clear()
            self.job_map.clear()
            logger.info("Cleared all jobs from time wheel")
            
    def get_all_jobs(self):
        """Get all job IDs"""
        with self.lock:
            return list(self.job_map.keys())
            
    def get_job_count(self):
        """Get total number of jobs"""
        with self.lock:
            return len(self.job_map)

# Initialize time wheel and job executor
time_wheel = TimeWheel(wheel_size=60, tick_interval=1.0)  # 60 slots, 1 second intervals
job_executor = ThreadPoolExecutor(max_workers=50, thread_name_prefix="AlarmWorker")

# Data Model
class AlarmRequest(BaseModel):
    code_id: str
    email: str
    time: str
    is_recurring: bool = False

# Database connection helper with connection pooling
def get_db_connection():
    conn = psycopg2.connect(
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        # Connection pooling settings
        keepalives=1,
        keepalives_idle=30,
        keepalives_interval=10,
        keepalives_count=5
    )
    return conn

# Initialize Database
def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS alarms (
            code_id TEXT,
            email TEXT,
            time TEXT,
            is_recurring BOOLEAN,
            PRIMARY KEY (code_id, email, time)
        )
    """)
    conn.commit()
    cursor.close()
    conn.close()

init_db()

# Function to get code description from Flask API with caching
_code_description_cache = {}
def get_code_description(code_id: str) -> str:
    # Simple in-memory cache to reduce API calls
    if code_id in _code_description_cache:
        return _code_description_cache[code_id]
    
    try:
        response = requests.get(f"{DESCRIPTION_API_URL}/{code_id}", timeout=5)
        if response.status_code == 200:
            description = response.json().get('description', "No description available")
            _code_description_cache[code_id] = description
            return description
        return "No description available"
    except requests.RequestException:
        return "Description service unavailable"

# Email worker for batch processing
def email_worker():
    """Background worker to process email queue"""
    global email_worker_running
    email_worker_running = True
    
    # Create SMTP connection pool for real email sending
    smtp_connections = queue.Queue(maxsize=5) if not SIMULATION_MODE else None
    
    while email_worker_running:
        try:
            # Get alarm from queue with timeout
            alarm_data = email_queue.get(timeout=1)
            if alarm_data is None:  # Shutdown signal
                break
                
            alarm, description = alarm_data
            
            if SIMULATION_MODE:
                # Simulate email sending
                try:
                    # Simulate email processing time (10-50ms)
                    time.sleep(random.uniform(0.01, 0.05))
                    
                    # Log the simulated email
                    logger.info(f"📧 SIMULATED EMAIL SENT to {alarm.email} at {alarm.time}")
                    logger.info(f"   Code ID: {alarm.code_id}")
                    logger.info(f"   Description: {description}")
                    
                    # Optional: Add some realistic simulation details
                    if random.random() < 0.01:  # 1% chance of "failure"
                        logger.warning(f"⚠️ SIMULATED EMAIL FAILED for {alarm.email} (network timeout)")
                    
                except Exception as e:
                    logger.error(f"⚠️ Simulated email error for {alarm.email}: {e}")
            else:
                # Real email sending
                try:
                    # Get or create SMTP connection
                    try:
                        smtp_conn = smtp_connections.get_nowait()
                    except queue.Empty:
                        smtp_conn = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
                        smtp_conn.starttls()
                        smtp_conn.login(SMTP_USER, SMTP_PASSWORD)
                    
                    # Send email
                    msg = MIMEMultipart()
                    msg["From"] = SMTP_USER
                    msg["To"] = alarm.email
                    msg["Subject"] = "⏰ Alarm Notification"
                    body = f"""Your alarm has triggered at {alarm.time}.
                    
Code ID: {alarm.code_id}
Description: {description}
"""
                    msg.attach(MIMEText(body, "plain"))
                    
                    smtp_conn.sendmail(SMTP_USER, alarm.email, msg.as_string())
                    logger.info(f"📧 Email sent to {alarm.email}")
                    
                    # Return connection to pool
                    smtp_connections.put(smtp_conn)
                    
                except Exception as e:
                    logger.error(f"⚠️ Email failed for {alarm.email}: {e}")
                    # Don't return failed connection to pool
                
        except queue.Empty:
            continue
        except Exception as e:
            logger.error(f"Email worker error: {e}")
    
    # Clean up SMTP connections if using real email
    if not SIMULATION_MODE and smtp_connections:
        while not smtp_connections.empty():
            try:
                smtp_connections.get().quit()
            except:
                pass
    
    logger.info("Email worker shutdown complete")

# Alarm trigger function
def trigger_alarm(alarm_data: dict):
    """Trigger a single alarm"""
    try:
        alarm = AlarmRequest(**alarm_data)
        description = get_code_description(alarm.code_id)
        
        # Add to email queue for batch processing
        try:
            email_queue.put((alarm, description), timeout=1)  # 1 second timeout
            logger.info(f"⏰ ALARM TRIGGERED: {alarm.time} for {alarm.email} 🔔🔔")
        except queue.Full:
            logger.warning(f"Email queue full, alarm {alarm.code_id} may be delayed")
            # Try to add with a longer timeout
            email_queue.put((alarm, description), timeout=5)
        
        # Remove non-recurring alarms
        if not alarm.is_recurring:
            time_wheel.add_job(
                job_id=f"remove_{alarm.code_id}_{alarm.email}_{alarm.time}",
                func=remove_alarm_job,
                args=[alarm.code_id, alarm.email, alarm.time],
                delay_seconds=1  # Remove after 1 second
            )
            
    except Exception as e:
        logger.error(f"Error triggering alarm {alarm_data.get('code_id', 'unknown')}: {e}")

# Database job for removing alarms
def remove_alarm_job(code_id: str, email: str, time: str):
    """Remove alarm from database"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM alarms WHERE code_id = %s AND email = %s AND time = %s", 
                      (code_id, email, time))
        conn.commit()
        cursor.close()
        conn.close()
        logger.info(f"Removed alarm: {code_id} {email} {time}")
    except Exception as e:
        logger.error(f"Error removing alarm: {e}")

# Helper to parse time string to hour, minute, second
def parse_time_to_hms(time_str):
    parts = time_str.split(':')
    if len(parts) == 3:
        hour, minute, second = parts
    elif len(parts) == 2:
        hour, minute = parts
        second = '0'
    else:
        raise ValueError("Invalid time format")
    return int(hour), int(minute), int(second)

# Helper to calculate seconds until target time
def calculate_seconds_until(target_time_str: str) -> int:
    """Calculate seconds until the target time today"""
    now = datetime.now()
    hour, minute, second = parse_time_to_hms(target_time_str)
    
    # Create target time for today
    target_time = now.replace(hour=hour, minute=minute, second=second, microsecond=0)
    
    # If target time has passed today, it's for tomorrow
    if target_time <= now:
        target_time += timedelta(days=1)
    
    return int((target_time - now).total_seconds())

# Add Alarm
@app.post("/alarms/")
def add_alarm(alarm: AlarmRequest):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO alarms (code_id, email, time, is_recurring) VALUES (%s, %s, %s, %s)",
                       (alarm.code_id, alarm.email, alarm.time, alarm.is_recurring))
        conn.commit()
        cursor.close()
        conn.close()
        
        # Schedule the alarm using time wheel
        try:
            delay_seconds = calculate_seconds_until(alarm.time)
            job_id = f"alarm_{alarm.code_id}_{alarm.email}_{alarm.time}"
            
            time_wheel.add_job(
                job_id=job_id,
                func=trigger_alarm,
                args=[alarm.dict()],
                delay_seconds=delay_seconds
            )
            logger.info(f"Scheduled alarm: {job_id} in {delay_seconds} seconds")
        except Exception as e:
            logger.error(f"Error scheduling alarm: {e}")
        
        return {"status": "success", "message": "Alarm added"}
    except psycopg2.IntegrityError:
        cursor.close()
        conn.close()
        raise HTTPException(status_code=400, detail="Alarm already exists")

# Remove Alarm
@app.delete("/alarms/")
def remove_alarm(code_id: str, email: str, time: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM alarms WHERE code_id = %s AND email = %s AND time = %s", (code_id, email, time))
    conn.commit()
    cursor.close()
    conn.close()
    
    # Remove from time wheel
    job_id = f"alarm_{code_id}_{email}_{time}"
    try:
        time_wheel.remove_job(job_id)
        logger.info(f"Removed scheduled alarm: {job_id}")
    except:
        pass
    
    return {"status": "success", "message": "Alarm removed"} if cursor.rowcount else {"status": "error", "message": "Alarm not found"}

# Get All Alarms with Pagination
@app.get("/alarms/")
def list_alarms(limit: int = 20, offset: int = 0):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT code_id, email, time, is_recurring FROM alarms ORDER BY code_id, email, time LIMIT %s OFFSET %s", (limit, offset))
    alarms = cursor.fetchall()
    cursor.close()
    conn.close()
    return [{"code_id": row[0], "email": row[1], "time": row[2], "is_recurring": row[3]} for row in alarms]

# Count Alarms
@app.get("/alarms/count")
def count_alarms():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM alarms")
    count = cursor.fetchone()[0]
    cursor.close()
    conn.close()
    return {"count": count}

# Load existing alarms on startup
def load_existing_alarms():
    """Load all existing alarms from database into time wheel"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT code_id, email, time, is_recurring FROM alarms")
    alarms = cursor.fetchall()
    cursor.close()
    conn.close()
    
    loaded_count = 0
    for row in alarms:
        code_id, email, time, is_recurring = row
        alarm_data = {
            "code_id": code_id,
            "email": email,
            "time": time,
            "is_recurring": is_recurring
        }
        
        try:
            delay_seconds = calculate_seconds_until(time)
            job_id = f"alarm_{code_id}_{email}_{time}"
            
            time_wheel.add_job(
                job_id=job_id,
                func=trigger_alarm,
                args=[alarm_data],
                delay_seconds=delay_seconds
            )
            loaded_count += 1
        except Exception as e:
            logger.error(f"Error scheduling alarm: {e}")
    
    logger.info(f"Loaded {loaded_count} existing alarms into time wheel")

# Startup and shutdown events
@app.on_event("startup")
async def startup_event():
    """Initialize time wheel and email worker on startup"""
    time_wheel.start()
    load_existing_alarms()
    
    # Start email worker thread
    email_thread = threading.Thread(target=email_worker, daemon=True)
    email_thread.start()
    
    logger.info("Alarm server started successfully with time wheel scheduler")
    logger.info(f"Time wheel: {time_wheel.wheel_size} slots, {time_wheel.tick_interval}s intervals")
    logger.info(f"Email queue size: {email_queue.maxsize}")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    global email_worker_running
    email_worker_running = False
    
    # Signal email worker to stop
    email_queue.put(None)
    
    # Shutdown time wheel
    time_wheel.stop()
    
    # Shutdown job executor
    job_executor.shutdown(wait=True)
    
    logger.info("Alarm server shutdown complete")

# Debug endpoint to list all scheduled jobs
@app.get("/debug/jobs")
def list_scheduled_jobs():
    """List all scheduled jobs for debugging"""
    jobs = time_wheel.get_all_jobs()
    return {
        "total_jobs": len(jobs), 
        "jobs": jobs,
        "time_wheel_info": {
            "current_slot": time_wheel.current_slot,
            "wheel_size": time_wheel.wheel_size,
            "tick_interval": time_wheel.tick_interval,
            "running": time_wheel.running
        }
    }

if __name__ == "__main__":
    cli()
