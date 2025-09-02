#!/usr/bin/env python3
"""
Simple database connection test
"""

import psycopg2

# Database configuration
DB_HOST = "localhost"
DB_NAME = "alarms"
DB_USER = "admin"
DB_PASSWORD = "ZZ4charlie"

try:
    print("🔍 Testing database connection...")
    print(f"Host: {DB_HOST}")
    print(f"Database: {DB_NAME}")
    print(f"User: {DB_USER}")
    
    # Connect to database
    conn = psycopg2.connect(
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST
    )
    
    print("✅ Connected successfully!")
    
    # Check what tables exist
    cursor = conn.cursor()
    cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
    tables = cursor.fetchall()
    
    print(f"📋 Tables in database: {[table[0] for table in tables]}")
    
    # Check if alarms table exists
    if ('alarms',) in tables:
        print("✅ Alarms table exists!")
        
        # Check table structure
        cursor.execute("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns 
            WHERE table_name = 'alarms'
            ORDER BY ordinal_position
        """)
        columns = cursor.fetchall()
        
        print("📊 Current table structure:")
        for col_name, data_type, nullable in columns:
            print(f"   - {col_name}: {data_type} ({'NULL' if nullable == 'YES' else 'NOT NULL'})")
        
        # Check if utc_time column exists
        has_utc_column = any(col[0] == 'utc_time' for col in columns)
        if has_utc_column:
            print("✅ UTC time column already exists!")
        else:
            print("⚠️ UTC time column does not exist - migration needed")
        
        # Count alarms
        cursor.execute("SELECT COUNT(*) FROM alarms")
        count = cursor.fetchone()[0]
        print(f"📊 Total alarms: {count}")
        
    else:
        print("⚠️ Alarms table does not exist")
    
    cursor.close()
    conn.close()
    
    print("\n🎉 Database connection test completed successfully!")
    
except Exception as e:
    print(f"❌ Connection failed: {e}")
    print("\n🔧 Troubleshooting:")
    print("   1. Make sure PostgreSQL is running")
    print("   2. Check if the 'alarms' database exists")
    print("   3. Verify username and password")
    print("   4. Check if PostgreSQL is listening on localhost:5432") 