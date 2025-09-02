#!/usr/bin/env python3
"""
Performance Dashboard for Alarm System
Real-time GUI to monitor and measure alarm system performance.
"""

from flask import Flask, render_template, jsonify, request, redirect, url_for
import requests
import json
import time
import threading
from datetime import datetime, timedelta
import os

app = Flask(__name__)

# Configuration
SCHEDULER_URL = "http://localhost:8002"
API_GATEWAY_URL = "http://localhost:8000"

# Global variables for real-time data
performance_data = {
    "current_alarms": 0,
    "memory_usage": 0.0,
    "performance_tier": "Unknown",
    "response_time": 0.0,
    "last_update": None
}

# Performance history for charts
performance_history = {
    "timestamps": [],
    "alarm_counts": [],
    "memory_usage": [],
    "response_times": []
}

def get_scheduler_health():
    """Get scheduler health status"""
    try:
        response = requests.get(f"{SCHEDULER_URL}/health", timeout=5)
        if response.status_code == 200:
            return response.json()
        else:
            return {"status": "error", "message": f"HTTP {response.status_code}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def get_performance_metrics():
    """Get current performance metrics"""
    try:
        response = requests.get(f"{SCHEDULER_URL}/debug/performance", timeout=5)
        if response.status_code == 200:
            return response.json()
        else:
            return None
    except Exception as e:
        return None

def get_scheduler_stats():
    """Get detailed scheduler statistics"""
    try:
        response = requests.get(f"{SCHEDULER_URL}/debug/scheduler-stats", timeout=5)
        if response.status_code == 200:
            return response.json()
        else:
            return None
    except Exception as e:
        return None

def get_scheduled_alarms():
    """Get list of scheduled alarms"""
    try:
        response = requests.get(f"{SCHEDULER_URL}/jobs/", timeout=5)
        if response.status_code == 200:
            return response.json()
        else:
            return {"jobs": [], "total_jobs": 0}
    except Exception as e:
        return {"jobs": [], "total_jobs": 0}

def measure_response_time():
    """Measure API response time"""
    try:
        start_time = time.time()
        response = requests.get(f"{SCHEDULER_URL}/health", timeout=5)
        response_time = time.time() - start_time
        
        if response.status_code == 200:
            return response_time
        else:
            return None
    except Exception as e:
        return None

def update_performance_data():
    """Update performance data in background"""
    global performance_data, performance_history
    
    while True:
        try:
            # Get current metrics
            health_data = get_scheduler_health()
            perf_data = get_performance_metrics()
            response_time = measure_response_time()
            
            if health_data and health_data.get("status") == "healthy":
                performance_data["current_alarms"] = health_data.get("scheduled_alarms", 0)
                performance_data["last_update"] = datetime.now().strftime("%H:%M:%S")
                
                if perf_data:
                    performance_data["memory_usage"] = perf_data.get("estimated_memory_mb", 0.0)
                    performance_data["performance_tier"] = perf_data.get("performance_tier", "Unknown")
                
                if response_time:
                    performance_data["response_time"] = response_time
                
                # Update history (keep last 100 data points)
                current_time = datetime.now().strftime("%H:%M:%S")
                performance_history["timestamps"].append(current_time)
                performance_history["alarm_counts"].append(performance_data["current_alarms"])
                performance_history["memory_usage"].append(performance_data["memory_usage"])
                performance_history["response_times"].append(performance_data["response_time"])
                
                # Keep only last 100 entries
                if len(performance_history["timestamps"]) > 100:
                    performance_history["timestamps"] = performance_history["timestamps"][-100:]
                    performance_history["alarm_counts"] = performance_history["alarm_counts"][-100:]
                    performance_history["memory_usage"] = performance_history["memory_usage"][-100:]
                    performance_history["response_times"] = performance_history["response_times"][-100:]
            
        except Exception as e:
            print(f"Error updating performance data: {e}")
        
        time.sleep(5)  # Update every 5 seconds

@app.route('/')
def dashboard():
    """Main dashboard page"""
    return render_template('dashboard.html')

@app.route('/api/performance')
def api_performance():
    """API endpoint for performance data"""
    return jsonify(performance_data)

@app.route('/api/history')
def api_history():
    """API endpoint for performance history"""
    return jsonify(performance_history)

@app.route('/api/alarms')
def api_alarms():
    """API endpoint for scheduled alarms"""
    alarms_data = get_scheduled_alarms()
    return jsonify(alarms_data)

@app.route('/api/health')
def api_health():
    """API endpoint for health status"""
    health_data = get_scheduler_health()
    return jsonify(health_data)

@app.route('/api/stats')
def api_stats():
    """API endpoint for detailed stats"""
    stats_data = get_scheduler_stats()
    return jsonify(stats_data)

@app.route('/add_alarm', methods=['GET', 'POST'])
def add_alarm():
    """Add alarm page"""
    if request.method == 'POST':
        try:
            # Generate unique ID if not provided
            code_id = request.form.get('code_id', '').strip()
            if not code_id:
                import time
                import random
                timestamp = int(time.time())
                random_suffix = ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=6))
                code_id = f"ALARM_{timestamp}_{random_suffix}"
            
            alarm_data = {
                "code_id": code_id,
                "email": request.form['email'],
                "time": request.form['time'],
                "is_recurring": 'is_recurring' in request.form
            }
            
            # Add test alarm flag if present
            if 'is_test_alarm' in request.form:
                alarm_data["code_id"] = f"TEST_{alarm_data['code_id']}"
            
            response = requests.post(f"{SCHEDULER_URL}/schedule/", json=alarm_data)
            if response.status_code == 200:
                return jsonify({
                    "status": "success",
                    "message": "Alarm created successfully",
                    "alarm_id": code_id
                })
            else:
                return jsonify({
                    "status": "error",
                    "message": f"Failed to create alarm: {response.status_code}"
                }), 400
        except Exception as e:
            return jsonify({
                "status": "error",
                "message": f"Error: {str(e)}"
            }), 500
    
    return render_template('add_alarm_dashboard.html')

