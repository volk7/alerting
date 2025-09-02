from fastapi import FastAPI, HTTPException
import psycopg2
import psycopg2.pool
import os
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Set
import uuid
import threading
import time
from collections import defaultdict
from shared.models import AlarmRequest, AlarmEvent, convert_local_time_to_utc, convert_utc_time_to_local
from shared.redis_client import RedisClient
import pytz

# Configure logging
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

app = FastAPI(title="Scalable Alarm Scheduler Service", version="2.0.0")

# Configuration
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://admin:ZZ4charlie@localhost:5432/alarms_db")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
MAX_CONNECTIONS = int(os.getenv("MAX_DB_CONNECTIONS", "20"))
MIN_CONNECTIONS = int(os.getenv("MIN_DB_CONNECTIONS", "5"))
DEFAULT_TIMEZONE = os.getenv("TIMEZONE", "America/Los_Angeles")

# Timezone configuration - always use UTC for scheduling
SCHEDULER_TZ = pytz.UTC
logger.info(f"✅ Scheduler using UTC timezone for all operations")

# Initialize Redis client
redis_client = RedisClient()

# Database connection pool
connection_pool = None

# Scalable alarm storage with time-based indexing (using UTC times)
class TimeIndexedAlarmScheduler:
    def __init__(self):
        # Time-based index: {hour: {minute: {second: Set[alarm_id]}}} (UTC times)
        self.time_index = defaultdict(lambda: defaultdict(lambda: defaultdict(set)))
        
        # Alarm data storage: {alarm_id: alarm_data}
        self.alarms = {}
        
        # Statistics
        self.total_alarms = 0
        self.last_cleanup = time.time()
        
        # Thread safety
        self.lock = threading.RLock()
        
        logger.info("🔄 Initialized TimeIndexedAlarmScheduler with UTC timezone")
    
    def add_alarm(self, alarm_id: str, alarm_data: dict) -> bool:
        """Add alarm with O(1) time complexity using UTC times"""
        try:
            with self.lock:
                # Use UTC time for scheduling
                utc_time = alarm_data.get('utc_time')
                if not utc_time:
                    # Convert local time to UTC if not already converted
                    utc_time = convert_local_time_to_utc(alarm_data['time'], alarm_data.get('timezone', 'America/Los_Angeles'))
                    alarm_data['utc_time'] = utc_time
                
                # Parse UTC time
                hour, minute, second = self._parse_time_to_hms(utc_time)
                
                # Add to time index using UTC time
                self.time_index[hour][minute][second].add(alarm_id)
                
                # Store alarm data (ensure all fields are present)
                if 'days_of_week' not in alarm_data:
                    alarm_data['days_of_week'] = 'Mon,Tue,Wed,Thu,Fri,Sat,Sun'
                if 'timezone' not in alarm_data:
                    alarm_data['timezone'] = 'America/Los_Angeles'
                
                self.alarms[alarm_id] = alarm_data
                self.total_alarms += 1
                
                logger.debug(f"📅 Added alarm {alarm_id} to UTC time index [{hour}:{minute}:{second}] (local: {alarm_data['time']})")
                return True
                
        except Exception as e:
            logger.error(f"Error adding alarm {alarm_id}: {e}")
            return False
    
    def remove_alarm(self, alarm_id: str) -> bool:
        """Remove alarm with O(1) time complexity"""
        try:
            with self.lock:
                if alarm_id not in self.alarms:
                    return False
                
                alarm_data = self.alarms[alarm_id]
                utc_time = alarm_data.get('utc_time', alarm_data['time'])  # Fallback to original time
                hour, minute, second = self._parse_time_to_hms(utc_time)
                
                # Remove from time index
                self.time_index[hour][minute][second].discard(alarm_id)
                
                # Clean up empty time slots
                if not self.time_index[hour][minute][second]:
                    del self.time_index[hour][minute][second]
                if not self.time_index[hour][minute]:
                    del self.time_index[hour][minute]
                if not self.time_index[hour]:
                    del self.time_index[hour]
                
                # Remove alarm data
                del self.alarms[alarm_id]
                self.total_alarms -= 1
                
                logger.debug(f"🗑️ Removed alarm {alarm_id} from UTC time index")
                return True
                
        except Exception as e:
            logger.error(f"Error removing alarm {alarm_id}: {e}")
            return False
    
    def get_due_alarms(self, current_time: datetime) -> List[tuple]:
        """Get alarms due at current time using UTC comparison"""
        try:
            with self.lock:
                due_alarms = []
                # Ensure current_time is in UTC
                if current_time.tzinfo is None:
                    current_time = pytz.UTC.localize(current_time)
                elif current_time.tzinfo != pytz.UTC:
                    current_time = current_time.astimezone(pytz.UTC)
                
                for hour in self.time_index:
                    for minute in self.time_index[hour]:
                        for second in self.time_index[hour][minute]:
                            for alarm_id in self.time_index[hour][minute][second]:
                                alarm = self.alarms[alarm_id]
                                
                                # Check if UTC time matches
                                if (current_time.hour == hour and current_time.minute == minute and current_time.second == second):
                                    # Check if today is in days_of_week (using alarm's timezone)
                                    alarm_tz = pytz.timezone(alarm.get('timezone', 'America/Los_Angeles'))
                                    now_in_alarm_tz = current_time.astimezone(alarm_tz)
                                    days = [d.strip() for d in alarm.get('days_of_week', 'Mon,Tue,Wed,Thu,Fri,Sat,Sun').split(',')]
                                    weekday = now_in_alarm_tz.strftime('%a')
                                    
                                    if weekday in days:
                                        due_alarms.append((alarm_id, alarm))
                
                return due_alarms
        except Exception as e:
            logger.error(f"Error getting due alarms: {e}")
            return []
    
    def get_alarm_count(self) -> int:
        """Get total number of alarms"""
        return self.total_alarms
    
    def get_time_index_stats(self) -> dict:
        """Get statistics about time index distribution"""
        try:
            with self.lock:
                stats = {
                    "total_alarms": self.total_alarms,
                    "hours_with_alarms": len(self.time_index),
                    "total_time_slots": 0,
                    "alarms_per_hour": {},
                    "timezone": "UTC"
                }
                
                for hour in self.time_index:
                    hour_count = 0
                    for minute in self.time_index[hour]:
                        for second in self.time_index[hour][minute]:
                            hour_count += len(self.time_index[hour][minute][second])
                            stats["total_time_slots"] += 1
                    stats["alarms_per_hour"][hour] = hour_count
                
                return stats
                
        except Exception as e:
            logger.error(f"Error getting time index stats: {e}")
            return {}
    
    def cleanup_expired_alarms(self):
        """Clean up expired non-recurring alarms using UTC time"""
        try:
            with self.lock:
                current_time = datetime.now(pytz.UTC)
                expired_alarms = []
                
                for alarm_id, alarm_data in list(self.alarms.items()):
                    if not alarm_data['is_recurring']:
                        # Check if alarm time has passed using UTC
                        utc_time = alarm_data.get('utc_time', alarm_data['time'])
                        alarm_hour, alarm_minute, alarm_second = self._parse_time_to_hms(utc_time)
                        alarm_time_today = current_time.replace(
                            hour=alarm_hour, 
                            minute=alarm_minute, 
                            second=alarm_second, 
                            microsecond=0
                        )
                        
                        # If alarm time has passed by more than 1 hour, remove it
                        if current_time > alarm_time_today + timedelta(hours=1):
                            expired_alarms.append(alarm_id)
                
                # Remove expired alarms
                for alarm_id in expired_alarms:
                    self.remove_alarm(alarm_id)
                
                if expired_alarms:
                    logger.info(f"🧹 Cleaned up {len(expired_alarms)} expired alarms")
                    
        except Exception as e:
            logger.error(f"Error cleaning up expired alarms: {e}")
    
    def _parse_time_to_hms(self, time_str: str) -> tuple:
        """Parse time string to hour, minute, second"""
        parts = time_str.split(':')
        if len(parts) == 3:
            hour, minute, second = parts
        elif len(parts) == 2:
            hour, minute = parts
            second = '0'
        else:
            raise ValueError("Invalid time format")
        return int(hour), int(minute), int(second)

