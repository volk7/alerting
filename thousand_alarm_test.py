#!/usr/bin/env python3
"""
Thousand Alarm Test - Simultaneous Firing
Tests the alarm system with 1000 alarms that fire simultaneously
"""

import requests
import time
import json
from datetime import datetime, timedelta
import threading
import random

# Configuration
SCHEDULER_URL = "http://localhost:8002"
DASHBOARD_URL = "http://localhost:5000"

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
            result = response.json()
            if result.get('status') == 'success':
                return True
            else:
                print(f"❌ Failed to add alarm {code_id}: {result.get('message', 'Unknown error')}")
                return False
        else:
            print(f"❌ Failed to add alarm {code_id}: HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error adding alarm {code_id}: {e}")
        return False

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

def get_alarms():
    """Get current alarms"""
    try:
        response = requests.get(f"{SCHEDULER_URL}/jobs/")
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        print(f"❌ Error getting alarms: {e}")
        return None

def monitor_alarms(duration=900):
    """Monitor alarms for a specified duration"""
    print(f"\n🔍 Monitoring alarms for {duration} seconds...")
    start_time = time.time()
    
    while time.time() - start_time < duration:
        try:
            # Get health status
            health = get_health()
            if health:
                status = health.get('status', 'unknown')
                scheduled = health.get('scheduled_alarms', 0)
                thread_running = health.get('thread_running', False)
                print(f"   Health: {status}, Scheduled: {scheduled}, Thread: {'✅' if thread_running else '❌'}")
            
            # Get alarm details
            alarms = get_alarms()
            if alarms:
                jobs = alarms.get('jobs', [])
                if jobs:
                    print(f"   Active alarms: {len(jobs)}")
                    # Show first few alarms
                    for i, job in enumerate(jobs[:3]):
                        print(f"     {i+1}. {job.get('code_id')} at {job.get('time')} (recurring: {job.get('is_recurring')})")
                    if len(jobs) > 3:
                        print(f"     ... and {len(jobs) - 3} more")
                else:
                    print("   No active alarms")
            
            time.sleep(10)  # Check every 10 seconds
            
        except KeyboardInterrupt:
            print("\n⏹️ Monitoring stopped by user")
            break
        except Exception as e:
            print(f"❌ Error during monitoring: {e}")
            time.sleep(10)

def main():
    print("🚀 Starting 1000 Alarm Test - Simultaneous Firing")
    print("=" * 50)
    
    # Get current time
    current_time = datetime.now()
    print(f"⏰ Current time: {current_time.strftime('%H:%M:%S')}")
    
    # Calculate future firing time (10 minutes from now)
    firing_time = current_time + timedelta(minutes=10)
    firing_time_str = firing_time.strftime("%H:%M:%S")
    print(f"🎯 All alarms will fire at: {firing_time_str}")
    
    # Clear any existing alarms first
    print("\n🧹 Clearing existing alarms...")
    try:
        response = requests.delete(f"{SCHEDULER_URL}/jobs/")
        if response.status_code == 200:
            print("✅ Existing alarms cleared")
        else:
            print(f"⚠️ Could not clear alarms: {response.status_code}")
    except Exception as e:
        print(f"⚠️ Error clearing alarms: {e}")
    
    # Add 1000 test alarms that all fire simultaneously
    print(f"\n📝 Adding 1000 test alarms (all firing at {firing_time_str})...")
    alarms_added = 0
    
    # Create 1000 non-recurring alarms that all fire at the same time
    for i in range(1000):
        # All alarms fire at the same time
        time_str = firing_time_str
        
        # All alarms are non-recurring for this test
        is_recurring = False
        
        code_id = f"THOUSAND_{i+1:04d}"
        email = f"test{i+1}@example.com"
        
        if add_test_alarm(code_id, email, time_str, is_recurring):
            alarms_added += 1
            if alarms_added % 100 == 0:
                print(f"   ✅ Added {alarms_added} alarms...")
        
        # Small delay to avoid overwhelming the system
        time.sleep(0.05)
    
    print(f"\n✅ Added {alarms_added} test alarms")
    
    # Verify alarms were added
    print("\n🔍 Verifying alarms...")
    alarms = get_alarms()
    if alarms:
        total_jobs = alarms.get('total_jobs', 0)
        print(f"📊 Found {total_jobs} alarms in system")
        
        # Show sample of alarms
        jobs = alarms.get('jobs', [])
        if jobs:
            print("📋 Sample alarms:")
            for i, job in enumerate(jobs[:5]):
                print(f"   {i+1}. {job.get('code_id')} at {job.get('time')} (recurring: {job.get('is_recurring')})")
            if len(jobs) > 5:
                print(f"   ... and {len(jobs) - 5} more")
    
    # Calculate monitoring duration (10 minutes to firing + 5 minutes after)
    monitoring_duration = 900  # 15 minutes total
    print(f"\n⏰ Starting {monitoring_duration//60}-minute monitoring period...")
    print(f"   Alarms will fire in ~10 minutes at {firing_time_str}")
    print("Press Ctrl+C to stop monitoring early")
    
    try:
        monitor_alarms(monitoring_duration)
    except KeyboardInterrupt:
        print("\n⏹️ Monitoring stopped by user")
    
    # Final status
    print("\n📊 Final Status:")
    health = get_health()
    if health:
        status = health.get('status', 'unknown')
        scheduled = health.get('scheduled_alarms', 0)
        thread_running = health.get('thread_running', False)
        print(f"   Health: {status}")
        print(f"   Scheduled Alarms: {scheduled}")
        print(f"   Thread Running: {'✅' if thread_running else '❌'}")
    
    print("\n🎉 1000 Alarm Test Complete!")

if __name__ == "__main__":
    main() 