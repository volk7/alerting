#!/usr/bin/env python3
"""
Test script to load test the alarm server by creating thousands of alarms
that fire at the exact same time.
"""

import requests
import time
import random
from datetime import datetime, timedelta
import threading
from concurrent.futures import ThreadPoolExecutor

# Configuration
ALARM_SERVER_URL = "http://localhost:8000"
NUM_ALARMS = 500  # Number of alarms to create for the load test
CONCURRENT_REQUESTS = 50  # Number of concurrent requests
TRIGGER_DELAY_SECONDS = 30  # Delay before all alarms fire simultaneously

# Global variable to hold the single trigger time for all alarms
SIMULTANEOUS_TRIGGER_TIME = None

def get_simultaneous_trigger_time():
    """Sets a single future time for all alarms to trigger."""
    global SIMULTANEOUS_TRIGGER_TIME
    if SIMULTANEOUS_TRIGGER_TIME is None:
        SIMULTANEOUS_TRIGGER_TIME = datetime.now() + timedelta(seconds=TRIGGER_DELAY_SECONDS)
    return SIMULTANEOUS_TRIGGER_TIME

def generate_load_test_alarm():
    """Generate a load test alarm with a simultaneous trigger time."""
    trigger_time = get_simultaneous_trigger_time()
    
    return {
        "code_id": f"LOAD_TEST_{random.randint(10000, 99999)}",
        "email": f"loadtest{random.randint(1, 1000)}@example.com",
        "time": trigger_time.strftime("%H:%M:%S"),
        "is_recurring": False  # Non-recurring for easier cleanup
    }

def add_single_alarm(alarm_data):
    """Add a single alarm to the server."""
    try:
        response = requests.post(f"{ALARM_SERVER_URL}/alarms/", json=alarm_data, timeout=10)
        if response.status_code != 200:
            print(f"Failed to add alarm {alarm_data['code_id']}: {response.text}")
            return False
        return True
    except requests.exceptions.RequestException as e:
        print(f"Error adding alarm: {e}")
        return False

def run_load_test():
    """Test creating and triggering alarms concurrently."""
    trigger_time = get_simultaneous_trigger_time()
    print(f"🚀 Starting load test: Creating {NUM_ALARMS} alarms...")
    print(f"🔥 All alarms will fire simultaneously at: {trigger_time.strftime('%H:%M:%S')}")
    
    alarms_to_create = [generate_load_test_alarm() for _ in range(NUM_ALARMS)]
    
    start_time = time.time()
    
    with ThreadPoolExecutor(max_workers=CONCURRENT_REQUESTS) as executor:
        results = list(executor.map(add_single_alarm, alarms_to_create))
    
    end_time = time.time()
    duration = end_time - start_time
    
    successful = sum(results)
    failed = NUM_ALARMS - successful
    
    print(f"\n✅ Created {successful} alarms successfully.")
    if failed > 0:
        print(f"❌ Failed to create {failed} alarms.")
    print(f"⏱️  Total creation time: {duration:.2f} seconds")
    print(f"📊 Creation rate: {successful/duration:.2f} alarms/second")
    
    return successful

def test_server_status():
    """Test if the server is running."""
    try:
        response = requests.get(f"{ALARM_SERVER_URL}/alarms/", timeout=5)
        return response.status_code == 200
    except requests.exceptions.ConnectionError:
        return False

def main():
    """Main test function."""
    print("=" * 60)
    print("🔥 ALARM SERVER LOAD TEST: SIMULTANEOUS TRIGGER 🔥")
    print("=" * 60)
    
    if not test_server_status():
        print("❌ Alarm server is not running or not responding.")
        print("   Please ensure the server is started and accessible before running the test.")
        print("   You can start it with: env/Scripts/python alert_server.py run-server")
        return
    
    print("✅ Alarm server is running.")
    
    initial_count_response = requests.get(f"{ALARM_SERVER_URL}/alarms/count")
    initial_count = initial_count_response.json()["count"]
    print(f"📊 Initial alarm count: {initial_count}")
    
    created_count = run_load_test()
    
    if created_count > 0:
        print(f"\n⏳ Waiting for alarms to trigger... (approx. {TRIGGER_DELAY_SECONDS} seconds)")
        print("   Watch the 'alert_server.py' console output to see the alarms firing.")
        
        # Wait until after the trigger time
        time.sleep(TRIGGER_DELAY_SECONDS + 5)
        
        print("\n🎉 Load test complete!")
        
        final_count_response = requests.get(f"{ALARM_SERVER_URL}/alarms/count")
        final_count = final_count_response.json()["count"]
        
        print("\n📈 Results Summary:")
        print(f"   Initial alarms: {initial_count}")
        print(f"   Created alarms: {created_count}")
        print(f"   Final alarms:   {final_count}")
        
        print("\nSince alarms were non-recurring, they should be automatically deleted after firing.")
        print("The final count should be close to the initial count.")
        
        if final_count > initial_count:
             print("   Some test alarms may not have been cleaned up automatically.")
        else:
            print("   All test alarms were automatically cleaned up.")
    else:
        print("\n❌ No alarms were created. The load test could not be performed.")
        print("   Check server logs for errors.")

if __name__ == "__main__":
    main() 