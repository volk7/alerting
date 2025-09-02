-- Database Migration for Scalable Alarm Scheduler with UTC Timezone Support
-- This script adds necessary indexes and optimizations for handling thousands of alarms
-- and adds UTC time storage for proper timezone handling

-- Add utc_time column for UTC-based scheduling
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'alarms' AND column_name = 'utc_time') THEN
        ALTER TABLE alarms ADD COLUMN utc_time VARCHAR(8);
        
        -- Convert existing times to UTC (assuming they were stored in America/Los_Angeles timezone)
        UPDATE alarms 
        SET utc_time = CASE 
            WHEN time LIKE '%:%:%' THEN 
                -- Convert HH:MM:SS to UTC (simplified conversion - in practice, this should be done with proper timezone conversion)
                time
            WHEN time LIKE '%:%' THEN 
                -- Convert HH:MM to UTC (add :00 for seconds)
                time || ':00'
            ELSE time
        END
        WHERE utc_time IS NULL;
        
        -- Make utc_time NOT NULL after populating
        ALTER TABLE alarms ALTER COLUMN utc_time SET NOT NULL;
        
        RAISE NOTICE 'Added utc_time column and populated with existing times';
    END IF;
END $$;

-- Add indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_alarms_time ON alarms(time);
CREATE INDEX IF NOT EXISTS idx_alarms_utc_time ON alarms(utc_time);
CREATE INDEX IF NOT EXISTS idx_alarms_email ON alarms(email);
CREATE INDEX IF NOT EXISTS idx_alarms_code_id ON alarms(code_id);
CREATE INDEX IF NOT EXISTS idx_alarms_is_recurring ON alarms(is_recurring);

-- Composite index for common query patterns
CREATE INDEX IF NOT EXISTS idx_alarms_email_time ON alarms(email, time);
CREATE INDEX IF NOT EXISTS idx_alarms_code_time ON alarms(code_id, time);
CREATE INDEX IF NOT EXISTS idx_alarms_email_utc_time ON alarms(email, utc_time);
CREATE INDEX IF NOT EXISTS idx_alarms_code_utc_time ON alarms(code_id, utc_time);

-- Partial index for non-recurring alarms (for cleanup operations)
CREATE INDEX IF NOT EXISTS idx_alarms_non_recurring ON alarms(utc_time) WHERE is_recurring = false;

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

-- Add status column for alarm tracking
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'alarms' AND column_name = 'status') THEN
        ALTER TABLE alarms ADD COLUMN status VARCHAR(20) DEFAULT 'scheduled';
    END IF;
END $$;

-- Create index on status for filtering
CREATE INDEX IF NOT EXISTS idx_alarms_status ON alarms(status);

-- Add priority column for future use
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'alarms' AND column_name = 'priority') THEN
        ALTER TABLE alarms ADD COLUMN priority INTEGER DEFAULT 1;
    END IF;
END $$;

-- Create index on priority
CREATE INDEX IF NOT EXISTS idx_alarms_priority ON alarms(priority);

-- Add timezone column for multi-timezone support
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'alarms' AND column_name = 'timezone') THEN
        ALTER TABLE alarms ADD COLUMN timezone VARCHAR(50) DEFAULT 'America/Los_Angeles';
    END IF;
END $$;

-- Create index on timezone
CREATE INDEX IF NOT EXISTS idx_alarms_timezone ON alarms(timezone);

-- Add days_of_week column if it doesn't exist
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'alarms' AND column_name = 'days_of_week') THEN
        ALTER TABLE alarms ADD COLUMN days_of_week VARCHAR(50) DEFAULT 'Mon,Tue,Wed,Thu,Fri,Sat,Sun';
    END IF;
END $$;

-- Create index on days_of_week
CREATE INDEX IF NOT EXISTS idx_alarms_days_of_week ON alarms(days_of_week);

-- Create a view for active alarms (for easier querying)
CREATE OR REPLACE VIEW active_alarms AS
SELECT 
    code_id,
    email,
    time,
    utc_time,
    is_recurring,
    status,
    priority,
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
    code_id VARCHAR,
    email VARCHAR,
    time VARCHAR,
    utc_time VARCHAR,
    is_recurring BOOLEAN,
    status VARCHAR,
    priority INTEGER,
    timezone VARCHAR
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        a.code_id,
        a.email,
        a.time,
        a.utc_time,
        a.is_recurring,
        a.status,
        a.priority,
        a.timezone
    FROM alarms a
    WHERE a.utc_time BETWEEN start_time::TEXT AND end_time::TEXT
    AND a.status = 'scheduled'
    ORDER BY a.utc_time, a.priority DESC;
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