# Initialize scalable scheduler
scheduler = TimeIndexedAlarmScheduler()

# Background thread management
alarm_thread = None
stop_thread = False

def trigger_alarm(alarm_data: dict):
    """Trigger an alarm by publishing an event"""
    logger.info(f"🔔 TRIGGER_ALARM FUNCTION CALLED with data: {alarm_data}")
    try:
        # Create unique alarm ID
        alarm_id = str(uuid.uuid4())
        
        # Create alarm event with timezone info
        event = AlarmEvent(
            alarm_id=alarm_id,
            code_id=alarm_data['code_id'],
            email=alarm_data['email'],
            time=alarm_data['time'],  # Original user time
            utc_time=alarm_data.get('utc_time', alarm_data['time']),  # UTC time
            triggered_at=datetime.utcnow(),
            is_recurring=alarm_data['is_recurring'],
            timezone=alarm_data.get('timezone', 'America/Los_Angeles')
        )
        
        # Publish event to Redis
        success = redis_client.publish_alarm_event(event)
        
        if success:
            logger.info(f"⏰ ALARM TRIGGERED: {alarm_data['time']} ({alarm_data.get('timezone', 'America/Los_Angeles')}) for {alarm_data['email']} 🔔🔔")
            logger.info(f"   Code ID: {alarm_data['code_id']}")
            logger.info(f"   Event ID: {alarm_id}")
            logger.info(f"   UTC Time: {alarm_data.get('utc_time', 'N/A')}")
        else:
            logger.error(f"Failed to publish alarm event for {alarm_data['code_id']}")
            
    except Exception as e:
        logger.error(f"Error triggering alarm {alarm_data.get('code_id', 'unknown')}: {e}")

