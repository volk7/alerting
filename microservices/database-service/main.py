from fastapi import FastAPI, HTTPException
from sqlalchemy import create_engine, Column, String, Boolean, DateTime, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError
import os
from datetime import datetime
from typing import List, Optional
from shared.models import AlarmRequest, AlarmResponse, DatabaseAlarm, convert_local_time_to_utc, convert_utc_time_to_local

app = FastAPI(title="Database Service", version="1.0.0")

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://admin:ZZ4charlie@localhost:5432/alarms_db")
TIMEZONE = os.getenv("TIMEZONE", "America/Los_Angeles")

# SQLAlchemy setup
engine = create_engine(DATABASE_URL, pool_size=20, max_overflow=30)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Database models
class Alarm(Base):
    __tablename__ = "alarms"
    
    code_id = Column(String, primary_key=True)
    email = Column(String, primary_key=True)
    time = Column(String, primary_key=True)  # User's local time for display
    utc_time = Column(String, nullable=False)  # UTC time for scheduling
    is_recurring = Column(Boolean, default=False)
    days_of_week = Column(String, default="Mon,Tue,Wed,Thu,Fri,Sat,Sun")
    timezone = Column(String, default="America/Los_Angeles")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class CodeDescription(Base):
    __tablename__ = "code_descriptions"
    
    code_id = Column(String, primary_key=True)
    description = Column(String, nullable=False)

# Create tables
Base.metadata.create_all(bind=engine)

# Dependency to get database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Test database connection
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "healthy", "service": "database-service", "database": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "service": "database-service", "error": str(e)}

@app.post("/alarms/", response_model=AlarmResponse)
async def add_alarm(alarm: AlarmRequest):
    """Add a new alarm to the database with UTC time conversion"""
    db = SessionLocal()
    try:
        # Convert user's local time to UTC for storage
        utc_time = convert_local_time_to_utc(alarm.time, alarm.timezone)
        
        db_alarm = Alarm(
            code_id=alarm.code_id,
            email=alarm.email,
            time=alarm.time,  # Store original user time for display
            utc_time=utc_time,  # Store UTC time for scheduling
            is_recurring=alarm.is_recurring,
            days_of_week=alarm.days_of_week,
            timezone=alarm.timezone
        )
        db.add(db_alarm)
        db.commit()
        db.refresh(db_alarm)
        
        return AlarmResponse(
            code_id=db_alarm.code_id,
            email=db_alarm.email,
            time=db_alarm.time,  # Display time in user's timezone
            utc_time=db_alarm.utc_time,  # UTC time for internal use
            is_recurring=db_alarm.is_recurring,
            status="scheduled",
            days_of_week=db_alarm.days_of_week,
            timezone=db_alarm.timezone
        )
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Alarm already exists")
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Invalid time format: {str(e)}")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        db.close()

