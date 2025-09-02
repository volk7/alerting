#!/usr/bin/env python3
"""
Simple alarm test - no external dependencies
"""
import threading
import time
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Simple alarm storage
alarms = {}
alarm_thread = None
stop_thread = False

def parse_time_to_hms(time_str: str) -> tuple:
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

def trigger_alarm(alarm_data: dict):
    """Trigger an alarm"""
    logger.info(f"🔔 ALARM TRIGGERED: {alarm_data['time']} for {alarm_data['email']}")
    logger.info(f"   Code ID: {alarm_data['code_id']}")
    logger.info(f"   Current time: {datetime.now().strftime('%H:%M:%S')}")

def alarm_checker():
    """Background thread that checks for alarms to trigger"""
    global alarms, stop_thread
    logger.info("🚀 Alarm checker thread started")
    
    tick_count = 0
    while not stop_thread:
        try:
            current_time = datetime.now()
            current_hour = current_time.hour
            current_minute = current_time.minute
            current_second = current_time.second
            
            tick_count += 1
            
            # Log every 10 ticks (every 10 seconds) to show the loop is running
            if tick_count % 10 == 0:
                logger.info(f"⏰ Tick #{tick_count}, current time: {current_time.strftime('%H:%M:%S')}, alarms: {len(alarms)}")
                
                # Show details of scheduled alarms every 10 ticks
                if alarms:
                    logger.info("📋 SCHEDULED ALARMS:")
                    for alarm_id, alarm_data in alarms.items():
                        logger.info(f"   {alarm_id}: {alarm_data['time']} for {alarm_data['email']}")
            
            # Check each alarm
            alarms_to_trigger = []
            for alarm_id, alarm_data in list(alarms.items()):
                try:
                    hour, minute, second = parse_time_to_hms(alarm_data['time'])
                    
                    # Check if it's time to trigger
                    if (current_hour == hour and 
                        current_minute == minute and 
                        current_second == second):
                        
                        logger.info(f"🎯 TIME TO TRIGGER ALARM: {alarm_id}")
                        logger.info(f"   Current time: {current_time.strftime('%H:%M:%S')}")
                        logger.info(f"   Alarm time: {alarm_data['time']}")
                        alarms_to_trigger.append((alarm_id, alarm_data))
                        
                        # Remove non-recurring alarms
                        if not alarm_data['is_recurring']:
                            del alarms[alarm_id]
                            logger.info(f"🗑️ Removed non-recurring alarm: {alarm_id}")
                            
                except Exception as e:
                    logger.error(f"Error checking alarm {alarm_id}: {e}")
            
            # Trigger alarms
            if alarms_to_trigger:
                logger.info(f"🚨 FOUND {len(alarms_to_trigger)} ALARMS TO TRIGGER!")
                
            for alarm_id, alarm_data in alarms_to_trigger:
                logger.info(f"🔔 TRIGGERING ALARM: {alarm_id}")
                trigger_alarm(alarm_data)
            
            # Sleep for 1 second
            time.sleep(1)
            
        except Exception as e:
            logger.error(f"Error in alarm checker: {e}")
            time.sleep(1)
    
    logger.info("🛑 Alarm checker thread stopped")

def add_test_alarm():
    """Add a test alarm for 30 seconds from now"""
    current_time = datetime.now()
    test_time = f"{current_time.hour:02d}:{current_time.minute:02d}:30"
    
    alarm_data = {
        "code_id": "TEST",
        "email": "test@example.com",
        "time": test_time,
        "is_recurring": False
    }
    
    alarm_id = f"test_alarm_{datetime.now().strftime('%H%M%S')}"
    alarms[alarm_id] = alarm_data
    
    logger.info(f"🧪 Created test alarm: {alarm_id} for {test_time}")
    logger.info(f"   Current time: {current_time.strftime('%H:%M:%S')}")
    logger.info(f"   Alarm will fire at {test_time}")
    
    return alarm_id, test_time

def main():
    """Main test function"""
    global alarm_thread, stop_thread
    
    logger.info("🧪 Starting simple alarm system test...")
    
    # Start alarm checker thread
    alarm_thread = threading.Thread(target=alarm_checker, daemon=True)
    alarm_thread.start()
    logger.info("✅ Alarm checker thread started")
    
    # Add a test alarm
    alarm_id, test_time = add_test_alarm()
    
    # Wait for alarm to fire
    logger.info("⏳ Waiting for alarm to fire...")
    time.sleep(60)  # Wait 60 seconds to see if it fires
    
    # Stop the thread
    stop_thread = True
    if alarm_thread:
        alarm_thread.join(timeout=5)
    
    logger.info("✅ Test completed")

if __name__ == "__main__":
    main() 