@app.route('/clear_alarms', methods=['POST'])
def clear_alarms():
    """Clear all alarms"""
    try:
        response = requests.delete(f"{SCHEDULER_URL}/jobs/clear")
        if response.status_code == 200:
            return jsonify({"status": "success", "message": "Alarms cleared"})
        else:
            return jsonify({"status": "error", "message": "Failed to clear alarms"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/reload_alarms', methods=['POST'])
def reload_alarms():
    """Reload alarms from database"""
    try:
        response = requests.post(f"{SCHEDULER_URL}/reload")
        if response.status_code == 200:
            return jsonify({"status": "success", "message": "Alarms reloaded"})
        else:
            return jsonify({"status": "error", "message": "Failed to reload alarms"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/test_alarm', methods=['POST'])
def test_alarm():
    """Create a test alarm for current time"""
    try:
        current_time = datetime.now()
        test_time = f"{current_time.hour:02d}:{current_time.minute:02d}:{current_time.second:02d}"
        
        alarm_data = {
            "code_id": f"TEST_{int(time.time())}",
            "email": "test@example.com",
            "time": test_time,
            "is_recurring": False
        }
        
        response = requests.post(f"{SCHEDULER_URL}/schedule/", json=alarm_data)
        if response.status_code == 200:
            return jsonify({"status": "success", "message": f"Test alarm created for {test_time}"})
        else:
            return jsonify({"status": "error", "message": "Failed to create test alarm"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/bulk_alarms', methods=['POST'])
def bulk_alarms():
    """Create multiple test alarms for performance testing"""
    try:
        data = request.get_json()
        count = data.get('count', 10)
        time_offset = data.get('time_offset', 2)  # minutes from now
        
        created_count = 0
        failed_count = 0
        
        for i in range(count):
            try:
                # Create alarm for future time
                future_time = datetime.now() + timedelta(minutes=time_offset + i)
                test_time = f"{future_time.hour:02d}:{future_time.minute:02d}:{future_time.second:02d}"
                
                alarm_data = {
                    "code_id": f"BULK_TEST_{int(time.time())}_{i}",
                    "email": f"bulk_test_{i}@example.com",
                    "time": test_time,
                    "is_recurring": False
                }
                
                response = requests.post(f"{SCHEDULER_URL}/schedule/", json=alarm_data)
                if response.status_code == 200:
                    created_count += 1
                else:
                    failed_count += 1
                    
            except Exception as e:
                failed_count += 1
        
        return jsonify({
            "status": "success",
            "message": f"Created {created_count} alarms, {failed_count} failed",
            "created": created_count,
            "failed": failed_count
        })
        
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

if __name__ == '__main__':
    # Start background thread for performance monitoring
    monitor_thread = threading.Thread(target=update_performance_data, daemon=True)
    monitor_thread.start()
    
    print("🚀 Starting Performance Dashboard...")
    print("📊 Dashboard will be available at: http://localhost:5000")
    print("⏰ Performance data updates every 2 seconds")
    
    app.run(debug=True, host='0.0.0.0', port=5000) 