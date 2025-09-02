@echo off
REM Windows Database Migration Script
REM This script runs the database migration using Python

echo 🚀 Starting Database Migration
echo ==================================================

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python is not installed or not in PATH
    echo Please install Python and try again
    pause
    exit /b 1
)

REM Check if required packages are installed
echo 🔍 Checking dependencies...
python -c "import psycopg2" >nul 2>&1
if errorlevel 1 (
    echo ❌ psycopg2 is not installed
    echo Installing required packages...
    pip install psycopg2-binary
    if errorlevel 1 (
        echo ❌ Failed to install psycopg2-binary
        echo Please install it manually: pip install psycopg2-binary
        pause
        exit /b 1
    )
)

REM Check if migration file exists
if not exist "microservices\database_migration.sql" (
    echo ❌ Migration file not found: microservices\database_migration.sql
    pause
    exit /b 1
)

REM Run the migration
echo 🔄 Running migration...
python run_migration.py

if errorlevel 1 (
    echo.
    echo ❌ Migration failed!
    echo.
    echo 🔧 Troubleshooting:
    echo    1. Check database connection settings
    echo    2. Ensure PostgreSQL is running
    echo    3. Verify database permissions
    echo    4. Check migration logs above
    pause
    exit /b 1
) else (
    echo.
    echo 🎉 Migration completed successfully!
    echo.
    echo 📝 Next steps:
    echo    1. Restart your microservices
    echo    2. Test timezone conversion: python test_timezone_conversion.py
    echo    3. Create a test alarm to verify timezone handling
)

pause 