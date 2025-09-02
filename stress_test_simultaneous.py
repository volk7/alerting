#!/usr/bin/env python3
"""
Stress Test - Simultaneous Alarms
Comprehensive stress test for simultaneous alarm firing
"""

import requests
import time
import json
from datetime import datetime, timedelta
import threading
import random
import psutil
import os

# Configuration
SCHEDULER_URL = "http://localhost:8002"
DASHBOARD_URL = "http://localhost:5000"

# Stress test parameters
ALARM_COUNTS = [100, 500, 1000, 2000, 5000]  # Test different alarm counts
SIMULTANEOUS_DELAY = 30  # All alarms fire in 30 seconds

def get_current_time():
    """Get current time in HH:MM:SS format"""
    return datetime.now().strftime("%H:%M:%S")

def get_system_stats():
    """Get current system resource usage"""
    try:
        process = psutil.Process(os.getpid())
        memory_info = process.memory_info()
        cpu_percent = process.cpu_percent()
        return {
            'memory_mb': memory_info.rss / 1024 / 1024,
            'cpu_percent': cpu_percent
        }
    except Exception as e:
        return {'memory_mb': 0, 'cpu_percent': 0}

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
                return False
        else:
            return False
    except Exception as e:
        return False

def get_health():
    """Get scheduler health"""
    try:
        response = requests.get(f"{SCHEDULER_URL}/health")
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        return None

def get_alarms():
    """Get current alarms"""
    try:
        response = requests.get(f"{SCHEDULER_URL}/jobs/")
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        return None

def clear_alarms():
    """Clear all alarms"""
    try:
        response = requests.delete(f"{SCHEDULER_URL}/jobs/")
        return response.status_code == 200
    except Exception as e:
        return False

def run_single_stress_test(alarm_count, test_name):
    """Run a single stress test with specified alarm count"""
    print(f"\n🚀 {test_name}")
    print("=" * 60)
    
    # Get initial system stats
    initial_stats = get_system_stats()
    print(f"📊 Initial Memory: {initial_stats['memory_mb']:.1f} MB, CPU: {initial_stats['cpu_percent']:.1f}%")
    
    # Clear existing alarms
    print(f"🧹 Clearing existing alarms...")
    if clear_alarms():
        print("✅ Alarms cleared")
    else:
        print("⚠️ Could not clear alarms")
    
    # Get current time
    current_time = datetime.now()
    print(f"⏰ Current time: {current_time.strftime('%H:%M:%S')}")
    print(f"📝 Adding {alarm_count} alarms (all firing in {SIMULTANEOUS_DELAY} seconds)...")
    
    # Add alarms
    start_time = time.time()
    alarms_added = 0
    
    for i in range(alarm_count):
        # All alarms fire at the same time
        alarm_time = current_time + timedelta(seconds=SIMULTANEOUS_DELAY)
        time_str = alarm_time.strftime("%H:%M:%S")
        
        code_id = f"STRESS_{test_name}_{i+1:06d}"
        email = f"stress{i+1}@test.com"
        
        if add_test_alarm(code_id, email, time_str, is_recurring=False):
            alarms_added += 1
            if alarms_added % 100 == 0:
                print(f"   ✅ Added {alarms_added} alarms...")
    
    creation_time = time.time() - start_time
    print(f"✅ Added {alarms_added}/{alarm_count} alarms in {creation_time:.2f} seconds")
    print(f"📈 Creation rate: {alarms_added/creation_time:.1f} alarms/second")
    
    # Verify alarms were added
    alarms = get_alarms()
    if alarms:
        total_jobs = alarms.get('total_jobs', 0)
        print(f"📊 Verified {total_jobs} alarms in system")
    
    # Monitor during the critical period (before, during, and after firing)
    print(f"\n🔍 Monitoring system during stress test...")
    print("Press Ctrl+C to stop monitoring early")
    
    monitoring_start = time.time()
    max_memory = 0
    max_cpu = 0
    alarm_count_history = []
    
    try:
        while time.time() - monitoring_start < 120:  # Monitor for 2 minutes
            current_time_monitoring = time.time()
            elapsed = current_time_monitoring - monitoring_start
            
            # Get system stats
            stats = get_system_stats()
            max_memory = max(max_memory, stats['memory_mb'])
            max_cpu = max(max_cpu, stats['cpu_percent'])
            
            # Get alarm count
            alarms = get_alarms()
            current_alarm_count = alarms.get('total_jobs', 0) if alarms else 0
            alarm_count_history.append((elapsed, current_alarm_count))
            
            # Get health
            health = get_health()
            status = health.get('status', 'unknown') if health else 'unknown'
            thread_running = health.get('thread_running', False) if health else False
            
            print(f"   {elapsed:5.1f}s: Alarms={current_alarm_count:4d}, Memory={stats['memory_mb']:6.1f}MB, CPU={stats['cpu_percent']:5.1f}%, Status={status}, Thread={'✅' if thread_running else '❌'}")
            
            # Check if we're past the firing time
            if elapsed > SIMULTANEOUS_DELAY + 10:  # 10 seconds after firing
                if current_alarm_count == 0:
                    print(f"   ✅ All alarms fired and cleaned up successfully!")
                    break
            
            time.sleep(5)  # Check every 5 seconds
            
    except KeyboardInterrupt:
        print("\n⏹️ Monitoring stopped by user")
    
    # Final stats
    final_stats = get_system_stats()
    final_alarms = get_alarms()
    final_alarm_count = final_alarms.get('total_jobs', 0) if final_alarms else 0
    
    print(f"\n📊 {test_name} Results:")
    print(f"   ✅ Alarms Created: {alarms_added}/{alarm_count}")
    print(f"   ⏱️ Creation Time: {creation_time:.2f} seconds")
    print(f"   📈 Creation Rate: {alarms_added/creation_time:.1f} alarms/second")
    print(f"   🧠 Max Memory: {max_memory:.1f} MB")
    print(f"   🔥 Max CPU: {max_cpu:.1f}%")
    print(f"   📊 Final Memory: {final_stats['memory_mb']:.1f} MB")
    print(f"   🔥 Final CPU: {final_stats['cpu_percent']:.1f}%")
    print(f"   🚨 Final Alarms: {final_alarm_count}")
    
    return {
        'test_name': test_name,
        'alarm_count': alarm_count,
        'alarms_created': alarms_added,
        'creation_time': creation_time,
        'creation_rate': alarms_added/creation_time if creation_time > 0 else 0,
        'max_memory': max_memory,
        'max_cpu': max_cpu,
        'final_alarms': final_alarm_count,
        'success': final_alarm_count == 0  # Success if all alarms fired and were cleaned up
    }