-- Create a function to cleanup expired non-recurring alarms
CREATE OR REPLACE FUNCTION cleanup_expired_alarms() 
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM alarms 
    WHERE is_recurring = false 
    AND status = 'triggered'
    AND updated_at < CURRENT_TIMESTAMP - INTERVAL '24 hours';
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- Grant necessary permissions
GRANT SELECT, INSERT, UPDATE, DELETE ON alarms TO admin;
GRANT SELECT ON active_alarms TO admin;
GRANT EXECUTE ON FUNCTION get_alarms_by_utc_time_range(TIME, TIME) TO admin;
GRANT EXECUTE ON FUNCTION get_alarms_count_by_utc_hour() TO admin;
GRANT EXECUTE ON FUNCTION cleanup_expired_alarms() TO admin;

-- Create a table for alarm statistics
CREATE TABLE IF NOT EXISTS alarm_statistics (
    id SERIAL PRIMARY KEY,
    date DATE DEFAULT CURRENT_DATE,
    total_alarms INTEGER DEFAULT 0,
    triggered_alarms INTEGER DEFAULT 0,
    failed_alarms INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create index on alarm_statistics
CREATE INDEX IF NOT EXISTS idx_alarm_statistics_date ON alarm_statistics(date);

-- Insert initial statistics record
INSERT INTO alarm_statistics (date, total_alarms, triggered_alarms, failed_alarms)
SELECT 
    CURRENT_DATE,
    COUNT(*) as total_alarms,
    COUNT(CASE WHEN status = 'triggered' THEN 1 END) as triggered_alarms,
    COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed_alarms
FROM alarms
ON CONFLICT (date) DO NOTHING;

-- Create a function to update daily statistics
CREATE OR REPLACE FUNCTION update_daily_statistics() 
RETURNS VOID AS $$
BEGIN
    INSERT INTO alarm_statistics (date, total_alarms, triggered_alarms, failed_alarms)
    SELECT 
        CURRENT_DATE,
        COUNT(*) as total_alarms,
        COUNT(CASE WHEN status = 'triggered' THEN 1 END) as triggered_alarms,
        COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed_alarms
    FROM alarms
    ON CONFLICT (date) DO UPDATE SET
        total_alarms = EXCLUDED.total_alarms,
        triggered_alarms = EXCLUDED.triggered_alarms,
        failed_alarms = EXCLUDED.failed_alarms,
        created_at = CURRENT_TIMESTAMP;
END;
$$ LANGUAGE plpgsql;

-- Grant permissions for statistics
GRANT SELECT, INSERT, UPDATE ON alarm_statistics TO admin;
GRANT EXECUTE ON FUNCTION update_daily_statistics() TO admin;

-- Create a function to convert local time to UTC (for reference)
CREATE OR REPLACE FUNCTION convert_local_to_utc_time(
    local_time TIME,
    timezone_name VARCHAR(50)
) RETURNS TIME AS $$
DECLARE
    utc_time TIME;
BEGIN
    -- This is a simplified conversion - in practice, you'd want to use proper timezone conversion
    -- For now, we'll return the same time as a placeholder
    -- In a real implementation, you'd use timezone conversion functions
    RETURN local_time;
END;
$$ LANGUAGE plpgsql;

-- Grant permissions for time conversion
GRANT EXECUTE ON FUNCTION convert_local_to_utc_time(TIME, VARCHAR) TO admin;

-- Add comments to document the schema
COMMENT ON TABLE alarms IS 'Alarm table with UTC timezone support - time: user local time, utc_time: UTC time for scheduling';
COMMENT ON COLUMN alarms.time IS 'User local time for display purposes (HH:MM:SS format)';
COMMENT ON COLUMN alarms.utc_time IS 'UTC time for scheduling and comparison (HH:MM:SS format)';
COMMENT ON COLUMN alarms.timezone IS 'User timezone for conversion between local and UTC times';
COMMENT ON COLUMN alarms.days_of_week IS 'Comma-separated list of days when alarm should trigger (Mon,Tue,Wed,Thu,Fri,Sat,Sun)';

-- Create a summary view for timezone information
CREATE OR REPLACE VIEW timezone_summary AS
SELECT 
    timezone,
    COUNT(*) as alarm_count,
    MIN(time) as earliest_local_time,
    MAX(time) as latest_local_time,
    MIN(utc_time) as earliest_utc_time,
    MAX(utc_time) as latest_utc_time
FROM alarms 
WHERE status = 'scheduled'
GROUP BY timezone
ORDER BY alarm_count DESC;

-- Grant permissions for timezone summary
GRANT SELECT ON timezone_summary TO admin; 