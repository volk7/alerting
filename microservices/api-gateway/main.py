from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import httpx
import os
from typing import List, Dict, Any
from shared.models import AlarmRequest, AlarmResponse

app = FastAPI(title="Alarm System API Gateway", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Service URLs (in production, these would be service discovery)
DATABASE_SERVICE_URL = os.getenv("DATABASE_SERVICE_URL", "http://database-service:8001")
ALARM_SCHEDULER_URL = os.getenv("ALARM_SCHEDULER_URL", "http://alarm-scheduler:8002")

@app.get("/")
async def root():
    return {"message": "Alarm System API Gateway", "status": "running"}

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "api-gateway"}

# Alarm Management Endpoints
@app.post("/alarms/", response_model=AlarmResponse)
async def add_alarm(alarm: AlarmRequest):
    """Add a new alarm - routes to database service and scheduler"""
    async with httpx.AsyncClient() as client:
        try:
            # First, add to database
            db_response = await client.post(
                f"{DATABASE_SERVICE_URL}/alarms/",
                json=alarm.dict(),
                timeout=10.0
            )
            
            if db_response.status_code != 200:
                raise HTTPException(status_code=db_response.status_code, detail="Database service error")
            
            # Then, schedule the alarm
            scheduler_response = await client.post(
                f"{ALARM_SCHEDULER_URL}/schedule/",
                json=alarm.dict(),
                timeout=10.0
            )
            
            if scheduler_response.status_code != 200:
                # If scheduling fails, we should clean up the database entry
                await client.delete(f"{DATABASE_SERVICE_URL}/alarms/", params={
                    "code_id": alarm.code_id,
                    "email": alarm.email,
                    "time": alarm.time
                })
                raise HTTPException(status_code=scheduler_response.status_code, detail="Scheduler service error")
            
            return AlarmResponse(**alarm.dict())
            
        except httpx.RequestError as e:
            raise HTTPException(status_code=503, detail=f"Service unavailable: {str(e)}")

@app.get("/alarms/", response_model=List[AlarmResponse])
async def list_alarms(limit: int = 20, offset: int = 0):
    """List alarms - routes to database service"""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{DATABASE_SERVICE_URL}/alarms/",
                params={"limit": limit, "offset": offset},
                timeout=10.0
            )
            
            if response.status_code != 200:
                raise HTTPException(status_code=response.status_code, detail="Database service error")
            
            # Ensure days_of_week and timezone are included in each alarm
            alarms = response.json()
            for alarm in alarms:
                if 'days_of_week' not in alarm:
                    alarm['days_of_week'] = 'Mon,Tue,Wed,Thu,Fri,Sat,Sun'
                if 'timezone' not in alarm:
                    alarm['timezone'] = 'America/Los_Angeles'
            return alarms
            
        except httpx.RequestError as e:
            raise HTTPException(status_code=503, detail=f"Service unavailable: {str(e)}")

@app.get("/alarms/count")
async def count_alarms():
    """Count alarms - routes to database service"""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{DATABASE_SERVICE_URL}/alarms/count", timeout=10.0)
            
            if response.status_code != 200:
                raise HTTPException(status_code=response.status_code, detail="Database service error")
            
            return response.json()
            
        except httpx.RequestError as e:
            raise HTTPException(status_code=503, detail=f"Service unavailable: {str(e)}")

@app.delete("/alarms/")
async def remove_alarm(code_id: str, email: str, time: str):
    """Remove alarm - routes to both database and scheduler services"""
    async with httpx.AsyncClient() as client:
        try:
            # Remove from scheduler first
            scheduler_response = await client.delete(
                f"{ALARM_SCHEDULER_URL}/unschedule/",
                params={"code_id": code_id, "email": email, "time": time},
                timeout=10.0
            )
            
            # Remove from database
            db_response = await client.delete(
                f"{DATABASE_SERVICE_URL}/alarms/",
                params={"code_id": code_id, "email": email, "time": time},
                timeout=10.0
            )
            
            if db_response.status_code != 200:
                raise HTTPException(status_code=db_response.status_code, detail="Database service error")
            
            return {"status": "success", "message": "Alarm removed"}
            
        except httpx.RequestError as e:
            raise HTTPException(status_code=503, detail=f"Service unavailable: {str(e)}")

# Debug endpoints
@app.get("/debug/services")
async def debug_services():
    """Debug endpoint to check service health"""
    services = {
        "database-service": DATABASE_SERVICE_URL,
        "alarm-scheduler": ALARM_SCHEDULER_URL
    }
    
    health_status = {}
    async with httpx.AsyncClient() as client:
        for service_name, service_url in services.items():
            try:
                response = await client.get(f"{service_url}/health", timeout=5.0)
                health_status[service_name] = {
                    "status": "healthy" if response.status_code == 200 else "unhealthy",
                    "url": service_url
                }
            except Exception as e:
                health_status[service_name] = {
                    "status": "unreachable",
                    "url": service_url,
                    "error": str(e)
                }
    
    return health_status 