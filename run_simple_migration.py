#!/usr/bin/env python3
"""
Simple Database Migration Runner
This script runs the timezone migration directly using psycopg2.
"""

import psycopg2
import os
import sys
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Database configuration
DB_HOST = "localhost"
DB_NAME = "alarms"
DB_USER = "admin"
DB_PASSWORD = "ZZ4charlie"

def run_migration():
    """Run the timezone migration"""
    try:
        logger.info("🔍 Connecting to database...")
        conn = psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST
        )
        conn.autocommit = False
        cursor = conn.cursor()
        
        logger.info("✅ Connected successfully!")
        
        # Step 1: Add utc_time column
        logger.info("🔄 Step 1: Adding utc_time column...")
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'alarms' AND column_name = 'utc_time'
        """)
        has_utc_column = cursor.fetchone() is not None
        
        if not has_utc_column:
            cursor.execute("ALTER TABLE alarms ADD COLUMN utc_time VARCHAR(8)")
            logger.info("✅ Added utc_time column")
            
            # Populate utc_time with existing times (simplified conversion)
            cursor.execute("""
                UPDATE alarms 
                SET utc_time = CASE 
                    WHEN time_str LIKE '%:%:%' THEN time_str
                    WHEN time_str LIKE '%:%' THEN time_str || ':00'
                    ELSE time_str
                END
                WHERE utc_time IS NULL
            """)
            logger.info("✅ Populated utc_time column")
            
            # Make utc_time NOT NULL
            cursor.execute("ALTER TABLE alarms ALTER COLUMN utc_time SET NOT NULL")
            logger.info("✅ Made utc_time NOT NULL")
        else:
            logger.info("✅ UTC time column already exists")
        
        # Step 2: Add timezone column
        logger.info("🔄 Step 2: Adding timezone column...")
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'alarms' AND column_name = 'timezone'
        """)
        has_timezone_column = cursor.fetchone() is not None
        
        if not has_timezone_column:
            cursor.execute("ALTER TABLE alarms ADD COLUMN timezone VARCHAR(50) DEFAULT 'America/Los_Angeles'")
            logger.info("✅ Added timezone column")
        else:
            logger.info("✅ Timezone column already exists")
        
        # Step 3: Add days_of_week column
        logger.info("🔄 Step 3: Adding days_of_week column...")
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'alarms' AND column_name = 'days_of_week'
        """)
        has_days_column = cursor.fetchone() is not None
        
        if not has_days_column:
            cursor.execute("ALTER TABLE alarms ADD COLUMN days_of_week VARCHAR(50) DEFAULT 'Mon,Tue,Wed,Thu,Fri,Sat,Sun'")
            logger.info("✅ Added days_of_week column")
            
            # Convert existing day values
            cursor.execute("""
                UPDATE alarms 
                SET days_of_week = CASE 
                    WHEN day = 'Monday' THEN 'Mon'
                    WHEN day = 'Tuesday' THEN 'Tue'
                    WHEN day = 'Wednesday' THEN 'Wed'
                    WHEN day = 'Thursday' THEN 'Thu'
                    WHEN day = 'Friday' THEN 'Fri'
                    WHEN day = 'Saturday' THEN 'Sat'
                    WHEN day = 'Sunday' THEN 'Sun'
                    WHEN day = 'Everyday' THEN 'Mon,Tue,Wed,Thu,Fri,Sat,Sun'
                    WHEN day = 'Weekdays' THEN 'Mon,Tue,Wed,Thu,Fri'
                    WHEN day = 'Weekends' THEN 'Sat,Sun'
                    ELSE 'Mon,Tue,Wed,Thu,Fri,Sat,Sun'
                END
                WHERE days_of_week = 'Mon,Tue,Wed,Thu,Fri,Sat,Sun'
            """)
            logger.info("✅ Converted existing day values")
        else:
            logger.info("✅ Days of week column already exists")
        
        # Step 4: Add is_recurring column
        logger.info("🔄 Step 4: Adding is_recurring column...")
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'alarms' AND column_name = 'is_recurring'
        """)
        has_recurring_column = cursor.fetchone() is not None
        
        if not has_recurring_column:
            cursor.execute("ALTER TABLE alarms ADD COLUMN is_recurring BOOLEAN DEFAULT false")
            logger.info("✅ Added is_recurring column")
            
            # Map existing recurring values
            cursor.execute("""
                UPDATE alarms 
                SET is_recurring = COALESCE(recurring, false)
                WHERE is_recurring IS NULL
            """)
            logger.info("✅ Mapped existing recurring values")
        else:
            logger.info("✅ Is recurring column already exists")
        
        # Step 5: Add status column
        logger.info("🔄 Step 5: Adding status column...")
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'alarms' AND column_name = 'status'
        """)
        has_status_column = cursor.fetchone() is not None
        
        if not has_status_column:
            cursor.execute("ALTER TABLE alarms ADD COLUMN status VARCHAR(20) DEFAULT 'scheduled'")
            logger.info("✅ Added status column")
            
            # Map existing canceled values
            cursor.execute("""
                UPDATE alarms 
                SET status = CASE 
                    WHEN canceled = true THEN 'canceled'
                    ELSE 'scheduled'
                END
                WHERE status = 'scheduled'
            """)
            logger.info("✅ Mapped existing canceled values")
        else:
            logger.info("✅ Status column already exists")
        
        # Step 6: Add created_at and updated_at columns
        logger.info("🔄 Step 6: Adding timestamp columns...")
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'alarms' AND column_name = 'created_at'
        """)
        has_created_at = cursor.fetchone() is not None
        
        if not has_created_at:
            cursor.execute("ALTER TABLE alarms ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
            logger.info("✅ Added created_at column")
        else:
            logger.info("✅ Created at column already exists")
        
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'alarms' AND column_name = 'updated_at'
        """)
        has_updated_at = cursor.fetchone() is not None
        
        if not has_updated_at:
            cursor.execute("ALTER TABLE alarms ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
            logger.info("✅ Added updated_at column")
        else:
            logger.info("✅ Updated at column already exists")
        
        # Step 7: Create indexes
        logger.info("🔄 Step 7: Creating indexes...")
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_alarms_utc_time ON alarms(utc_time)",
            "CREATE INDEX IF NOT EXISTS idx_alarms_timezone ON alarms(timezone)",
            "CREATE INDEX IF NOT EXISTS idx_alarms_days_of_week ON alarms(days_of_week)",
            "CREATE INDEX IF NOT EXISTS idx_alarms_is_recurring ON alarms(is_recurring)",
            "CREATE INDEX IF NOT EXISTS idx_alarms_status ON alarms(status)",
            "CREATE INDEX IF NOT EXISTS idx_alarms_email_utc_time ON alarms(email, utc_time)",
            "CREATE INDEX IF NOT EXISTS idx_alarms_code_utc_time ON alarms(code_id, utc_time)"
        ]
        
        for index_sql in indexes:
            cursor.execute(index_sql)
        logger.info("✅ Created indexes")
        
        # Commit all changes
        conn.commit()
        logger.info("✅ All changes committed successfully!")
        
        # Verify the migration
        logger.info("🔍 Verifying migration...")
        cursor.execute("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns 
            WHERE table_name = 'alarms'
            ORDER BY ordinal_position
        """)
        columns = cursor.fetchall()
        
        logger.info("📊 Final table structure:")
        for col_name, data_type, nullable in columns:
            logger.info(f"   - {col_name}: {data_type} ({'NULL' if nullable == 'YES' else 'NOT NULL'})")
        
        # Check if all required columns exist
        required_columns = ['utc_time', 'timezone', 'days_of_week', 'is_recurring', 'status']
        existing_columns = [col[0] for col in columns]
        
        missing_columns = [col for col in required_columns if col not in existing_columns]
        if missing_columns:
            logger.warning(f"⚠️ Missing columns: {missing_columns}")
        else:
            logger.info("✅ All required columns exist")
        
        cursor.close()
        conn.close()
        
        logger.info("🎉 Migration completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return False

def main():
    """Main function"""
    logger.info("🚀 Starting Simple Database Migration")
    logger.info("=" * 50)
    
    if run_migration():
        logger.info("")
        logger.info("🎉 Migration completed successfully!")
        logger.info("")
        logger.info("📝 Next steps:")
        logger.info("   1. Restart your microservices")
        logger.info("   2. Test timezone conversion: python test_timezone_conversion.py")
        logger.info("   3. Create a test alarm to verify timezone handling")
        sys.exit(0)
    else:
        logger.error("")
        logger.error("❌ Migration failed!")
        sys.exit(1)

if __name__ == "__main__":
    main() 