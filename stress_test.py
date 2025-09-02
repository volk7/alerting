#!/usr/bin/env python3
"""
Stress Test for Alarm System
Pushes the system to its limits to test extreme scalability scenarios.
"""

import requests
import time
import json
import random
from datetime import datetime, timedelta
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import statistics

# Configuration
SCHEDULER_URL = "http://localhost:8002"

def stress_test_alarm_creation(max_alarms=10000):
    """Stress test alarm creation with very large numbers"""
    print(f"🔥 STRESS TEST: Creating {max_alarms} alarms...")
    
    start_time = time.time()
    success_count = 0
    error_count = 0
    response_times = []
    
    # Create alarms in batches to avoid overwhelming the system
    batch_size = 1000
    total_batches = (max_alarms + batch_size - 1) // batch_size
    
    for batch_num in range(total_batches):
        batch_start = time.time()
        batch_alarms = min(batch_size, max_alarms - batch_num * batch_size)
        
        print(f"📦 Batch {batch_num + 1}/{total_batches}: {batch_alarms} alarms")
        
        for i in range(batch_alarms):
            alarm_num = batch_num * batch_size + i
            
            # Create alarm for random time in next 24 hours
            future_time = datetime.now() + timedelta(
                hours=random.randint(0, 23),
                minutes=random.randint(0, 59),
                seconds=random.randint(0, 59)
            )
            time_str = f"{future_time.hour:02d}:{future_time.minute:02d}:{future_time.second:02d}"
            
            alarm = {
                "code_id": f"STRESS_{alarm_num:06d}",
                "email": f"stress{alarm_num}@example.com",
                "time": time_str,
                "is_recurring": random.choice([True, False])
            }
            
            try:
                response_start = time.time()
                response = requests.post(f"{SCHEDULER_URL}/schedule/", json=alarm)
                response_time = time.time() - response_start
                response_times.append(response_time)
                
                if response.status_code == 200:
                    success_count += 1
                else:
                    error_count += 1
                    if error_count <= 5:  # Only show first 5 errors
                        print(f"❌ Failed to add alarm {alarm_num}: {response.status_code}")
                        
            except Exception as e:
                error_count += 1
                if error_count <= 5:  # Only show first 5 errors
                    print(f"❌ Error adding alarm {alarm_num}: {e}")
            
            # Progress indicator
            if (i + 1) % 100 == 0:
                elapsed = time.time() - batch_start
                rate = (i + 1) / elapsed if elapsed > 0 else 0
                print(f"   Progress: {i + 1}/{batch_alarms} ({rate:.1f} alarms/sec)")
        
        batch_time = time.time() - batch_start
        print(f"   Batch completed in {batch_time:.2f}s")
        
        # Check performance after each batch
        try:
            response = requests.get(f"{SCHEDULER_URL}/debug/performance")
            if response.status_code == 200:
                perf_data = response.json()
                print(f"   Current: {perf_data['alarm_count']} alarms, {perf_data['estimated_memory_mb']:.2f} MB")
        except:
            pass
    
    total_time = time.time() - start_time
    
    print(f"\n🔥 STRESS TEST RESULTS:")
    print(f"   Total alarms: {success_count + error_count}")
    print(f"   Success: {success_count}")
    print(f"   Errors: {error_count}")
    print(f"   Success rate: {success_count/(success_count + error_count)*100:.1f}%")
    print(f"   Total time: {total_time:.2f}s")
    print(f"   Average rate: {success_count/total_time:.1f} alarms/sec")
    print(f"   Avg response time: {statistics.mean(response_times):.3f}s")
    print(f"   Max response time: {max(response_times):.3f}s")
    
    return {
        "total_alarms": success_count + error_count,
        "success_count": success_count,
        "error_count": error_count,
        "total_time": total_time,
        "avg_rate": success_count/total_time,
        "avg_response_time": statistics.mean(response_times),
        "max_response_time": max(response_times)
    }

