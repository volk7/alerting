#!/usr/bin/env python3
"""
Clear Scheduler Memory
Clears all alarms from the scheduler's in-memory storage
"""

import requests
import json

# Configuration
SCHEDULER_URL = "http://localhost:8002"

def check_current_alarms():
    """Check what alarms are currently in the scheduler"""
    try:
        response = requests.get(f"{SCHEDULER_URL}/jobs/")
        if response.status_code == 200:
            data = response.json()
            print(f"📊 Current alarms in scheduler: {data.get('total_jobs', 0)}")
            for job in data.get('jobs', []):
                print(f"   - {job.get('code_id')} at {job.get('time')} (recurring: {job.get('is_recurring')})")
            return data
        else:
            print(f"❌ Failed to get jobs: {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ Error getting jobs: {e}")
        return None

def clear_scheduler():
    """Clear all alarms from scheduler memory"""
    try:
        response = requests.delete(f"{SCHEDULER_URL}/jobs/clear")
        if response.status_code == 200:
            print("✅ Scheduler memory cleared successfully")
            return True
        else:
            print(f"❌ Failed to clear scheduler: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error clearing scheduler: {e}")
        return False

def main():
    print("🔍 Checking current alarms in scheduler...")
    current_alarms = check_current_alarms()
    
    if current_alarms and current_alarms.get('total_jobs', 0) > 0:
        print(f"\n🧹 Clearing {current_alarms.get('total_jobs', 0)} alarms from scheduler memory...")
        if clear_scheduler():
            print("\n🔍 Verifying scheduler is now empty...")
            check_current_alarms()
    else:
        print("✅ Scheduler is already empty")

if __name__ == "__main__":
    main() 