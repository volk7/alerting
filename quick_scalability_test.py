#!/usr/bin/env python3
"""
Quick Scalability Test for Alarm System
Simple script to test alarm system performance with different load levels.
"""

import requests
import time
import json
import random
from datetime import datetime, timedelta

# Configuration
SCHEDULER_URL = "http://localhost:8002"

def test_health():
    """Test basic health of the scheduler"""
    print("🔍 Testing scheduler health...")
    try:
        response = requests.get(f"{SCHEDULER_URL}/health")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Health: {data['status']}")
            print(f"   Alarms: {data['scheduled_alarms']}")
            print(f"   Thread: {data['thread_running']}")
            return True
        else:
            print(f"❌ Health check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Health check error: {e}")
        return False

def test_performance():
    """Test current performance metrics"""
    print("📊 Testing performance metrics...")
    try:
        response = requests.get(f"{SCHEDULER_URL}/debug/performance")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Performance: {data['performance_tier']}")
            print(f"   Alarms: {data['alarm_count']}")
            print(f"   Memory: {data['estimated_memory_mb']} MB")
            print(f"   Recommendation: {data['recommendation']}")
            return data
        else:
            print(f"❌ Performance check failed: {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ Performance check error: {e}")
        return None

def add_test_alarms(count, time_offset_minutes=2):
    """Add test alarms that will trigger soon"""
    print(f"📅 Adding {count} test alarms...")
    
    current_time = datetime.now()
    success_count = 0
    start_time = time.time()
    
    for i in range(count):
        # Create alarm for 2-5 minutes from now
        future_time = current_time + timedelta(minutes=time_offset_minutes + random.randint(0, 3))
        time_str = f"{future_time.hour:02d}:{future_time.minute:02d}:{future_time.second:02d}"
        
        alarm = {
            "code_id": f"SCALE_TEST_{i:04d}",
            "email": f"test{i}@example.com",
            "time": time_str,
            "is_recurring": False
        }
        
        try:
            response = requests.post(f"{SCHEDULER_URL}/schedule/", json=alarm)
            if response.status_code == 200:
                success_count += 1
                if i % 100 == 0:
                    print(f"   Added {i+1}/{count} alarms...")
            else:
                print(f"❌ Failed to add alarm {i}: {response.status_code}")
        except Exception as e:
            print(f"❌ Error adding alarm {i}: {e}")
    
    total_time = time.time() - start_time
    print(f"✅ Added {success_count}/{count} alarms in {total_time:.2f}s")
    print(f"   Rate: {success_count/total_time:.1f} alarms/second")
    
    return success_count, total_time

def test_concurrent_requests(count=50):
    """Test concurrent alarm scheduling"""
    print(f"⚡ Testing {count} concurrent requests...")
    
    import threading
    
    results = []
    lock = threading.Lock()
    
    def add_alarm(i):
        current_time = datetime.now()
        future_time = current_time + timedelta(minutes=random.randint(1, 5))
        time_str = f"{future_time.hour:02d}:{future_time.minute:02d}:{future_time.second:02d}"
        
        alarm = {
            "code_id": f"CONCURRENT_{i:04d}",
            "email": f"concurrent{i}@example.com",
            "time": time_str,
            "is_recurring": False
        }
        
        start_time = time.time()
        try:
            response = requests.post(f"{SCHEDULER_URL}/schedule/", json=alarm)
            response_time = time.time() - start_time
            
            with lock:
                results.append({
                    "success": response.status_code == 200,
                    "response_time": response_time,
                    "status_code": response.status_code
                })
        except Exception as e:
            with lock:
                results.append({
                    "success": False,
                    "response_time": time.time() - start_time,
                    "error": str(e)
                })
    
    threads = []
    start_time = time.time()
    
    for i in range(count):
        thread = threading.Thread(target=add_alarm, args=(i,))
        threads.append(thread)
        thread.start()
    
    for thread in threads:
        thread.join()
    
    total_time = time.time() - start_time
    success_count = sum(1 for r in results if r["success"])
    avg_response_time = sum(r["response_time"] for r in results) / len(results)
    
    print(f"✅ Concurrent test completed:")
    print(f"   Success: {success_count}/{count}")
    print(f"   Total time: {total_time:.2f}s")
    print(f"   Avg response: {avg_response_time:.3f}s")
    print(f"   Requests/sec: {count/total_time:.1f}")
    
    return {
        "total": count,
        "success": success_count,
        "total_time": total_time,
        "avg_response_time": avg_response_time,
        "requests_per_second": count/total_time
    }

