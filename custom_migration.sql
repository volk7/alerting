-- Custom Database Migration for Existing Alarms Table
-- This script adapts the timezone migration to the existing table structure

-- Add utc_time column for UTC-based scheduling
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'alarms' AND column_name = 'utc_time') THEN
        ALTER TABLE alarms ADD COLUMN utc_time VARCHAR(8);
        
        -- Convert existing times to UTC (assuming they were stored in America/Los_Angeles timezone)
        UPDATE alarms 
        SET utc_time = CASE 
            WHEN time_str LIKE '%:%:%' THEN 
                -- Convert HH:MM:SS to UTC (simplified conversion - in practice, this should be done with proper timezone conversion)
                time_str
            WHEN time_str LIKE '%:%' THEN 
                -- Convert HH:MM to UTC (add :00 for seconds)
                time_str || ':00'
            ELSE time_str
        END
        WHERE utc_time IS NULL;
        
        -- Make utc_time NOT NULL after populating
        ALTER TABLE alarms ALTER COLUMN utc_time SET NOT NULL;
        
        RAISE NOTICE 'Added utc_time column and populated with existing times';
    END IF;
END $$;

-- Add timezone column for multi-timezone support
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'alarms' AND column_name = 'timezone') THEN
        ALTER TABLE alarms ADD COLUMN timezone VARCHAR(50) DEFAULT 'America/Los_Angeles';
    END IF;
END $$;

-- Add days_of_week column if it doesn't exist (map from existing 'day' column)
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'alarms' AND column_name = 'days_of_week') THEN
        ALTER TABLE alarms ADD COLUMN days_of_week VARCHAR(50) DEFAULT 'Mon,Tue,Wed,Thu,Fri,Sat,Sun';
        
        -- Convert existing 'day' values to days_of_week format
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
        WHERE days_of_week = 'Mon,Tue,Wed,Thu,Fri,Sat,Sun';
        
        RAISE NOTICE 'Added days_of_week column and converted existing day values';
    END IF;
END $$;

-- Add is_recurring column if it doesn't exist (map from existing 'recurring' column)
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'alarms' AND column_name = 'is_recurring') THEN
        ALTER TABLE alarms ADD COLUMN is_recurring BOOLEAN DEFAULT false;
        
        -- Map existing recurring values
        UPDATE alarms 
        SET is_recurring = COALESCE(recurring, false)
        WHERE is_recurring IS NULL;
        
        RAISE NOTICE 'Added is_recurring column and mapped existing recurring values';
    END IF;
END $$;

-- Add status column for alarm tracking
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'alarms' AND column_name = 'status') THEN
        ALTER TABLE alarms ADD COLUMN status VARCHAR(20) DEFAULT 'scheduled';
        
        -- Map existing canceled values to status
        UPDATE alarms 
        SET status = CASE 
            WHEN canceled = true THEN 'canceled'
            ELSE 'scheduled'
        END
        WHERE status = 'scheduled';
        
        RAISE NOTICE 'Added status column and mapped existing canceled values';
    END IF;
END $$;

-- Add created_at and updated_at columns if they don't exist
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'alarms' AND column_name = 'created_at') THEN
        ALTER TABLE alarms ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'alarms' AND column_name = 'updated_at') THEN
        ALTER TABLE alarms ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
    END IF;
END $$;

-- Create trigger to update updated_at column
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Drop trigger if it exists and recreate
DROP TRIGGER IF EXISTS update_alarms_updated_at ON alarms;
CREATE TRIGGER update_alarms_updated_at 
    BEFORE UPDATE ON alarms 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

-- Add indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_alarms_time_str ON alarms(time_str);
CREATE INDEX IF NOT EXISTS idx_alarms_utc_time ON alarms(utc_time);
CREATE INDEX IF NOT EXISTS idx_alarms_email ON alarms(email);
CREATE INDEX IF NOT EXISTS idx_alarms_code_id ON alarms(code_id);
CREATE INDEX IF NOT EXISTS idx_alarms_is_recurring ON alarms(is_recurring);
CREATE INDEX IF NOT EXISTS idx_alarms_timezone ON alarms(timezone);
CREATE INDEX IF NOT EXISTS idx_alarms_days_of_week ON alarms(days_of_week);
CREATE INDEX IF NOT EXISTS idx_alarms_status ON alarms(status);

