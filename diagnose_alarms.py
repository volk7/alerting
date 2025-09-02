#!/usr/bin/env python3
"""
Diagnostic script for alarm system
"""
import requests
import json
from datetime import datetime
import time

def check_service_health():
    """Check if the alarm scheduler service is running"""
    try:
        response = requests.get("http://localhost:8001/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Service is healthy: {data}")
            return True
        else:
            print(f"❌ Service returned status {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Cannot connect to service: {e}")
        return False

def list_scheduled_jobs():
    """List all scheduled alarms"""
    try:
        response = requests.get("http://localhost:8001/jobs/", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"📋 Scheduled jobs: {data}")
            return data
        else:
            print(f"❌ Failed to get jobs: {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ Error getting jobs: {e}")
        return None

def create_test_alarm():
    """Create a test alarm"""
    try:
        current_time = datetime.now()
        test_time = f"{current_time.hour:02d}:{current_time.minute:02d}:30"
        
        alarm_data = {
            "code_id": "DIAGNOSTIC",
            "email": "test@example.com",
            "time": test_time,
            "is_recurring": False
        }
        
        response = requests.post("http://localhost:8001/schedule/", 
                               json=alarm_data, timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Test alarm created: {data}")
            return True
        else:
            print(f"❌ Failed to create test alarm: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error creating test alarm: {e}")
        return False

def test_alarm_endpoint():
    """Test the test alarm endpoint"""
    try:
        response = requests.get("http://localhost:8001/debug/test-alarm", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Test alarm endpoint: {data}")
            return True
        else:
            print(f"❌ Test alarm endpoint failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error with test alarm endpoint: {e}")
        return False

def manual_trigger():
    """Manually trigger alarms"""
    try:
        response = requests.get("http://localhost:8001/debug/manual-trigger", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Manual trigger: {data}")
            return True
        else:
            print(f"❌ Manual trigger failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error with manual trigger: {e}")
        return False

def main():
    """Run diagnostics"""
    print("🔍 Alarm System Diagnostics")
    print("=" * 50)
    
    # Check service health
    print("\n1. Checking service health...")
    if not check_service_health():
        print("❌ Service is not running or not accessible")
        return
    
    # List current jobs
    print("\n2. Listing current jobs...")
    jobs = list_scheduled_jobs()
    
    # Create test alarm
    print("\n3. Creating test alarm...")
    if create_test_alarm():
        print("✅ Test alarm created successfully")
    else:
        print("❌ Failed to create test alarm")
    
    # List jobs again
    print("\n4. Listing jobs after creating test alarm...")
    jobs = list_scheduled_jobs()
    
    # Test alarm endpoint
    print("\n5. Testing alarm endpoint...")
    test_alarm_endpoint()
    
    # Manual trigger
    print("\n6. Testing manual trigger...")
    manual_trigger()
    
    print("\n✅ Diagnostics completed")

if __name__ == "__main__":
    main() 