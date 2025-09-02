#!/usr/bin/env python3
"""
Quick Alarm Test
Simple test to verify alarm creation and firing
"""

import requests
import time
from datetime import datetime, timedelta

# Configuration
SCHEDULER_URL = "http://localhost:8002"
DASHBOARD_URL = "http://localhost:5000"

def add_test_alarm(code_id, email, time_str, is_recurring=False):
    """Add a test alarm directly to the scheduler"""
    try:
        alarm_data = {
            "code_id": code_id,
            "email": email,
            "time": time_str,
            "is_recurring": is_recurring
        }
        
        print(f"📝 Creating alarm: {code_id} at {time_str} (recurring: {is_recurring})")
        response = requests.post(f"{SCHEDULER_URL}/schedule/", json=alarm_data)
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Added alarm: {code_id} at {time_str}")
            return True
        else:
            print(f"❌ Failed to add alarm {code_id}: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error adding alarm {code_id}: {e}")
        return False

def check_alarms():
    """Check current alarms"""
    try:
        response = requests.get(f"{SCHEDULER_URL}/jobs/")
        if response.status_code == 200:
            data = response.json()
            print(f"📊 Current alarms: {data.get('total_jobs', 0)}")
            for job in data.get('jobs', []):
                print(f"   - {job.get('code_id')} at {job.get('time')} (recurring: {job.get('is_recurring')})")
            return data
        else:
            print(f"❌ Failed to get jobs: {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ Error getting jobs: {e}")
        return None

def main():
    print("🚀 Quick Alarm Test")
    print("=" * 30)
    
    # Get current time and create test times
    now = datetime.now()
    time_30s = (now + timedelta(seconds=30)).strftime("%H:%M:%S")
    time_1m = (now + timedelta(minutes=1)).strftime("%H:%M:%S")
    
    print(f"⏰ Current time: {now.strftime('%H:%M:%S')}")
    print(f"📅 Test times: {time_30s}, {time_1m}")
    print()
    
    # Check initial state
    print("🔍 Initial state:")
    check_alarms()
    print()
    
    # Add test alarms
    print("📝 Adding test alarms...")
    
    # Test 1: 30 seconds from now (non-recurring)
    add_test_alarm("QUICK_TEST_1", "test1@example.com", time_30s, False)
    
    # Test 2: 1 minute from now (recurring)
    add_test_alarm("QUICK_TEST_2", "test2@example.com", time_1m, True)
    
    print()
    
    # Check final state
    print("🔍 Final state:")
    check_alarms()
    
    print()
    print("✅ Quick test completed!")
    print("📋 Expected behavior:")
    print("   - QUICK_TEST_1: Should fire in ~30 seconds and be removed")
    print("   - QUICK_TEST_2: Should fire in ~1 minute and remain (recurring)")
    print("   - Check scheduler logs for alarm firing messages")

if __name__ == "__main__":
    main() 