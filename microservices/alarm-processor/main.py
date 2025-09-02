from fastapi import FastAPI, HTTPException
import threading
import logging
import os
import psycopg2
import httpx
from shared.models import AlarmEvent, EmailRequest
from shared.redis_client import RedisClient

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Alarm Processor Service", version="1.0.0")

# Configuration
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://admin:ZZ4charlie@localhost:5432/alarms_db")
DESCRIPTION_API_URL = os.getenv("DESCRIPTION_API_URL", "http://database-service:8001/code-descriptions")
TIMEZONE = os.getenv("TIMEZONE", "America/Los_Angeles")

# Initialize Redis client
redis_client = RedisClient()

# Global state
processor_running = False
processed_count = 0

def get_code_description(code_id: str) -> str:
    """Get code description from database service with fallback to default"""
    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.get(f"{DESCRIPTION_API_URL}/{code_id}")
            if response.status_code == 200:
                data = response.json()
                return data.get('description', f"Alarm code {code_id} has been triggered")
            return f"Alarm code {code_id} has been triggered"
    except Exception as e:
        logger.warning(f"Could not fetch description for {code_id}: {e}")
        return f"Alarm code {code_id} has been triggered"

def process_alarm_event(event: AlarmEvent):
    """Process a triggered alarm event"""
    global processed_count
    
    try:
        logger.info(f"🔄 PROCESSING ALARM: {event.code_id} for {event.email}")
        
        # Get code description
        description = get_code_description(event.code_id)
        
        # Create email request
        email_request = EmailRequest(
            to_email=event.email,
            code_id=event.code_id,
            description=description,
            alarm_time=event.time,
            timezone=event.timezone
        )
        
        # Publish email request to Redis
        success = redis_client.publish_email_request(email_request)
        
        if success:
            logger.info(f"📧 EMAIL REQUEST SENT for {event.email}")
            logger.info(f"   Code ID: {event.code_id}")
            logger.info(f"   Description: {description}")
            processed_count += 1
        else:
            logger.error(f"Failed to publish email request for {event.code_id}")
        
        # Remove non-recurring alarms from database
        if not event.is_recurring:
            try:
                conn = psycopg2.connect(DATABASE_URL)
                cursor = conn.cursor()
                cursor.execute(
                    "DELETE FROM alarms WHERE code_id = %s AND email = %s AND time = %s",
                    (event.code_id, event.email, event.time)
                )
                conn.commit()
                cursor.close()
                conn.close()
                logger.info(f"🗑️  REMOVED NON-RECURRING ALARM: {event.code_id}")
            except Exception as e:
                logger.error(f"Error removing non-recurring alarm: {e}")
        
    except Exception as e:
        logger.error(f"Error processing alarm event {event.alarm_id}: {e}")

def start_event_processor():
    """Start the event processor in a background thread"""
    global processor_running
    
    def processor_thread():
        logger.info("Starting alarm event processor...")
        redis_client.subscribe_to_alarm_events(process_alarm_event)
    
    if not processor_running:
        processor_running = True
        thread = threading.Thread(target=processor_thread, daemon=True)
        thread.start()
        logger.info("Alarm event processor started")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Test database connection
        conn = psycopg2.connect(DATABASE_URL)
        conn.close()
        
        # Test Redis connection
        redis_client.redis.ping()
        
        return {
            "status": "healthy", 
            "service": "alarm-processor",
            "database": "connected",
            "redis": "connected",
            "processor_running": processor_running,
            "processed_count": processed_count
        }
    except Exception as e:
        return {"status": "unhealthy", "service": "alarm-processor", "error": str(e)}

@app.post("/start")
async def start_processor():
    """Manually start the event processor"""
    try:
        start_event_processor()
        return {"status": "success", "message": "Event processor started"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error starting processor: {str(e)}")

@app.get("/stats")
async def get_stats():
    """Get processing statistics"""
    return {
        "processor_running": processor_running,
        "processed_count": processed_count,
        "service": "alarm-processor"
    }

@app.post("/reset")
async def reset_stats():
    """Reset processing statistics"""
    global processed_count
    processed_count = 0
    return {"status": "success", "message": "Statistics reset", "processed_count": processed_count}

# Debug endpoints
@app.get("/debug/status")
async def debug_status():
    """Debug endpoint to show service status"""
    return {
        "service": "alarm-processor",
        "processor_running": processor_running,
        "processed_count": processed_count,
        "database_url": DATABASE_URL,
        "description_api_url": DESCRIPTION_API_URL
    }

@app.get("/debug/test-description/{code_id}")
async def test_description_retrieval(code_id: str):
    """Debug endpoint to test code description retrieval"""
    description = get_code_description(code_id)
    return {
        "code_id": code_id,
        "description": description,
        "description_api_url": DESCRIPTION_API_URL,
        "timestamp": "test"
    }

# Startup event
@app.on_event("startup")
async def startup_event():
    """Initialize processor on startup"""
    logger.info("Alarm Processor Service starting...")
    start_event_processor()
    logger.info("Alarm Processor Service started successfully")

# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    global processor_running
    logger.info("Alarm Processor Service shutting down...")
    processor_running = False
    logger.info("Alarm Processor Service shutdown complete") 