def stress_test_concurrent_requests(max_concurrent=500):
    """Stress test with very high concurrency"""
    print(f"⚡ STRESS TEST: {max_concurrent} concurrent requests...")
    
    results = []
    lock = threading.Lock()
    
    def make_request(i):
        # Create alarm for near future
        future_time = datetime.now() + timedelta(minutes=random.randint(1, 10))
        time_str = f"{future_time.hour:02d}:{future_time.minute:02d}:{future_time.second:02d}"
        
        alarm = {
            "code_id": f"CONCURRENT_STRESS_{i:06d}",
            "email": f"concurrent_stress{i}@example.com",
            "time": time_str,
            "is_recurring": False
        }
        
        start_time = time.time()
        try:
            response = requests.post(f"{SCHEDULER_URL}/schedule/", json=alarm, timeout=10)
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
    
    # Use ThreadPoolExecutor for controlled concurrency
    start_time = time.time()
    
    with ThreadPoolExecutor(max_workers=50) as executor:  # Limit to 50 workers
        futures = []
        for i in range(max_concurrent):
            future = executor.submit(make_request, i)
            futures.append(future)
        
        # Wait for all to complete
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                print(f"❌ Future error: {e}")
    
    total_time = time.time() - start_time
    success_count = sum(1 for r in results if r["success"])
    response_times = [r["response_time"] for r in results]
    
    print(f"\n⚡ CONCURRENT STRESS TEST RESULTS:")
    print(f"   Total requests: {len(results)}")
    print(f"   Success: {success_count}")
    print(f"   Errors: {len(results) - success_count}")
    print(f"   Success rate: {success_count/len(results)*100:.1f}%")
    print(f"   Total time: {total_time:.2f}s")
    print(f"   Requests/sec: {len(results)/total_time:.1f}")
    print(f"   Avg response time: {statistics.mean(response_times):.3f}s")
    print(f"   Max response time: {max(response_times):.3f}s")
    
    return {
        "total_requests": len(results),
        "success_count": success_count,
        "error_count": len(results) - success_count,
        "total_time": total_time,
        "requests_per_second": len(results)/total_time,
        "avg_response_time": statistics.mean(response_times),
        "max_response_time": max(response_times)
    }

def stress_test_memory_usage():
    """Test memory usage under extreme load"""
    print("🧠 STRESS TEST: Memory usage under extreme load...")
    
    # Get baseline
    try:
        response = requests.get(f"{SCHEDULER_URL}/debug/scheduler-stats")
        if response.status_code == 200:
            baseline = response.json()
            print(f"📊 Baseline: {baseline['total_alarms']} alarms, {baseline['memory_usage_estimate_mb']:.2f} MB")
        else:
            baseline = None
    except:
        baseline = None
    
    # Add alarms in increasing batches
    batch_sizes = [1000, 2000, 5000, 10000]
    memory_results = []
    
    for batch_size in batch_sizes:
        print(f"\n📦 Adding {batch_size} alarms...")
        
        # Get performance before
        try:
            response = requests.get(f"{SCHEDULER_URL}/debug/performance")
            if response.status_code == 200:
                before_perf = response.json()
            else:
                before_perf = None
        except:
            before_perf = None
        
        # Add alarms
        start_time = time.time()
        success_count = 0
        
        for i in range(batch_size):
            future_time = datetime.now() + timedelta(
                hours=random.randint(0, 23),
                minutes=random.randint(0, 59),
                seconds=random.randint(0, 59)
            )
            time_str = f"{future_time.hour:02d}:{future_time.minute:02d}:{future_time.second:02d}"
            
            alarm = {
                "code_id": f"MEMORY_STRESS_{len(memory_results)}_{i:06d}",
                "email": f"memory_stress_{len(memory_results)}_{i}@example.com",
                "time": time_str,
                "is_recurring": random.choice([True, False])
            }
            
            try:
                response = requests.post(f"{SCHEDULER_URL}/schedule/", json=alarm)
                if response.status_code == 200:
                    success_count += 1
            except:
                pass
        
        add_time = time.time() - start_time
        
        # Get performance after
        try:
            response = requests.get(f"{SCHEDULER_URL}/debug/performance")
            if response.status_code == 200:
                after_perf = response.json()
            else:
                after_perf = None
        except:
            after_perf = None
        
        if before_perf and after_perf:
            memory_increase = after_perf['estimated_memory_mb'] - before_perf['estimated_memory_mb']
            print(f"   Added: {success_count}/{batch_size} alarms")
            print(f"   Time: {add_time:.2f}s")
            print(f"   Rate: {success_count/add_time:.1f} alarms/sec")
            print(f"   Memory increase: {memory_increase:.2f} MB")
            print(f"   Total memory: {after_perf['estimated_memory_mb']:.2f} MB")
            
            memory_results.append({
                "batch_size": batch_size,
                "success_count": success_count,
                "add_time": add_time,
                "add_rate": success_count/add_time,
                "memory_increase": memory_increase,
                "total_memory": after_perf['estimated_memory_mb'],
                "total_alarms": after_perf['alarm_count']
            })
    
    return memory_results

