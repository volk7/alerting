# Timezone Migration Guide

## Overview

The alerting system has been updated to be fully timezone-aware with proper UTC storage and conversion. This ensures consistent alarm scheduling regardless of server timezone, daylight saving time changes, or user location.

## Key Changes

### 1. Database Schema Updates

- **Added `utc_time` column**: Stores alarm times in UTC for consistent scheduling
- **Preserved `time` column**: Keeps user's local time for display purposes
- **Enhanced `timezone` column**: Stores user's timezone for conversion

### 2. Model Updates

- **AlarmRequest**: Added timezone validation and time format validation
- **AlarmResponse**: Includes both local and UTC times
- **AlarmEvent**: Enhanced with timezone information
- **DatabaseAlarm**: Supports UTC time storage

### 3. Timezone Conversion Functions

```python
# Convert user's local time to UTC for storage
utc_time = convert_local_time_to_utc("09:00:00", "America/Los_Angeles")

# Convert UTC time back to user's local time for display
local_time = convert_utc_time_to_local("17:00:00", "America/Los_Angeles")
```

### 4. Scheduler Updates

- **UTC-based scheduling**: All alarm comparisons use UTC time
- **Timezone-aware day checking**: Day-of-week validation uses user's timezone
- **Consistent time handling**: No more timezone confusion

## Migration Steps

### 1. Run Database Migration

```sql
-- Execute the migration script
\i microservices/database_migration.sql
```

This will:
- Add the `utc_time` column
- Convert existing times to UTC (assuming America/Los_Angeles)
- Create necessary indexes
- Add timezone support functions

### 2. Update Dependencies

Ensure all services have the required dependencies:

```bash
pip install pytz>=2023.3
```

### 3. Restart Services

Restart all microservices to pick up the new timezone-aware code:

```bash
# Database service
cd microservices/database-service
python main.py

# Alarm scheduler
cd microservices/alarm-scheduler
python main.py

# Email service
cd microservices/email-service
python main.py
```

## API Changes

### Creating Alarms

```json
POST /alarms/
{
    "code_id": "TEST_001",
    "email": "user@example.com",
    "time": "09:00:00",
    "timezone": "America/Los_Angeles",
    "is_recurring": true,
    "days_of_week": "Mon,Tue,Wed,Thu,Fri"
}
```

### Response Format

```json
{
    "code_id": "TEST_001",
    "email": "user@example.com",
    "time": "09:00:00",
    "utc_time": "17:00:00",
    "is_recurring": true,
    "status": "scheduled",
    "timezone": "America/Los_Angeles",
    "days_of_week": "Mon,Tue,Wed,Thu,Fri"
}
```

## Benefits

### 1. Consistent Scheduling
- Alarms trigger at the correct time regardless of server timezone
- No more daylight saving time issues
- Reliable scheduling across different regions

### 2. User-Friendly Display
- Users see times in their local timezone
- No confusion about what timezone is being used
- Clear timezone indication in emails

### 3. Scalability
- Support for users in any timezone
- Proper handling of timezone transitions
- Future-proof for global deployment

## Testing

### Run Timezone Tests

```bash
python test_timezone_conversion.py
```

This will test:
- Timezone conversion accuracy
- Edge cases (midnight, DST transitions)
- Invalid input handling
- Round-trip conversion validation

### Manual Testing

1. **Create an alarm** in a specific timezone
2. **Verify the UTC conversion** in the database
3. **Test alarm triggering** at the correct time
4. **Check email notifications** show correct timezone

## Troubleshooting

### Common Issues

1. **Import Errors**: Ensure `pytz` is installed
2. **Database Errors**: Run the migration script
3. **Timezone Errors**: Verify timezone names are valid
4. **Conversion Errors**: Check time format (HH:MM:SS)

### Debug Endpoints

- `/debug/timezone-test`: Test timezone conversion
- `/debug/alarms`: View all alarms with timezone info
- `/health`: Check service status and timezone config

## Backward Compatibility

- Existing alarms will be automatically converted
- Old API endpoints still work
- Gradual migration supported
- No data loss during migration

## Future Enhancements

1. **Automatic timezone detection** from user location
2. **DST transition handling** for recurring alarms
3. **Timezone-aware UI** with timezone picker
4. **Global timezone support** for international users

## Support

For issues or questions about the timezone migration:

1. Check the debug endpoints for timezone information
2. Run the test script to verify conversions
3. Review the migration logs for any errors
4. Contact the development team for assistance 