def scalable_alarm_checker():
    """Scalable background thread that checks for alarms to trigger using UTC time"""
    global stop_thread
    logger.warning("🚀 Scalable alarm checker thread started")
    logger.warning(f"⏰ Using UTC timezone for all scheduling operations")
    
    tick_count = 0
    last_log_time = time.time()
    last_cleanup_time = time.time()
    
    while not stop_thread:
        try:
            current_time = datetime.now(pytz.UTC)
            current_log_time = time.time()
            tick_count += 1
            
            # Log every 300 ticks (every 5 minutes) to reduce log noise
            if tick_count % 300 == 0:
                elapsed = current_log_time - last_log_time
                alarm_count = scheduler.get_alarm_count()
                logger.info(f"⏰ Tick #{tick_count}, current UTC time: {current_time.strftime('%H:%M:%S')}, alarms: {alarm_count}, elapsed: {elapsed:.1f}s")
                last_log_time = current_log_time
                
                # Show time index stats every 15 minutes
                if tick_count % 900 == 0:
                    stats = scheduler.get_time_index_stats()
                    logger.info(f"📊 Time index stats: {stats}")
            
            # Cleanup expired alarms every 10 minutes
            if current_log_time - last_cleanup_time > 600:
                scheduler.cleanup_expired_alarms()
                last_cleanup_time = current_log_time
            
            # Get due alarms with O(1) lookup using UTC time
            start_check = time.time()
            due_alarms = scheduler.get_due_alarms(current_time)
            check_duration = time.time() - start_check
            
            # Trigger alarms
            if due_alarms:
                logger.warning(f"🚨 FOUND {len(due_alarms)} ALARMS TO TRIGGER!")
                
            for alarm_id, alarm_data in due_alarms:
                logger.warning(f"🔔 TRIGGERING ALARM: {alarm_id}")
                trigger_alarm(alarm_data)
                
                # Remove non-recurring alarms
                if not alarm_data['is_recurring']:
                    scheduler.remove_alarm(alarm_id)
                    logger.warning(f"🗑️ Removed non-recurring alarm: {alarm_id}")
            
            # Debug: Log every 60 seconds to show the thread is running
            if tick_count % 60 == 0:
                logger.info(f"🔍 DEBUG: Thread running, current UTC: {current_time.strftime('%H:%M:%S')}, alarms: {scheduler.get_alarm_count()}")
                # Show what's in the time index for current time
                current_hour = current_time.hour
                current_minute = current_time.minute
                current_second = current_time.second
                
                if (current_hour in scheduler.time_index and 
                    current_minute in scheduler.time_index[current_hour] and 
                    current_second in scheduler.time_index[current_hour][current_minute]):
                    alarms_at_current_time = scheduler.time_index[current_hour][current_minute][current_second]
                    logger.info(f"🔍 DEBUG: Found {len(alarms_at_current_time)} alarms at current time {current_hour}:{current_minute}:{current_second}")
                    for alarm_id in alarms_at_current_time:
                        alarm_data = scheduler.alarms.get(alarm_id, {})
                        logger.info(f"🔍 DEBUG: Alarm {alarm_id} - {alarm_data.get('time', 'N/A')} ({alarm_data.get('timezone', 'N/A')})")
                else:
                    logger.info(f"🔍 DEBUG: No alarms scheduled for current time {current_hour}:{current_minute}:{current_second}")
            
            # Performance monitoring - log if check takes too long
            if check_duration > 0.01:  # More than 10ms
                logger.warning(f"⚠️ Slow alarm check: {check_duration:.3f}s for {scheduler.get_alarm_count()} alarms")
            
            # Sleep for 1 second
            time.sleep(1)
            
        except Exception as e:
            logger.error(f"Error in scalable alarm checker: {e}")
            time.sleep(1)
    
    logger.info("🛑 Scalable alarm checker thread stopped")

