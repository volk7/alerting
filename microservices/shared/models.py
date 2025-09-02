from pydantic import BaseModel, validator
from typing import Optional
from datetime import datetime
import pytz

class AlarmRequest(BaseModel):
    code_id: str
    email: str
    time: str  # User input time in their timezone (e.g., "22:30:00")
    is_recurring: bool = False
    days_of_week: str = 'Mon,Tue,Wed,Thu,Fri,Sat,Sun'
    timezone: str = 'America/Los_Angeles'
    
    @validator('time')
    def validate_time_format(cls, v):
        """Validate time format HH:MM or HH:MM:SS"""
        parts = v.split(':')
        if len(parts) not in [2, 3]:
            raise ValueError('Time must be in format HH:MM or HH:MM:SS')
        try:
            hour, minute = int(parts[0]), int(parts[1])
            if len(parts) == 3:
                second = int(parts[2])
            else:
                second = 0
            if not (0 <= hour <= 23 and 0 <= minute <= 59 and 0 <= second <= 59):
                raise ValueError('Invalid time values')
        except ValueError:
            raise ValueError('Time must contain valid numbers')
        return v
    
    @validator('timezone')
    def validate_timezone(cls, v):
        """Validate timezone string"""
        try:
            pytz.timezone(v)
            return v
        except pytz.exceptions.UnknownTimeZoneError:
            raise ValueError(f'Invalid timezone: {v}')

class AlarmResponse(BaseModel):
    code_id: str
    email: str
    time: str  # Display time in user's timezone
    utc_time: str  # UTC time for internal use
    is_recurring: bool
    status: str = "scheduled"
    days_of_week: str = 'Mon,Tue,Wed,Thu,Fri,Sat,Sun'
    timezone: str = 'America/Los_Angeles'

class AlarmEvent(BaseModel):
    """Event published when alarm is triggered"""
    alarm_id: str
    code_id: str
    email: str
    time: str  # Original user time
    utc_time: str  # UTC time when alarm was scheduled
    triggered_at: datetime
    is_recurring: bool
    timezone: str

class EmailRequest(BaseModel):
    """Request to send email"""
    to_email: str
    code_id: str
    description: str
    alarm_time: str  # User's local time
    timezone: str

class DatabaseAlarm(BaseModel):
    """Database representation of alarm with UTC storage"""
    code_id: str
    email: str
    time: str  # User's local time for display
    utc_time: str  # UTC time for scheduling (HH:MM:SS format)
    is_recurring: bool
    days_of_week: str = 'Mon,Tue,Wed,Thu,Fri,Sat,Sun'
    timezone: str = 'America/Los_Angeles'
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

def convert_local_time_to_utc(time_str: str, timezone_str: str) -> str:
    """Convert local time string to UTC time string"""
    try:
        # Parse the time string
        parts = time_str.split(':')
        hour, minute = int(parts[0]), int(parts[1])
        second = int(parts[2]) if len(parts) == 3 else 0
        
        # Get timezone
        tz = pytz.timezone(timezone_str)
        
        # Create a datetime object for today in the user's timezone
        now = datetime.now(tz)
        local_time = now.replace(hour=hour, minute=minute, second=second, microsecond=0)
        
        # Convert to UTC
        utc_time = local_time.astimezone(pytz.UTC)
        
        # Return UTC time as string
        return f"{utc_time.hour:02d}:{utc_time.minute:02d}:{utc_time.second:02d}"
    except Exception as e:
        raise ValueError(f"Error converting time to UTC: {e}")

def convert_utc_time_to_local(utc_time_str: str, timezone_str: str) -> str:
    """Convert UTC time string to local time string"""
    try:
        # Parse the UTC time string
        parts = utc_time_str.split(':')
        hour, minute = int(parts[0]), int(parts[1])
        second = int(parts[2]) if len(parts) == 3 else 0
        
        # Get timezone
        tz = pytz.timezone(timezone_str)
        
        # Create a datetime object for today in UTC
        now_utc = datetime.now(pytz.UTC)
        utc_time = now_utc.replace(hour=hour, minute=minute, second=second, microsecond=0)
        
        # Convert to local timezone
        local_time = utc_time.astimezone(tz)
        
        # Return local time as string
        return f"{local_time.hour:02d}:{local_time.minute:02d}:{local_time.second:02d}"
    except Exception as e:
        raise ValueError(f"Error converting UTC time to local: {e}") 