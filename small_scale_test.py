#!/usr/bin/env python3
"""
Small Scale Alarm Test
Tests the alarm system with a few alarms to verify functionality
"""

import requests
import time
import json
from datetime import datetime, timedelta
import threading

# Configuration
DASHBOARD_URL = "http://localhost:5000"
SCHEDULER_URL = "http://localhost:8002"

def get_current_time():
    """Get current time in HH:MM:SS format"""
    return datetime.now().strftime("%H:%M:%S")

def add_test_alarm(code_id, email, time_str, is_recurring=False):
    """Add a test alarm directly to the scheduler"""
    try:
        alarm_data = {
            "code_id": code_id,
            "email": email,
            "time": time_str,
            "is_recurring": is_recurring
        }
        
        response = requests.post(f"{SCHEDULER_URL}/schedule/", json=alarm_data)
        
        if response.status_code == 200:
            print(f"✅ Added alarm: {code_id} at {time_str} ({'recurring' if is_recurring else 'one-time'})")
            return True
        else:
            print(f"❌ Failed to add alarm {code_id}: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error adding alarm {code_id}: {e}")
        return False

def get_alarms():
    """Get current alarms from dashboard"""
    try:
        response = requests.get(f"{DASHBOARD_URL}/api/alarms")
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        print(f"❌ Error getting alarms: {e}")
        return None

def get_health():
    """Get scheduler health"""
    try:
        response = requests.get(f"{SCHEDULER_URL}/health")
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        print(f"❌ Error getting health: {e}")
        return None

def get_scheduler_jobs():
    """Get scheduler jobs directly"""
    try:
        response = requests.get(f"{SCHEDULER_URL}/jobs/")
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        print(f"❌ Error getting jobs: {e}")
        return None

def monitor_alarms(duration=60):
    """Monitor alarms for a specified duration"""
    print(f"\n🔍 Monitoring alarms for {duration} seconds...")
    start_time = time.time()
    
    while time.time() - start_time < duration:
        try:
            # Get current alarms
            alarms = get_alarms()
            if alarms:
                print(f"⏰ {datetime.now().strftime('%H:%M:%S')} - Active alarms: {len(alarms.get('alarms', []))}")
            
            # Get health status
            health = get_health()
            if health:
                status = health.get('status', 'unknown')
                scheduled = health.get('scheduled_alarms', 0)
                thread_running = health.get('thread_running', False)
                print(f"   Health: {status}, Scheduled: {scheduled}, Thread: {'✅' if thread_running else '❌'}")
            
            # Get scheduler jobs
            scheduler_jobs = get_scheduler_jobs()
            if scheduler_jobs:
                total_jobs = scheduler_jobs.get('total_jobs', 0)
                print(f"   Scheduler jobs: {total_jobs}")
            
            time.sleep(5)
            
        except KeyboardInterrupt:
            print("\n⏹️ Monitoring stopped by user")
            break
        except Exception as e:
            print(f"❌ Monitoring error: {e}")
            time.sleep(5)

def run_small_scale_test():
    """Run the small scale test"""
    print("🚀 Starting Small Scale Alarm Test")
    print("=" * 50)
    
    # Clear any existing alarms first
    print("🧹 Clearing existing alarms...")
    try:
        requests.post(f"{DASHBOARD_URL}/clear_alarms")
        time.sleep(2)
    except:
        pass
    
    # Get current time and calculate test times
    now = datetime.now()
    current_time = now.strftime("%H:%M:%S")
    
    # Create test times: 30 seconds, 1 minute, and 2 minutes from now
    time_30s = (now + timedelta(seconds=30)).strftime("%H:%M:%S")
    time_1m = (now + timedelta(minutes=1)).strftime("%H:%M:%S")
    time_2m = (now + timedelta(minutes=2)).strftime("%H:%M:%S")
    
    print(f"⏰ Current time: {current_time}")
    print(f"📅 Test times: {time_30s}, {time_1m}, {time_2m}")
    print()
    
    # Add test alarms
    print("📝 Adding test alarms...")
    alarms_added = 0
    
    # Test 1: 30 seconds from now
    if add_test_alarm("TEST001", "test1@example.com", time_30s, False):
        alarms_added += 1
    
    # Test 2: 1 minute from now (recurring)
    if add_test_alarm("TEST002", "test2@example.com", time_1m, True):
        alarms_added += 1
    
    # Test 3: 2 minutes from now
    if add_test_alarm("TEST003", "test3@example.com", time_2m, False):
        alarms_added += 1
    
    print(f"\n✅ Added {alarms_added} test alarms")
    
    # Reload alarms from database to scheduler
    print("\n🔄 Reloading alarms from database...")
    try:
        response = requests.post(f"{SCHEDULER_URL}/reload")
        if response.status_code == 200:
            print("✅ Alarms reloaded successfully")
        else:
            print(f"❌ Failed to reload alarms: {response.status_code}")
    except Exception as e:
        print(f"❌ Error reloading alarms: {e}")
    
    # Verify alarms were added
    print("\n🔍 Verifying alarms...")
    alarms = get_alarms()
    if alarms:
        print(f"📊 Found {len(alarms.get('alarms', []))} alarms in system")
        for alarm in alarms.get('alarms', []):
            print(f"   - {alarm.get('code_id')} at {alarm.get('time')} ({'recurring' if alarm.get('is_recurring') else 'one-time'})")
    
    # Also check scheduler directly
    print("\n🔍 Checking scheduler directly...")
    scheduler_jobs = get_scheduler_jobs()
    if scheduler_jobs:
        print(f"📊 Scheduler has {scheduler_jobs.get('total_jobs', 0)} jobs")
        for job in scheduler_jobs.get('jobs', []):
            print(f"   - {job.get('code_id')} at {job.get('time')} ({'recurring' if job.get('is_recurring') else 'one-time'})")
    
    # Check health
    print("\n🏥 Checking system health...")
    health = get_health()
    if health:
        print(f"   Status: {health.get('status')}")
        print(f"   Scheduled alarms: {health.get('scheduled_alarms')}")
        print(f"   Thread running: {'✅' if health.get('thread_running') else '❌'}")
        print(f"   Database: {health.get('database')}")
        print(f"   Redis: {health.get('redis')}")
    
    # Monitor for 3 minutes to see alarms trigger
    print(f"\n⏱️ Monitoring for 3 minutes to observe alarm execution...")
    print("   Expected: TEST001 (30s), TEST002 (1m, recurring), TEST003 (2m)")
    print("   Press Ctrl+C to stop monitoring early")
    
    try:
        monitor_alarms(180)  # Monitor for 3 minutes
    except KeyboardInterrupt:
        print("\n⏹️ Test stopped by user")
    
    # Final status
    print("\n📋 Final Status:")
    alarms = get_alarms()
    if alarms:
        remaining = len(alarms.get('alarms', []))
        print(f"   Remaining alarms: {remaining}")
        if remaining > 0:
            print("   Remaining alarms (should be recurring ones):")
            for alarm in alarms.get('alarms', []):
                print(f"     - {alarm.get('code_id')} at {alarm.get('time')}")
    
    print("\n✅ Small scale test completed!")

if __name__ == "__main__":
    run_small_scale_test() 