def load_existing_alarms():
    """Load all existing alarms from database using connection pool, including UTC time conversion"""
    global connection_pool
    try:
        conn = connection_pool.getconn()
        cursor = conn.cursor()
        
        # Check if utc_time column exists, if not use the old schema
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'alarms' AND column_name = 'utc_time'
        """)
        has_utc_column = cursor.fetchone() is not None
        
        if has_utc_column:
            cursor.execute("SELECT code_id, email, time, utc_time, is_recurring, days_of_week, timezone FROM alarms")
            db_alarms = cursor.fetchall()
        else:
            # Fallback to old schema - convert times to UTC
            cursor.execute("SELECT code_id, email, time, is_recurring, days_of_week, timezone FROM alarms")
            db_alarms = cursor.fetchall()
        
        cursor.close()
        connection_pool.putconn(conn)
        
        loaded_count = 0
        for row in db_alarms:
            if has_utc_column:
                code_id, email, time, utc_time, is_recurring, days_of_week, timezone = row
            else:
                code_id, email, time, is_recurring, days_of_week, timezone = row
                # Convert local time to UTC for old schema
                try:
                    utc_time = convert_local_time_to_utc(time, timezone or 'America/Los_Angeles')
                except Exception as e:
                    logger.warning(f"Failed to convert time {time} to UTC for {code_id}: {e}")
                    continue
            
            alarm_data = {
                "code_id": code_id,
                "email": email,
                "time": time,
                "utc_time": utc_time,
                "is_recurring": is_recurring,
                "days_of_week": days_of_week or 'Mon,Tue,Wed,Thu,Fri,Sat,Sun',
                "timezone": timezone or 'America/Los_Angeles'
            }
            alarm_id = f"alarm_{code_id}_{email}_{time}"
            if scheduler.add_alarm(alarm_id, alarm_data):
                loaded_count += 1
                logger.debug(f"📥 Loaded alarm: {alarm_id} (UTC: {utc_time})")
        
        logger.warning(f"📊 Loaded {loaded_count} existing alarms into UTC-aware scheduler")
    except Exception as e:
        logger.error(f"Error loading existing alarms: {e}")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Test database connection pool
        conn = connection_pool.getconn()
        conn.close()
        connection_pool.putconn(conn)
        
        # Test Redis connection
        redis_client.redis.ping()
        
        # Get scheduler stats
        stats = scheduler.get_time_index_stats()
        
        return {
            "status": "healthy", 
            "service": "scalable-alarm-scheduler",
            "database": "connected",
            "redis": "connected",
            "scheduled_alarms": scheduler.get_alarm_count(),
            "thread_running": alarm_thread and alarm_thread.is_alive(),
            "timezone": "UTC",
            "scheduler_stats": stats
        }
    except Exception as e:
        return {"status": "unhealthy", "service": "scalable-alarm-scheduler", "error": str(e)}

@app.post("/schedule/")
async def schedule_alarm(alarm: AlarmRequest):
    """Schedule a new alarm with UTC time conversion"""
    try:
        alarm_id = f"alarm_{alarm.code_id}_{alarm.email}_{alarm.time}"
        
        # Convert local time to UTC
        utc_time = convert_local_time_to_utc(alarm.time, alarm.timezone)
        
        alarm_data = {
            "code_id": alarm.code_id,
            "email": alarm.email,
            "time": alarm.time,  # Original user time
            "utc_time": utc_time,  # UTC time for scheduling
            "is_recurring": alarm.is_recurring,
            "days_of_week": alarm.days_of_week,
            "timezone": alarm.timezone
        }
        
        # Add to scalable scheduler
        success = scheduler.add_alarm(alarm_id, alarm_data)
        if success:
            # Only log every 10th alarm to reduce log noise
            current_count = scheduler.get_alarm_count()
            if current_count % 10 == 0 or current_count <= 5:
                logger.warning(f"📅 Added alarm #{current_count}: {alarm_id} (UTC: {utc_time})")
            return {
                "status": "success", 
                "message": "Alarm scheduled", 
                "alarm_id": alarm_id,
                "total_alarms": scheduler.get_alarm_count(),
                "user_time": alarm.time,
                "utc_time": utc_time,
                "timezone": alarm.timezone,
                "days_of_week": alarm.days_of_week
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to schedule alarm")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid time format: {str(e)}")
    except Exception as e:
        logger.error(f"Error scheduling alarm: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.delete("/unschedule/")
async def unschedule_alarm(code_id: str, email: str, time: str):
    """Unschedule an alarm"""
    try:
        alarm_id = f"alarm_{code_id}_{email}_{time}"
        
        success = scheduler.remove_alarm(alarm_id)
        
        if success:
            logger.warning(f"🗑️ Unscheduled alarm: {alarm_id}")
            return {
                "status": "success", 
                "message": "Alarm unscheduled",
                "total_alarms": scheduler.get_alarm_count()
            }
        else:
            return {"status": "success", "message": "Alarm not found"}
            
    except Exception as e:
        logger.error(f"Error unscheduling alarm: {e}")
        raise HTTPException(status_code=500, detail=f"Scheduler error: {str(e)}")

@app.get("/jobs/")
async def list_scheduled_jobs():
    """List all scheduled alarms"""
    try:
        alarm_list = []
        with scheduler.lock:
            for alarm_id, alarm_data in scheduler.alarms.items():
                alarm_list.append({
                    "id": alarm_id,
                    "time": alarm_data['time'],
                    "code_id": alarm_data['code_id'],
                    "email": alarm_data['email'],
                    "is_recurring": alarm_data['is_recurring'],
                    "days_of_week": alarm_data.get('days_of_week', 'Mon,Tue,Wed,Thu,Fri,Sat,Sun'),
                    "timezone": alarm_data.get('timezone', 'America/Los_Angeles')
                })
        return {
            "total_jobs": scheduler.get_alarm_count(),
            "jobs": alarm_list,
            "scheduler_stats": scheduler.get_time_index_stats()
        }
    except Exception as e:
        logger.error(f"Error listing alarms: {e}")
        raise HTTPException(status_code=500, detail=f"Scheduler error: {str(e)}")

@app.delete("/jobs/clear")
async def clear_all_jobs():
    """Clear all scheduled alarms"""
    try:
        with scheduler.lock:
            alarm_count = scheduler.get_alarm_count()
            scheduler.time_index.clear()
            scheduler.alarms.clear()
            scheduler.total_alarms = 0
            
        logger.info(f"🗑️ Cleared {alarm_count} scheduled alarms")
        return {"status": "success", "message": f"Cleared {alarm_count} alarms"}
        
    except Exception as e:
        logger.error(f"Error clearing alarms: {e}")
        raise HTTPException(status_code=500, detail=f"Scheduler error: {str(e)}")

@app.post("/reload")
async def reload_alarms():
    """Reload all alarms from database"""
    try:
        # Clear existing alarms
        with scheduler.lock:
            scheduler.time_index.clear()
            scheduler.alarms.clear()
            scheduler.total_alarms = 0
        
        # Load from database
        load_existing_alarms()
        
        return {
            "status": "success", 
            "message": "Alarms reloaded from database",
            "total_alarms": scheduler.get_alarm_count()
        }
        
    except Exception as e:
        logger.error(f"Error reloading alarms: {e}")
        raise HTTPException(status_code=500, detail=f"Reload error: {str(e)}")

@app.get("/debug/test-alarm")
async def test_alarm():
    """Test endpoint to create a test alarm for the next minute"""
    try:
        current_time = datetime.now(pytz.UTC)
        # Create alarm for next minute, 10 seconds in
        next_minute = current_time.replace(second=0, microsecond=0) + timedelta(minutes=1)
        test_time = f"{next_minute.hour:02d}:{next_minute.minute:02d}:10"
        
        alarm_id = f"test_alarm_{datetime.now(pytz.UTC).strftime('%H%M%S')}"
        
        alarm_data = {
            "code_id": "TEST",
            "email": "test@example.com",
            "time": test_time,
            "is_recurring": False
        }
        
        success = scheduler.add_alarm(alarm_id, alarm_data)
        
        if success:
            logger.info(f"🧪 Created test alarm: {alarm_id} for {test_time}")
            logger.info(f"   Current time: {current_time.strftime('%H:%M:%S')} ({pytz.UTC})")
            logger.info(f"   Alarm will fire at {test_time}")
            logger.info(f"   Expected fire time: {next_minute.strftime('%H:%M:%S')} ({pytz.UTC})")
            
            return {
                "status": "success",
                "message": f"Test alarm created for {test_time}",
                "alarm_id": alarm_id,
                "test_time": test_time,
                "current_time": current_time.strftime('%H:%M:%S'),
                "timezone": pytz.UTC,
                "expected_fire_time": next_minute.strftime('%H:%M:%S'),
                "total_alarms": scheduler.get_alarm_count(),
                "scheduler_stats": scheduler.get_time_index_stats()
            }
        else:
            return {"error": "Failed to add test alarm"}
            
    except Exception as e:
        return {"error": str(e)}

@app.get("/debug/manual-trigger")
async def manual_trigger():
    """Manually trigger all scheduled alarms for testing"""
    try:
        if scheduler.get_alarm_count() == 0:
            return {"status": "no_alarms", "message": "No alarms scheduled"}
        
        triggered_count = 0
        with scheduler.lock:
            for alarm_id, alarm_data in list(scheduler.alarms.items()):
                logger.info(f"🔧 MANUALLY TRIGGERING ALARM: {alarm_id}")
                trigger_alarm(alarm_data)
                triggered_count += 1
                
                # Remove non-recurring alarms
                if not alarm_data['is_recurring']:
                    scheduler.remove_alarm(alarm_id)
                    logger.info(f"🗑️ Removed non-recurring alarm: {alarm_id}")
        
        return {
            "status": "success",
            "message": f"Manually triggered {triggered_count} alarms",
            "triggered_count": triggered_count,
            "remaining_alarms": scheduler.get_alarm_count()
        }
    except Exception as e:
        return {"error": str(e)}

@app.get("/debug/time-check")
async def debug_time_check():
    """Debug endpoint to show time comparison details"""
    try:
        current_time = datetime.now(pytz.UTC)
        result = {
            "current_time": current_time.strftime('%H:%M:%S'),
            "timezone": pytz.UTC,
            "current_hour": current_time.hour,
            "current_minute": current_time.minute,
            "current_second": current_time.second,
            "total_alarms": scheduler.get_alarm_count(),
            "alarm_details": []
        }
        
        with scheduler.lock:
            for alarm_id, alarm_data in scheduler.alarms.items():
                try:
                    hour, minute, second = scheduler._parse_time_to_hms(alarm_data['time'])
                    target_time = current_time.replace(hour=hour, minute=minute, second=second, microsecond=0)
                    time_diff = (target_time - current_time).total_seconds()
                    
                    alarm_detail = {
                        "alarm_id": alarm_id,
                        "alarm_time": alarm_data['time'],
                        "parsed_hour": hour,
                        "parsed_minute": minute,
                        "parsed_second": second,
                        "target_time": target_time.strftime('%H:%M:%S'),
                        "time_diff_seconds": time_diff,
                        "is_due": time_diff <= 0,
                        "is_due_within_minute": -60 <= time_diff <= 0
                    }
                    result["alarm_details"].append(alarm_detail)
                    
                except Exception as e:
                    alarm_detail = {
                        "alarm_id": alarm_id,
                        "error": str(e)
                    }
                    result["alarm_details"].append(alarm_detail)
        
        return result
    except Exception as e:
        return {"error": str(e)}

@app.get("/debug/test-now")
async def test_alarm_now():
    """Test endpoint to create a test alarm for the current second"""
    try:
        current_time = datetime.now(pytz.UTC)
        # Create alarm for current second
        test_time = f"{current_time.hour:02d}:{current_time.minute:02d}:{current_time.second:02d}"
        
        alarm_id = f"test_now_{datetime.now(pytz.UTC).strftime('%H%M%S')}"
        
        alarm_data = {
            "code_id": "TEST_NOW",
            "email": "test@example.com",
            "time": test_time,
            "is_recurring": False
        }
        
        success = scheduler.add_alarm(alarm_id, alarm_data)
        
        if success:
            logger.info(f"🧪 Created immediate test alarm: {alarm_id} for {test_time}")
            logger.info(f"   Current time: {current_time.strftime('%H:%M:%S')} ({pytz.UTC})")
            logger.info(f"   Alarm should fire immediately!")
            
            return {
                "status": "success",
                "message": f"Immediate test alarm created for {test_time}",
                "alarm_id": alarm_id,
                "test_time": test_time,
                "current_time": current_time.strftime('%H:%M:%S'),
                "timezone": pytz.UTC,
                "total_alarms": scheduler.get_alarm_count()
            }
        else:
            return {"error": "Failed to add immediate test alarm"}
            
    except Exception as e:
        return {"error": str(e)}

@app.get("/debug/timezone-test")
async def debug_timezone_test():
    """Debug endpoint to test timezone conversion"""
    try:
        current_time = datetime.now(pytz.UTC)
        utc_time = datetime.utcnow()
        
        # Test with a specific alarm time (22:25:00)
        test_hour, test_minute, test_second = 22, 25, 0
        
        # Convert from UTC to local
        utc_alarm_time = utc_time.replace(hour=test_hour, minute=test_minute, second=test_second, microsecond=0)
        local_alarm_time = utc_alarm_time.replace(tzinfo=pytz.UTC).astimezone(pytz.UTC) # Convert to UTC for comparison
        
        result = {
            "current_utc": utc_time.strftime('%H:%M:%S'),
            "current_local": current_time.strftime('%H:%M:%S'),
            "timezone": pytz.UTC,
            "test_alarm_utc": f"{test_hour:02d}:{test_minute:02d}:{test_second:02d}",
            "test_alarm_local": local_alarm_time.strftime('%H:%M:%S'),
            "hour_match": current_time.hour == local_alarm_time.hour,
            "minute_match": current_time.minute == local_alarm_time.minute,
            "second_match": current_time.second == local_alarm_time.second,
            "time_diff_seconds": abs((current_time.hour * 3600 + current_time.minute * 60 + current_time.second) - 
                                   (local_alarm_time.hour * 3600 + local_alarm_time.minute * 60 + local_alarm_time.second))
        }
        
        return result
    except Exception as e:
        return {"error": str(e)}

@app.get("/debug/force-trigger")
async def force_trigger():
    """Force trigger all alarms for testing"""
    try:
        if scheduler.get_alarm_count() == 0:
            return {"status": "no_alarms", "message": "No alarms scheduled"}
        
        triggered_count = 0
        with scheduler.lock:
            for alarm_id, alarm_data in list(scheduler.alarms.items()):
                logger.info(f"🔧 FORCE TRIGGERING ALARM: {alarm_id}")
                trigger_alarm(alarm_data)
                triggered_count += 1
                
                # Remove non-recurring alarms
                if not alarm_data['is_recurring']:
                    scheduler.remove_alarm(alarm_id)
                    logger.info(f"🗑️ Removed non-recurring alarm: {alarm_id}")
        
        return {
            "status": "success",
            "message": f"Force triggered {triggered_count} alarms",
            "triggered_count": triggered_count,
            "remaining_alarms": scheduler.get_alarm_count()
        }
    except Exception as e:
        return {"error": str(e)}

@app.get("/debug/test-current-time")
async def test_current_time():
    """Test endpoint to create an alarm for the current time"""
    try:
        current_time = datetime.now(pytz.UTC)
        # Create alarm for current time
        test_time = f"{current_time.hour:02d}:{current_time.minute:02d}:{current_time.second:02d}"
        
        alarm_id = f"test_current_{datetime.now(pytz.UTC).strftime('%H%M%S')}"
        
        alarm_data = {
            "code_id": "TEST_CURRENT",
            "email": "test@example.com",
            "time": test_time,
            "is_recurring": False,
            "days_of_week": "Mon,Tue,Wed,Thu,Fri,Sat,Sun",
            "timezone": "UTC"
        }
        
        success = scheduler.add_alarm(alarm_id, alarm_data)
        
        if success:
            logger.info(f"🧪 Created current time test alarm: {alarm_id} for {test_time}")
            logger.info(f"   Current time: {current_time.strftime('%H:%M:%S')} ({pytz.UTC})")
            logger.info(f"   Alarm should fire within 1-2 seconds!")
            
            # Show what's in the time index
            hour, minute, second = scheduler._parse_time_to_hms(test_time)
            logger.info(f"   Added to time index: [{hour}:{minute}:{second}]")
            
            return {
                "status": "success",
                "message": f"Current time test alarm created for {test_time}",
                "alarm_id": alarm_id,
                "test_time": test_time,
                "current_time": current_time.strftime('%H:%M:%S'),
                "timezone": pytz.UTC,
                "total_alarms": scheduler.get_alarm_count(),
                "time_index_location": f"{hour}:{minute}:{second}"
            }
        else:
            return {"error": "Failed to add current time test alarm"}
            
    except Exception as e:
        return {"error": str(e)}

@app.get("/debug/time-debug")
async def time_debug():
    """Debug endpoint to show current time calculation details"""
    try:
        current_time = datetime.now(pytz.UTC)
        
        # Test with the existing alarm time (22:43:00)
        test_hour, test_minute, test_second = 22, 43, 0
        
        # Calculate target time
        target_time = current_time.replace(hour=test_hour, minute=test_minute, second=test_second, microsecond=0)
        
        if target_time <= current_time:
            target_time += timedelta(days=1)
        
        time_diff = (current_time - target_time).total_seconds()
        
        result = {
            "current_time": current_time.strftime('%H:%M:%S'),
            "timezone": pytz.UTC,
            "test_alarm_time": f"{test_hour:02d}:{test_minute:02d}:{test_second:02d}",
            "target_time_today": current_time.replace(hour=test_hour, minute=test_minute, second=test_second, microsecond=0).strftime('%H:%M:%S'),
            "final_target_time": target_time.strftime('%H:%M:%S'),
            "time_diff_seconds": time_diff,
            "time_diff_hours": time_diff / 3600,
            "will_trigger": -1 <= time_diff <= 1,
            "hours_until_alarm": abs(time_diff) / 3600 if time_diff < 0 else 0
        }
        
        return result
    except Exception as e:
        return {"error": str(e)}

@app.get("/debug/performance")
async def performance_metrics():
    """Performance monitoring endpoint"""
    try:
        current_time = datetime.now(pytz.UTC)
        
        # Get scheduler stats
        stats = scheduler.get_time_index_stats()
        
        # Calculate theoretical performance
        alarm_count = scheduler.get_alarm_count()
        theoretical_ops_per_sec = 1  # O(1) lookup now!
        theoretical_ops_per_min = 60
        
        # Estimate memory usage (rough calculation)
        estimated_memory_bytes = alarm_count * 200  # ~200 bytes per alarm
        estimated_memory_mb = estimated_memory_bytes / (1024 * 1024)
        
        # Performance tiers
        if alarm_count <= 10000:
            performance_tier = "Excellent"
            recommendation = "No changes needed"
        elif alarm_count <= 100000:
            performance_tier = "Good"
            recommendation = "Monitor performance"
        elif alarm_count <= 1000000:
            performance_tier = "Fair"
            recommendation = "Consider horizontal scaling"
        else:
            performance_tier = "Poor"
            recommendation = "Implement distributed scheduling"
        
        result = {
            "current_time": current_time.strftime('%H:%M:%S'),
            "timezone": pytz.UTC,
            "alarm_count": alarm_count,
            "theoretical_ops_per_sec": theoretical_ops_per_sec,
            "theoretical_ops_per_min": theoretical_ops_per_min,
            "estimated_memory_mb": round(estimated_memory_mb, 2),
            "performance_tier": performance_tier,
            "recommendation": recommendation,
            "scalability_limits": {
                "recommended_max_alarms": 1000000,
                "absolute_max_alarms": 10000000,
                "memory_limit_mb": 1000
            },
            "scheduler_stats": stats
        }
        
        return result
    except Exception as e:
        return {"error": str(e)}

@app.get("/debug/scheduler-stats")
async def scheduler_stats():
    """Get detailed scheduler statistics"""
    try:
        stats = scheduler.get_time_index_stats()
        
        # Add additional metrics
        result = {
            "scheduler_stats": stats,
            "total_alarms": scheduler.get_alarm_count(),
            "time_index_size": len(scheduler.time_index),
            "memory_usage_estimate_mb": round(scheduler.get_alarm_count() * 200 / (1024 * 1024), 2)
        }
        
        return result
    except Exception as e:
        return {"error": str(e)}

# Startup event
@app.on_event("startup")
async def startup_event():
    """Initialize scalable alarm system on startup"""
    global alarm_thread, connection_pool
    logger.info("Scalable Alarm Scheduler Service starting...")
    
    try:
        # Initialize database connection pool
        connection_pool = psycopg2.pool.SimpleConnectionPool(
            MIN_CONNECTIONS, MAX_CONNECTIONS, DATABASE_URL
        )
        logger.info(f"✅ Database connection pool initialized ({MIN_CONNECTIONS}-{MAX_CONNECTIONS} connections)")
        
        # Load existing alarms
        load_existing_alarms()
        
        # Start scalable alarm checker thread
        alarm_thread = threading.Thread(target=scalable_alarm_checker, daemon=True)
        alarm_thread.start()
        logger.info("✅ Scalable alarm checker thread started")
        
        logger.info("✅ Scalable Alarm Scheduler Service started successfully")
        
    except Exception as e:
        logger.error(f"❌ Failed to start scalable alarm system: {e}")
        raise

# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    global stop_thread, connection_pool
    logger.info("Scalable Alarm Scheduler Service shutting down...")
    stop_thread = True
    
    if alarm_thread:
        alarm_thread.join(timeout=5)
    
    if connection_pool:
        connection_pool.closeall()
        logger.info("Database connection pool closed")
    
    logger.info("Scalable Alarm Scheduler Service shutdown complete") 