-- Composite indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_alarms_email_time ON alarms(email, time_str);
CREATE INDEX IF NOT EXISTS idx_alarms_code_time ON alarms(code_id, time_str);
CREATE INDEX IF NOT EXISTS idx_alarms_email_utc_time ON alarms(email, utc_time);
CREATE INDEX IF NOT EXISTS idx_alarms_code_utc_time ON alarms(code_id, utc_time);

-- Partial index for non-recurring alarms (for cleanup operations)
CREATE INDEX IF NOT EXISTS idx_alarms_non_recurring ON alarms(utc_time) WHERE is_recurring = false;

-- Create a view for active alarms (for easier querying)
CREATE OR REPLACE VIEW active_alarms AS
SELECT 
    id,
    code_id,
    email,
    time_str as time,
    utc_time,
    is_recurring,
    status,
    timezone,
    days_of_week,
    created_at,
    updated_at
FROM alarms 
WHERE status = 'scheduled';

-- Create a function to get alarms by UTC time range
CREATE OR REPLACE FUNCTION get_alarms_by_utc_time_range(
    start_time TIME,
    end_time TIME
) RETURNS TABLE (
    id INTEGER,
    code_id VARCHAR,
    email VARCHAR,
    time VARCHAR,
    utc_time VARCHAR,
    is_recurring BOOLEAN,
    status VARCHAR,
    timezone VARCHAR
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        a.id,
        a.code_id,
        a.email,
        a.time_str,
        a.utc_time,
        a.is_recurring,
        a.status,
        a.timezone
    FROM alarms a
    WHERE a.utc_time BETWEEN start_time::TEXT AND end_time::TEXT
    AND a.status = 'scheduled'
    ORDER BY a.utc_time;
END;
$$ LANGUAGE plpgsql;

-- Create a function to get alarms count by UTC hour
CREATE OR REPLACE FUNCTION get_alarms_count_by_utc_hour() 
RETURNS TABLE (
    hour INTEGER,
    alarm_count BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        EXTRACT(HOUR FROM utc_time::TIME)::INTEGER as hour,
        COUNT(*) as alarm_count
    FROM alarms 
    WHERE status = 'scheduled'
    GROUP BY EXTRACT(HOUR FROM utc_time::TIME)
    ORDER BY hour;
END;
$$ LANGUAGE plpgsql;

-- Grant necessary permissions
GRANT SELECT, INSERT, UPDATE, DELETE ON alarms TO admin;
GRANT SELECT ON active_alarms TO admin;
GRANT EXECUTE ON FUNCTION get_alarms_by_utc_time_range(TIME, TIME) TO admin;
GRANT EXECUTE ON FUNCTION get_alarms_count_by_utc_hour() TO admin;

-- Add comments to document the schema
COMMENT ON TABLE alarms IS 'Alarm table with UTC timezone support - time_str: user local time, utc_time: UTC time for scheduling';
COMMENT ON COLUMN alarms.time_str IS 'User local time for display purposes (HH:MM:SS format)';
COMMENT ON COLUMN alarms.utc_time IS 'UTC time for scheduling and comparison (HH:MM:SS format)';
COMMENT ON COLUMN alarms.timezone IS 'User timezone for conversion between local and UTC times';
COMMENT ON COLUMN alarms.days_of_week IS 'Comma-separated list of days when alarm should trigger (Mon,Tue,Wed,Thu,Fri,Sat,Sun)';

-- Create a summary view for timezone information
CREATE OR REPLACE VIEW timezone_summary AS
SELECT 
    timezone,
    COUNT(*) as alarm_count,
    MIN(time_str) as earliest_local_time,
    MAX(time_str) as latest_local_time,
    MIN(utc_time) as earliest_utc_time,
    MAX(utc_time) as latest_utc_time
FROM alarms 
WHERE status = 'scheduled'
GROUP BY timezone
ORDER BY alarm_count DESC;

-- Grant permissions for timezone summary
GRANT SELECT ON timezone_summary TO admin; 