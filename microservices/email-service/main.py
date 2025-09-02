from fastapi import FastAPI, HTTPException
import threading
import logging
import os
import smtplib
import random
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from shared.models import EmailRequest
from shared.redis_client import RedisClient

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Email Service", version="1.0.0")

# Configuration
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.mail.yahoo.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "kluge7@yahoo.com")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "kpjlmwqsslhbecpq!")

# Simulation mode for testing
SIMULATION_MODE = os.getenv("SIMULATION_MODE", "true").lower() == "true"

# Initialize Redis client
redis_client = RedisClient()

# Global state
email_worker_running = False
sent_count = 0
failed_count = 0

def send_email_simulation(email_req: EmailRequest):
    """Simulate email sending for testing"""
    try:
        # Simulate email processing time (10-50ms)
        time.sleep(random.uniform(0.01, 0.05))
        
        # Log the simulated email with timezone info
        logger.info(f"📧 SIMULATED EMAIL SENT to {email_req.to_email}")
        logger.info(f"   Code ID: {email_req.code_id}")
        logger.info(f"   Description: {email_req.description}")
        logger.info(f"   Time: {email_req.alarm_time} ({email_req.timezone})")
        
        return True
    except Exception as e:
        logger.error(f"Error in simulated email sending: {e}")
        return False

def send_email_real(email_req: EmailRequest):
    """Send real email via SMTP with timezone information"""
    try:
        # Create message
        msg = MIMEMultipart()
        msg['From'] = SMTP_USER
        msg['To'] = email_req.to_email
        msg['Subject'] = f"Alarm: {email_req.code_id}"
        
        # Email body with timezone information
        body = f"""
        🔔 ALARM TRIGGERED 🔔
        
        Code ID: {email_req.code_id}
        Description: {email_req.description}
        Time: {email_req.alarm_time} ({email_req.timezone})
        
        This is an automated alarm notification.
        The time shown is in your local timezone.
        """
        
        msg.attach(MIMEText(body, 'plain'))
        
        # Send email
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
        
        logger.info(f"📧 REAL EMAIL SENT to {email_req.to_email}")
        logger.info(f"   Code ID: {email_req.code_id}")
        logger.info(f"   Description: {email_req.description}")
        logger.info(f"   Time: {email_req.alarm_time} ({email_req.timezone})")
        
        return True
        
    except Exception as e:
        logger.error(f"Error sending real email to {email_req.to_email}: {e}")
        return False

def process_email_request(email_req: EmailRequest):
    """Process an email request"""
    global sent_count, failed_count
    
    try:
        logger.info(f"📧 PROCESSING EMAIL REQUEST for {email_req.to_email}")
        logger.info(f"   Time: {email_req.alarm_time} ({email_req.timezone})")
        
        # Send email (simulated or real)
        if SIMULATION_MODE:
            success = send_email_simulation(email_req)
        else:
            success = send_email_real(email_req)
        
        if success:
            sent_count += 1
            logger.info(f"✅ EMAIL SENT SUCCESSFULLY to {email_req.to_email}")
        else:
            failed_count += 1
            logger.error(f"❌ EMAIL SEND FAILED for {email_req.to_email}")
        
    except Exception as e:
        failed_count += 1
        logger.error(f"Error processing email request: {e}")

def start_email_worker():
    """Start the email worker in a background thread"""
    global email_worker_running
    
    def worker_thread():
        logger.info("Starting email worker...")
        redis_client.subscribe_to_email_requests(process_email_request)
    
    if not email_worker_running:
        email_worker_running = True
        thread = threading.Thread(target=worker_thread, daemon=True)
        thread.start()
        logger.info("Email worker started")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Test Redis connection
        redis_client.redis.ping()
        
        # Test SMTP connection (if not in simulation mode)
        smtp_status = "simulation_mode"
        if not SIMULATION_MODE:
            try:
                with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
                    server.starttls()
                    server.login(SMTP_USER, SMTP_PASSWORD)
                smtp_status = "connected"
            except Exception as e:
                smtp_status = f"error: {str(e)}"
        
        return {
            "status": "healthy", 
            "service": "email-service",
            "redis": "connected",
            "smtp": smtp_status,
            "simulation_mode": SIMULATION_MODE,
            "worker_running": email_worker_running,
            "sent_count": sent_count,
            "failed_count": failed_count
        }
    except Exception as e:
        return {"status": "unhealthy", "service": "email-service", "error": str(e)}

@app.post("/start")
async def start_worker():
    """Manually start the email worker"""
    try:
        start_email_worker()
        return {"status": "success", "message": "Email worker started"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error starting worker: {str(e)}")

@app.get("/stats")
async def get_stats():
    """Get email statistics"""
    return {
        "worker_running": email_worker_running,
        "sent_count": sent_count,
        "failed_count": failed_count,
        "simulation_mode": SIMULATION_MODE,
        "service": "email-service"
    }

@app.post("/reset")
async def reset_stats():
    """Reset email statistics"""
    global sent_count, failed_count
    sent_count = 0
    failed_count = 0
    return {"status": "success", "message": "Statistics reset", "sent_count": sent_count, "failed_count": failed_count}

@app.post("/test")
async def test_email(to_email: str = "test@example.com", timezone: str = "America/Los_Angeles"):
    """Send a test email with timezone information"""
    try:
        test_request = EmailRequest(
            to_email=to_email,
            code_id="TEST_EMAIL",
            description="This is a test email from the email service with timezone support",
            alarm_time="12:00:00",
            timezone=timezone
        )
        
        if SIMULATION_MODE:
            success = send_email_simulation(test_request)
        else:
            success = send_email_real(test_request)
        
        if success:
            return {
                "status": "success", 
                "message": f"Test email sent to {to_email}",
                "timezone": timezone,
                "simulation_mode": SIMULATION_MODE
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to send test email")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error sending test email: {str(e)}")

@app.get("/debug/status")
async def debug_status():
    """Debug endpoint to show email service status"""
    return {
        "service": "email-service",
        "worker_running": email_worker_running,
        "simulation_mode": SIMULATION_MODE,
        "smtp_server": SMTP_SERVER,
        "smtp_port": SMTP_PORT,
        "sent_count": sent_count,
        "failed_count": failed_count,
        "redis_connected": redis_client.redis.ping() if redis_client.redis else False
    }

@app.on_event("startup")
async def startup_event():
    """Start email worker on startup"""
    logger.info("🚀 Email service starting up...")
    start_email_worker()

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    global email_worker_running
    email_worker_running = False
    logger.info("🛑 Email service shutting down...") 