def test_memory_scaling():
    """Test memory usage at different scales"""
    print("🧠 Testing memory scaling...")
    
    scales = [100, 500, 1000, 2000]
    memory_results = []
    
    for scale in scales:
        print(f"\n📊 Testing with {scale} alarms...")
        
        # Get baseline
        baseline = test_performance()
        if not baseline:
            continue
        
        # Add alarms
        success_count, add_time = add_test_alarms(scale)
        
        # Get new performance
        new_perf = test_performance()
        if not new_perf:
            continue
        
        memory_results.append({
            "alarm_count": new_perf["alarm_count"],
            "memory_mb": new_perf["estimated_memory_mb"],
            "add_time": add_time,
            "add_rate": success_count/add_time if add_time > 0 else 0
        })
        
        print(f"   Memory increase: {new_perf['estimated_memory_mb'] - baseline['estimated_memory_mb']:.2f} MB")
        print(f"   Add rate: {success_count/add_time:.1f} alarms/sec")
    
    return memory_results

def test_alarm_triggering():
    """Test alarm triggering performance"""
    print("🔔 Testing alarm triggering...")
    
    # Add 10 test alarms for the next minute
    current_time = datetime.now()
    test_alarms = []
    
    for i in range(10):
        future_time = current_time + timedelta(seconds=random.randint(10, 30))
        time_str = f"{future_time.hour:02d}:{future_time.minute:02d}:{future_time.second:02d}"
        
        alarm = {
            "code_id": f"TRIGGER_TEST_{i}",
            "email": f"trigger{i}@example.com",
            "time": time_str,
            "is_recurring": False
        }
        test_alarms.append(alarm)
    
    # Add alarms
    for alarm in test_alarms:
        try:
            response = requests.post(f"{SCHEDULER_URL}/schedule/", json=alarm)
            if response.status_code == 200:
                print(f"✅ Added trigger test alarm: {alarm['time']}")
            else:
                print(f"❌ Failed to add trigger test alarm: {response.status_code}")
        except Exception as e:
            print(f"❌ Error adding trigger test alarm: {e}")
    
    # Wait for alarms to trigger
    print("⏰ Waiting for alarms to trigger (35 seconds)...")
    time.sleep(35)
    
    # Check final stats
    final_perf = test_performance()
    return final_perf

def main():
    """Run all scalability tests"""
    print("🚀 Starting Quick Scalability Tests")
    print("=" * 50)
    
    # Test 1: Health check
    if not test_health():
        print("❌ Health check failed. Stopping tests.")
        return
    
    print("\n" + "=" * 50)
    
    # Test 2: Baseline performance
    baseline = test_performance()
    
    print("\n" + "=" * 50)
    
    # Test 3: Small scale (100 alarms)
    print("📊 Test 3: Small Scale (100 alarms)")
    small_success, small_time = add_test_alarms(100)
    small_perf = test_performance()
    
    print("\n" + "=" * 50)
    
    # Test 4: Medium scale (500 alarms)
    print("📊 Test 4: Medium Scale (500 alarms)")
    medium_success, medium_time = add_test_alarms(500)
    medium_perf = test_performance()
    
    print("\n" + "=" * 50)
    
    # Test 5: Concurrent requests
    print("📊 Test 5: Concurrent Requests")
    concurrent_result = test_concurrent_requests(100)
    
    print("\n" + "=" * 50)
    
    # Test 6: Memory scaling
    print("📊 Test 6: Memory Scaling")
    memory_results = test_memory_scaling()
    
    print("\n" + "=" * 50)
    
    # Test 7: Alarm triggering
    print("📊 Test 7: Alarm Triggering")
    trigger_result = test_alarm_triggering()
    
    print("\n" + "=" * 50)
    
    # Summary
    print("📋 SCALABILITY TEST SUMMARY")
    print("=" * 50)
    
    if baseline:
        print(f"Baseline:")
        print(f"  - Alarms: {baseline['alarm_count']}")
        print(f"  - Memory: {baseline['estimated_memory_mb']} MB")
        print(f"  - Tier: {baseline['performance_tier']}")
    
    if small_perf:
        print(f"\nSmall Scale (100 alarms):")
        print(f"  - Add rate: {small_success/small_time:.1f} alarms/sec")
        print(f"  - Memory: {small_perf['estimated_memory_mb']} MB")
    
    if medium_perf:
        print(f"\nMedium Scale (500 alarms):")
        print(f"  - Add rate: {medium_success/medium_time:.1f} alarms/sec")
        print(f"  - Memory: {medium_perf['estimated_memory_mb']} MB")
    
    print(f"\nConcurrent Performance:")
    print(f"  - Requests/sec: {concurrent_result['requests_per_second']:.1f}")
    print(f"  - Success rate: {concurrent_result['success']/concurrent_result['total']*100:.1f}%")
    
    # Save results
    results = {
        "baseline": baseline,
        "small_scale": {
            "success_count": small_success,
            "time": small_time,
            "performance": small_perf
        },
        "medium_scale": {
            "success_count": medium_success,
            "time": medium_time,
            "performance": medium_perf
        },
        "concurrent": concurrent_result,
        "memory_scaling": memory_results,
        "trigger_test": trigger_result
    }
    
    with open("quick_scalability_results.json", "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"\n💾 Results saved to quick_scalability_results.json")
    print("\n✅ Scalability tests completed!")

if __name__ == "__main__":
    main() 