def stress_test_alarm_triggering_under_load():
    """Test alarm triggering performance under heavy load"""
    print("🔔 STRESS TEST: Alarm triggering under heavy load...")
    
    # First, add a large number of alarms
    print("📅 Adding 5000 background alarms...")
    background_alarms = 5000
    
    for i in range(background_alarms):
        future_time = datetime.now() + timedelta(
            hours=random.randint(1, 23),
            minutes=random.randint(0, 59),
            seconds=random.randint(0, 59)
        )
        time_str = f"{future_time.hour:02d}:{future_time.minute:02d}:{future_time.second:02d}"
        
        alarm = {
            "code_id": f"BACKGROUND_{i:06d}",
            "email": f"background{i}@example.com",
            "time": time_str,
            "is_recurring": False
        }
        
        try:
            response = requests.post(f"{SCHEDULER_URL}/schedule/", json=alarm)
        except:
            pass
    
    print("✅ Background alarms added")
    
    # Now add test alarms that will trigger soon
    print("🔔 Adding 50 test alarms for the next minute...")
    test_alarms = []
    current_time = datetime.now()
    
    for i in range(50):
        future_time = current_time + timedelta(seconds=random.randint(10, 60))
        time_str = f"{future_time.hour:02d}:{future_time.minute:02d}:{future_time.second:02d}"
        
        alarm = {
            "code_id": f"TRIGGER_STRESS_{i}",
            "email": f"trigger_stress{i}@example.com",
            "time": time_str,
            "is_recurring": False
        }
        test_alarms.append(alarm)
    
    # Add test alarms
    success_count = 0
    for alarm in test_alarms:
        try:
            response = requests.post(f"{SCHEDULER_URL}/schedule/", json=alarm)
            if response.status_code == 200:
                success_count += 1
                print(f"✅ Added trigger test alarm: {alarm['time']}")
        except Exception as e:
            print(f"❌ Failed to add trigger test alarm: {e}")
    
    print(f"✅ Added {success_count}/50 trigger test alarms")
    
    # Wait for alarms to trigger
    print("⏰ Waiting for alarms to trigger (70 seconds)...")
    time.sleep(70)
    
    # Check final performance
    try:
        response = requests.get(f"{SCHEDULER_URL}/debug/performance")
        if response.status_code == 200:
            final_perf = response.json()
            print(f"📊 Final performance:")
            print(f"   Total alarms: {final_perf['alarm_count']}")
            print(f"   Memory: {final_perf['estimated_memory_mb']:.2f} MB")
            print(f"   Performance tier: {final_perf['performance_tier']}")
            return final_perf
    except Exception as e:
        print(f"❌ Error getting final performance: {e}")
        return None

def main():
    """Run all stress tests"""
    print("🔥 Starting Stress Tests")
    print("=" * 60)
    
    # Test 1: Extreme alarm creation
    print("🔥 Test 1: Extreme Alarm Creation (10,000 alarms)")
    creation_result = stress_test_alarm_creation(10000)
    
    print("\n" + "=" * 60)
    
    # Test 2: Extreme concurrency
    print("🔥 Test 2: Extreme Concurrency (500 requests)")
    concurrency_result = stress_test_concurrent_requests(500)
    
    print("\n" + "=" * 60)
    
    # Test 3: Memory stress
    print("🔥 Test 3: Memory Stress Test")
    memory_result = stress_test_memory_usage()
    
    print("\n" + "=" * 60)
    
    # Test 4: Alarm triggering under load
    print("🔥 Test 4: Alarm Triggering Under Load")
    trigger_result = stress_test_alarm_triggering_under_load()
    
    print("\n" + "=" * 60)
    
    # Final summary
    print("📋 STRESS TEST SUMMARY")
    print("=" * 60)
    
    print(f"Alarm Creation Stress Test:")
    print(f"  - Created: {creation_result['success_count']} alarms")
    print(f"  - Success rate: {creation_result['success_count']/creation_result['total_alarms']*100:.1f}%")
    print(f"  - Rate: {creation_result['avg_rate']:.1f} alarms/sec")
    print(f"  - Avg response: {creation_result['avg_response_time']:.3f}s")
    
    print(f"\nConcurrency Stress Test:")
    print(f"  - Requests: {concurrency_result['total_requests']}")
    print(f"  - Success rate: {concurrency_result['success_count']/concurrency_result['total_requests']*100:.1f}%")
    print(f"  - Requests/sec: {concurrency_result['requests_per_second']:.1f}")
    print(f"  - Avg response: {concurrency_result['avg_response_time']:.3f}s")
    
    print(f"\nMemory Stress Test:")
    for result in memory_result:
        print(f"  - {result['batch_size']} alarms: {result['memory_increase']:.2f} MB increase")
    
    if trigger_result:
        print(f"\nTriggering Under Load:")
        print(f"  - Final alarms: {trigger_result['alarm_count']}")
        print(f"  - Memory: {trigger_result['estimated_memory_mb']:.2f} MB")
        print(f"  - Performance: {trigger_result['performance_tier']}")
    
    # Save results
    results = {
        "creation_stress": creation_result,
        "concurrency_stress": concurrency_result,
        "memory_stress": memory_result,
        "triggering_stress": trigger_result
    }
    
    with open("stress_test_results.json", "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"\n💾 Results saved to stress_test_results.json")
    print("\n🔥 Stress tests completed!")

if __name__ == "__main__":
    main() 