@app.get("/alarms/", response_model=List[AlarmResponse])
async def list_alarms(limit: int = 20, offset: int = 0):
    """List alarms with pagination"""
    db = SessionLocal()
    try:
        alarms = db.query(Alarm).order_by(Alarm.code_id, Alarm.email, Alarm.time).offset(offset).limit(limit).all()
        
        return [
            AlarmResponse(
                code_id=alarm.code_id,
                email=alarm.email,
                time=alarm.time,  # Display time in user's timezone
                utc_time=alarm.utc_time,  # UTC time for internal use
                is_recurring=alarm.is_recurring,
                status="scheduled",
                days_of_week=alarm.days_of_week,
                timezone=alarm.timezone
            )
            for alarm in alarms
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        db.close()

@app.get("/alarms/count")
async def count_alarms():
    """Count total number of alarms"""
    db = SessionLocal()
    try:
        count = db.query(Alarm).count()
        return {"count": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        db.close()

@app.delete("/alarms/")
async def remove_alarm(code_id: str, email: str, time: str):
    """Remove an alarm from the database"""
    db = SessionLocal()
    try:
        alarm = db.query(Alarm).filter(
            Alarm.code_id == code_id,
            Alarm.email == email,
            Alarm.time == time
        ).first()
        
        if not alarm:
            raise HTTPException(status_code=404, detail="Alarm not found")
        
        db.delete(alarm)
        db.commit()
        
        return {"status": "success", "message": "Alarm removed"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        db.close()

@app.get("/alarms/{code_id}")
async def get_alarm(code_id: str):
    """Get alarms by code_id"""
    db = SessionLocal()
    try:
        alarms = db.query(Alarm).filter(Alarm.code_id == code_id).all()
        
        return [
            AlarmResponse(
                code_id=alarm.code_id,
                email=alarm.email,
                time=alarm.time,  # Display time in user's timezone
                utc_time=alarm.utc_time,  # UTC time for internal use
                is_recurring=alarm.is_recurring,
                status="scheduled",
                days_of_week=alarm.days_of_week,
                timezone=alarm.timezone
            )
            for alarm in alarms
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        db.close()

@app.put("/alarms/", response_model=AlarmResponse)
async def update_alarm(alarm: AlarmRequest):
    """Update an existing alarm with UTC time conversion"""
    db = SessionLocal()
    try:
        db_alarm = db.query(Alarm).filter(
            Alarm.code_id == alarm.code_id,
            Alarm.email == alarm.email,
            Alarm.time == alarm.time
        ).first()
        
        if not db_alarm:
            raise HTTPException(status_code=404, detail="Alarm not found")
        
        # Convert user's local time to UTC for storage
        utc_time = convert_local_time_to_utc(alarm.time, alarm.timezone)
        
        db_alarm.utc_time = utc_time
        db_alarm.is_recurring = alarm.is_recurring
        db_alarm.days_of_week = alarm.days_of_week
        db_alarm.timezone = alarm.timezone
        db_alarm.updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(db_alarm)
        
        return AlarmResponse(
            code_id=db_alarm.code_id,
            email=db_alarm.email,
            time=db_alarm.time,  # Display time in user's timezone
            utc_time=db_alarm.utc_time,  # UTC time for internal use
            is_recurring=db_alarm.is_recurring,
            status="updated",
            days_of_week=db_alarm.days_of_week,
            timezone=db_alarm.timezone
        )
    except HTTPException:
        raise
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Invalid time format: {str(e)}")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        db.close()

# Debug endpoints
@app.get("/debug/alarms")
async def debug_alarms():
    """Debug endpoint to show all alarms with timezone info"""
    db = SessionLocal()
    try:
        alarms = db.query(Alarm).all()
        return {
            "total_alarms": len(alarms),
            "alarms": [
                {
                    "code_id": alarm.code_id,
                    "email": alarm.email,
                    "time": alarm.time,  # User's local time
                    "utc_time": alarm.utc_time,  # UTC time
                    "is_recurring": alarm.is_recurring,
                    "days_of_week": alarm.days_of_week,
                    "timezone": alarm.timezone,
                    "created_at": alarm.created_at.isoformat() if alarm.created_at else None,
                    "updated_at": alarm.updated_at.isoformat() if alarm.updated_at else None
                }
                for alarm in alarms
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        db.close()

# Code descriptions endpoints
@app.get("/code-descriptions/{code_id}")
async def get_code_description(code_id: str):
    """Get description for a specific code_id"""
    db = SessionLocal()
    try:
        description = db.query(CodeDescription).filter(CodeDescription.code_id == code_id).first()
        
        if not description:
            return {"code_id": code_id, "description": f"No description available for {code_id}"}
        
        return {"code_id": code_id, "description": description.description}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        db.close()

@app.get("/code-descriptions/")
async def list_code_descriptions():
    """List all code descriptions"""
    db = SessionLocal()
    try:
        descriptions = db.query(CodeDescription).order_by(CodeDescription.code_id).all()
        
        return [
            {"code_id": desc.code_id, "description": desc.description}
            for desc in descriptions
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        db.close()

@app.post("/code-descriptions/")
async def add_code_description(code_id: str, description: str):
    """Add a new code description"""
    db = SessionLocal()
    try:
        db_description = CodeDescription(code_id=code_id, description=description)
        db.add(db_description)
        db.commit()
        db.refresh(db_description)
        
        return {"code_id": db_description.code_id, "description": db_description.description}
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Code description already exists")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        db.close() 