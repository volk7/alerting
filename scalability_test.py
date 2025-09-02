#!/usr/bin/env python3
"""
Scalability Testing Script for Alarm System
Tests the performance and scalability of the alarm scheduler with various load levels.
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
API_GATEWAY_URL = "http://localhost:8000"
BASE_EMAIL = "test@example.com"

class ScalabilityTester:
    def __init__(self):
        self.results = []
        self.test_alarms = []
        
    def test_basic_functionality(self):
        """Test basic alarm functionality"""
        print("🔍 Testing basic functionality...")
        
        # Test health endpoint
        try:
            response = requests.get(f"{SCHEDULER_URL}/health")
            if response.status_code == 200:
                health_data = response.json()
                print(f"✅ Health check passed: {health_data['status']}")
                print(f"   Scheduled alarms: {health_data['scheduled_alarms']}")
                print(f"   Thread running: {health_data['thread_running']}")
            else:
                print(f"❌ Health check failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Health check error: {e}")
            return False
        
        # Test performance metrics
        try:
            response = requests.get(f"{SCHEDULER_URL}/debug/performance")
            if response.status_code == 200:
                perf_data = response.json()
                print(f"📊 Performance tier: {perf_data['performance_tier']}")
                print(f"   Recommendation: {perf_data['recommendation']}")
            else:
                print(f"❌ Performance check failed: {response.status_code}")
        except Exception as e:
            print(f"❌ Performance check error: {e}")
        
        return True
    
    def generate_test_alarms(self, count, time_distribution="random"):
        """Generate test alarms with different time distributions"""
        print(f"📅 Generating {count} test alarms...")
        
        alarms = []
        current_time = datetime.now()
        
        for i in range(count):
            # Generate different time distributions
            if time_distribution == "random":
                # Random times throughout the day
                hour = random.randint(0, 23)
                minute = random.randint(0, 59)
                second = random.randint(0, 59)
            elif time_distribution == "near_future":
                # Alarms in the next few minutes
                future_time = current_time + timedelta(minutes=random.randint(1, 10))
                hour = future_time.hour
                minute = future_time.minute
                second = future_time.second
            elif time_distribution == "peak_hours":
                # Alarms during peak hours (9-17)
                hour = random.randint(9, 17)
                minute = random.randint(0, 59)
                second = random.randint(0, 59)
            else:
                # Default to random
                hour = random.randint(0, 23)
                minute = random.randint(0, 59)
                second = random.randint(0, 59)
            
            time_str = f"{hour:02d}:{minute:02d}:{second:02d}"
            
            alarm = {
                "code_id": f"SCALE_TEST_{i:06d}",
                "email": f"test{i}@example.com",
                "time": time_str,
                "is_recurring": random.choice([True, False])
            }
            alarms.append(alarm)
        
        return alarms
    
    def add_alarm_batch(self, alarms, batch_size=100):
        """Add alarms in batches"""
        print(f"📤 Adding {len(alarms)} alarms in batches of {batch_size}...")
        
        start_time = time.time()
        success_count = 0
        error_count = 0
        response_times = []
        
        for i in range(0, len(alarms), batch_size):
            batch = alarms[i:i + batch_size]
            batch_start = time.time()
            
            for alarm in batch:
                try:
                    response_start = time.time()
                    response = requests.post(f"{SCHEDULER_URL}/schedule/", json=alarm)
                    response_time = time.time() - response_start
                    response_times.append(response_time)
                    
                    if response.status_code == 200:
                        success_count += 1
                    else:
                        error_count += 1
                        print(f"❌ Failed to add alarm {alarm['code_id']}: {response.status_code}")
                        
                except Exception as e:
                    error_count += 1
                    print(f"❌ Error adding alarm {alarm['code_id']}: {e}")
            
            batch_time = time.time() - batch_start
            print(f"   Batch {i//batch_size + 1}: {len(batch)} alarms in {batch_time:.2f}s")
        
        total_time = time.time() - start_time
        
        return {
            "total_alarms": len(alarms),
            "success_count": success_count,
            "error_count": error_count,
            "total_time": total_time,
            "avg_response_time": statistics.mean(response_times) if response_times else 0,
            "max_response_time": max(response_times) if response_times else 0,
            "min_response_time": min(response_times) if response_times else 0
        }
    
    def test_concurrent_requests(self, num_requests=100, max_workers=10):
        """Test concurrent alarm scheduling"""
        print(f"⚡ Testing {num_requests} concurrent requests with {max_workers} workers...")
        
        alarms = self.generate_test_alarms(num_requests, "near_future")
        
        start_time = time.time()
        success_count = 0
        error_count = 0
        response_times = []
        
        def add_single_alarm(alarm):
            try:
                response_start = time.time()
                response = requests.post(f"{SCHEDULER_URL}/schedule/", json=alarm)
                response_time = time.time() - response_start
                
                if response.status_code == 200:
                    return {"success": True, "response_time": response_time}
                else:
                    return {"success": False, "response_time": response_time, "error": response.status_code}
            except Exception as e:
                return {"success": False, "response_time": 0, "error": str(e)}
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_alarm = {executor.submit(add_single_alarm, alarm): alarm for alarm in alarms}
            
            for future in as_completed(future_to_alarm):
                result = future.result()
                response_times.append(result["response_time"])
                
                if result["success"]:
                    success_count += 1
                else:
                    error_count += 1
        
        total_time = time.time() - start_time
        
        return {
            "total_requests": num_requests,
            "success_count": success_count,
            "error_count": error_count,
            "total_time": total_time,
            "requests_per_second": num_requests / total_time,
            "avg_response_time": statistics.mean(response_times) if response_times else 0,
            "max_response_time": max(response_times) if response_times else 0,
            "min_response_time": min(response_times) if response_times else 0
        }
    
    def test_memory_usage(self):
        """Test memory usage under load"""
        print("🧠 Testing memory usage...")
        
        try:
            response = requests.get(f"{SCHEDULER_URL}/debug/scheduler-stats")
            if response.status_code == 200:
                stats = response.json()
                print(f"📊 Memory usage: {stats['memory_usage_estimate_mb']} MB")
                print(f"   Total alarms: {stats['total_alarms']}")
                print(f"   Time index size: {stats['time_index_size']}")
                return stats
            else:
                print(f"❌ Failed to get scheduler stats: {response.status_code}")
                return None
        except Exception as e:
            print(f"❌ Error getting scheduler stats: {e}")
            return None
    
    def test_alarm_triggering(self, num_test_alarms=10):
        """Test alarm triggering performance"""
        print(f"🔔 Testing alarm triggering with {num_test_alarms} test alarms...")
        
        # Create test alarms for the next minute
        current_time = datetime.now()
        test_alarms = []
        
        for i in range(num_test_alarms):
            future_time = current_time + timedelta(seconds=random.randint(5, 30))
            time_str = f"{future_time.hour:02d}:{future_time.minute:02d}:{future_time.second:02d}"
            
            alarm = {
                "code_id": f"TRIGGER_TEST_{i}",
                "email": f"trigger{i}@example.com",
                "time": time_str,
                "is_recurring": False
            }
            test_alarms.append(alarm)
        
        # Add test alarms
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
        print("⏰ Waiting for alarms to trigger...")
        time.sleep(35)  # Wait for all alarms to trigger
        
        # Check final stats
        try:
            response = requests.get(f"{SCHEDULER_URL}/debug/performance")
            if response.status_code == 200:
                perf_data = response.json()
                print(f"📊 Final alarm count: {perf_data['alarm_count']}")
                return perf_data
            else:
                print(f"❌ Failed to get final performance data: {response.status_code}")
                return None
        except Exception as e:
            print(f"❌ Error getting final performance data: {e}")
            return None
    
    def run_scalability_tests(self):
        """Run comprehensive scalability tests"""
        print("🚀 Starting Scalability Tests")
        print("=" * 50)
        
        # Test 1: Basic functionality
        if not self.test_basic_functionality():
            print("❌ Basic functionality test failed. Stopping tests.")
            return
        
        print("\n" + "=" * 50)
        
        # Test 2: Small load (100 alarms)
        print("📊 Test 2: Small Load (100 alarms)")
        small_alarms = self.generate_test_alarms(100, "random")
        small_result = self.add_alarm_batch(small_alarms, batch_size=50)
        print(f"✅ Small load test completed:")
        print(f"   Success: {small_result['success_count']}/{small_result['total_alarms']}")
        print(f"   Time: {small_result['total_time']:.2f}s")
        print(f"   Avg response: {small_result['avg_response_time']:.3f}s")
        
        # Check memory usage
        small_memory = self.test_memory_usage()
        
        print("\n" + "=" * 50)
        
        # Test 3: Medium load (1,000 alarms)
        print("📊 Test 3: Medium Load (1,000 alarms)")
        medium_alarms = self.generate_test_alarms(1000, "random")
        medium_result = self.add_alarm_batch(medium_alarms, batch_size=100)
        print(f"✅ Medium load test completed:")
        print(f"   Success: {medium_result['success_count']}/{medium_result['total_alarms']}")
        print(f"   Time: {medium_result['total_time']:.2f}s")
        print(f"   Avg response: {medium_result['avg_response_time']:.3f}s")
        
        # Check memory usage
        medium_memory = self.test_memory_usage()
        
        print("\n" + "=" * 50)
        
        # Test 4: Large load (10,000 alarms)
        print("📊 Test 4: Large Load (10,000 alarms)")
        large_alarms = self.generate_test_alarms(10000, "random")
        large_result = self.add_alarm_batch(large_alarms, batch_size=500)
        print(f"✅ Large load test completed:")
        print(f"   Success: {large_result['success_count']}/{large_result['total_alarms']}")
        print(f"   Time: {large_result['total_time']:.2f}s")
        print(f"   Avg response: {large_result['avg_response_time']:.3f}s")
        
        # Check memory usage
        large_memory = self.test_memory_usage()
        
        print("\n" + "=" * 50)
        
        # Test 5: Concurrent requests
        print("📊 Test 5: Concurrent Requests")
        concurrent_result = self.test_concurrent_requests(500, 20)
        print(f"✅ Concurrent test completed:")
        print(f"   Success: {concurrent_result['success_count']}/{concurrent_result['total_requests']}")
        print(f"   Requests/sec: {concurrent_result['requests_per_second']:.2f}")
        print(f"   Avg response: {concurrent_result['avg_response_time']:.3f}s")
        
        print("\n" + "=" * 50)
        
        # Test 6: Alarm triggering
        print("📊 Test 6: Alarm Triggering")
        trigger_result = self.test_alarm_triggering(20)
        
        print("\n" + "=" * 50)
        
        # Summary
        print("📋 SCALABILITY TEST SUMMARY")
        print("=" * 50)
        print(f"Small Load (100 alarms):")
        print(f"  - Success Rate: {small_result['success_count']/small_result['total_alarms']*100:.1f}%")
        print(f"  - Memory Usage: {small_memory['memory_usage_estimate_mb'] if small_memory else 'N/A'} MB")
        print(f"  - Avg Response: {small_result['avg_response_time']:.3f}s")
        
        print(f"\nMedium Load (1,000 alarms):")
        print(f"  - Success Rate: {medium_result['success_count']/medium_result['total_alarms']*100:.1f}%")
        print(f"  - Memory Usage: {medium_memory['memory_usage_estimate_mb'] if medium_memory else 'N/A'} MB")
        print(f"  - Avg Response: {medium_result['avg_response_time']:.3f}s")
        
        print(f"\nLarge Load (10,000 alarms):")
        print(f"  - Success Rate: {large_result['success_count']/large_result['total_alarms']*100:.1f}%")
        print(f"  - Memory Usage: {large_memory['memory_usage_estimate_mb'] if large_memory else 'N/A'} MB")
        print(f"  - Avg Response: {large_result['avg_response_time']:.3f}s")
        
        print(f"\nConcurrent Performance:")
        print(f"  - Requests/sec: {concurrent_result['requests_per_second']:.2f}")
        print(f"  - Success Rate: {concurrent_result['success_count']/concurrent_result['total_requests']*100:.1f}%")
        
        # Save results
        self.results = {
            "small_load": small_result,
            "medium_load": medium_result,
            "large_load": large_result,
            "concurrent": concurrent_result,
            "memory_usage": {
                "small": small_memory,
                "medium": medium_memory,
                "large": large_memory
            }
        }
        
        with open("scalability_test_results.json", "w") as f:
            json.dump(self.results, f, indent=2)
        
        print(f"\n💾 Results saved to scalability_test_results.json")

def main():
    """Main function to run scalability tests"""
    tester = ScalabilityTester()
    tester.run_scalability_tests()

if __name__ == "__main__":
    main() 