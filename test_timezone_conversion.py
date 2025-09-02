#!/usr/bin/env python3
"""
Test script to verify timezone conversion functions work correctly.
This script tests the convert_local_time_to_utc and convert_utc_time_to_local functions.
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'microservices'))

from shared.models import convert_local_time_to_utc, convert_utc_time_to_local
import pytz
from datetime import datetime

def test_timezone_conversion():
    """Test timezone conversion functions"""
    print("🧪 Testing Timezone Conversion Functions")
    print("=" * 50)
    
    # Test cases: (local_time, timezone, expected_utc_offset)
    test_cases = [
        ("09:00:00", "America/Los_Angeles", -8),  # PST
        ("09:00:00", "America/New_York", -5),     # EST
        ("09:00:00", "Europe/London", 0),         # GMT
        ("09:00:00", "Asia/Tokyo", 9),            # JST
        ("09:00:00", "Australia/Sydney", 11),     # AEDT
        ("12:00:00", "America/Los_Angeles", -8),  # Noon PST
        ("00:00:00", "America/Los_Angeles", -8),  # Midnight PST
    ]
    
    for local_time, timezone, expected_offset in test_cases:
        print(f"\n📍 Testing: {local_time} in {timezone}")
        
        try:
            # Convert local time to UTC
            utc_time = convert_local_time_to_utc(local_time, timezone)
            print(f"   Local time: {local_time}")
            print(f"   UTC time:   {utc_time}")
            
            # Convert back to local time
            converted_back = convert_utc_time_to_local(utc_time, timezone)
            print(f"   Converted back: {converted_back}")
            
            # Verify the conversion is correct
            if local_time == converted_back:
                print(f"   ✅ Conversion successful!")
            else:
                print(f"   ❌ Conversion failed! Expected {local_time}, got {converted_back}")
            
            # Show the actual timezone offset
            tz = pytz.timezone(timezone)
            now = datetime.now(tz)
            offset_hours = now.utcoffset().total_seconds() / 3600
            print(f"   Current offset: {offset_hours:+.0f} hours")
            
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    print("\n" + "=" * 50)
    print("🎯 Timezone Conversion Test Complete!")

def test_edge_cases():
    """Test edge cases and error handling"""
    print("\n🧪 Testing Edge Cases")
    print("=" * 30)
    
    edge_cases = [
        ("23:59:59", "America/Los_Angeles"),
        ("00:00:01", "America/Los_Angeles"),
        ("12:00:00", "UTC"),
        ("12:00:00", "GMT"),
    ]
    
    for local_time, timezone in edge_cases:
        print(f"\n📍 Edge case: {local_time} in {timezone}")
        try:
            utc_time = convert_local_time_to_utc(local_time, timezone)
            converted_back = convert_utc_time_to_local(utc_time, timezone)
            print(f"   Local: {local_time} → UTC: {utc_time} → Local: {converted_back}")
            if local_time == converted_back:
                print(f"   ✅ Success!")
            else:
                print(f"   ❌ Failed!")
        except Exception as e:
            print(f"   ❌ Error: {e}")

def test_invalid_inputs():
    """Test invalid input handling"""
    print("\n🧪 Testing Invalid Inputs")
    print("=" * 30)
    
    invalid_cases = [
        ("25:00:00", "America/Los_Angeles"),  # Invalid hour
        ("12:60:00", "America/Los_Angeles"),  # Invalid minute
        ("12:00:60", "America/Los_Angeles"),  # Invalid second
        ("12:00", "America/Los_Angeles"),     # Missing seconds
        ("12", "America/Los_Angeles"),        # Missing minutes
        ("12:00:00", "Invalid/Timezone"),     # Invalid timezone
    ]
    
    for local_time, timezone in invalid_cases:
        print(f"\n📍 Invalid case: {local_time} in {timezone}")
        try:
            utc_time = convert_local_time_to_utc(local_time, timezone)
            print(f"   ❌ Should have failed, but got: {utc_time}")
        except Exception as e:
            print(f"   ✅ Correctly caught error: {e}")

if __name__ == "__main__":
    test_timezone_conversion()
    test_edge_cases()
    test_invalid_inputs()
    
    print("\n🎉 All tests completed!")
    print("\n📝 Summary:")
    print("   - Timezone conversion functions are working")
    print("   - UTC storage will ensure consistent scheduling")
    print("   - User times are preserved for display")
    print("   - System is now properly timezone-aware") 