def main():
    print("🚀 Starting Simultaneous Alarm Stress Test")
    print("=" * 80)
    print("This test will push the system to its limits with simultaneous alarm firing")
    print("=" * 80)
    
    # Get initial system status
    print(f"\n📋 Initial System Status:")
    health = get_health()
    if health:
        status = health.get('status', 'unknown')
        thread_running = health.get('thread_running', False)
        print(f"   Status: {status}")
        print(f"   Thread Running: {'✅' if thread_running else '❌'}")
    
    # Run stress tests
    results = []
    
    for alarm_count in ALARM_COUNTS:
        test_name = f"STRESS_TEST_{alarm_count}_ALARMS"
        result = run_single_stress_test(alarm_count, test_name)
        results.append(result)
        
        # Wait between tests
        if alarm_count != ALARM_COUNTS[-1]:  # Not the last test
            print(f"\n⏳ Waiting 10 seconds before next test...")
            time.sleep(10)
    
    # Summary report
    print(f"\n🎉 STRESS TEST COMPLETE")
    print("=" * 80)
    print(f"📊 Summary Report:")
    print("=" * 80)
    
    for result in results:
        status = "✅ PASS" if result['success'] else "❌ FAIL"
        print(f"{status} {result['test_name']}:")
        print(f"   Alarms: {result['alarms_created']}/{result['alarm_count']}")
        print(f"   Rate: {result['creation_rate']:.1f} alarms/sec")
        print(f"   Max Memory: {result['max_memory']:.1f} MB")
        print(f"   Max CPU: {result['max_cpu']:.1f}%")
        print(f"   Final Alarms: {result['final_alarms']}")
        print()
    
    # Overall assessment
    successful_tests = sum(1 for r in results if r['success'])
    total_tests = len(results)
    
    print(f"📈 Overall Results:")
    print(f"   Tests Passed: {successful_tests}/{total_tests}")
    print(f"   Success Rate: {successful_tests/total_tests*100:.1f}%")
    
    if successful_tests == total_tests:
        print(f"🎉 ALL TESTS PASSED! System is ready for production use.")
    elif successful_tests > total_tests / 2:
        print(f"⚠️ Most tests passed. System has good performance but may need optimization.")
    else:
        print(f"❌ Many tests failed. System needs optimization for high load.")
    
    print(f"\n🚀 Stress test complete!")

if __name__ == "__main__":
    main() 