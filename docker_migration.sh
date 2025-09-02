#!/bin/bash
# Docker Migration Script
# This script runs the database migration inside the Docker PostgreSQL container

set -e  # Exit on any error

echo "🚀 Starting Docker Database Migration"
echo "=================================================="

# Function to find PostgreSQL container
find_postgres_container() {
    echo "🔍 Looking for PostgreSQL container..."
    
    # Try different possible container names
    CONTAINER_NAMES=(
        "postgres"
        "alarms_postgres"
        "alerting_postgres"
        "db"
        "database"
    )
    
    for name in "${CONTAINER_NAMES[@]}"; do
        if docker ps --format "table {{.Names}}" | grep -q "^${name}$"; then
            echo "✅ Found PostgreSQL container: $name"
            return 0
        fi
    done
    
    # If not found by name, try to find by image
    if docker ps --format "table {{.Names}}\t{{.Image}}" | grep -q "postgres"; then
        CONTAINER_NAME=$(docker ps --format "table {{.Names}}\t{{.Image}}" | grep "postgres" | head -1 | awk '{print $1}')
        echo "✅ Found PostgreSQL container by image: $CONTAINER_NAME"
        return 0
    fi
    
    echo "❌ No PostgreSQL container found"
    echo "Available containers:"
    docker ps --format "table {{.Names}}\t{{.Image}}"
    return 1
}

# Function to run migration
run_migration() {
    local container_name=$1
    
    echo "📄 Copying migration script to container..."
    
    # Copy migration script to container
    docker cp microservices/database_migration.sql "${container_name}:/tmp/migration.sql"
    
    echo "🔄 Running migration in container..."
    
    # Run the migration
    docker exec "${container_name}" psql -U admin -d alarms_db -f /tmp/migration.sql
    
    echo "🧹 Cleaning up..."
    
    # Remove temporary file
    docker exec "${container_name}" rm /tmp/migration.sql
    
    echo "✅ Migration completed!"
}

# Function to verify migration
verify_migration() {
    local container_name=$1
    
    echo "🔍 Verifying migration..."
    
    # Check if utc_time column exists
    docker exec "${container_name}" psql -U admin -d alarms_db -c "
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'alarms' AND column_name = 'utc_time';
    "
    
    # Check table structure
    echo "📋 Current table structure:"
    docker exec "${container_name}" psql -U admin -d alarms_db -c "
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns 
        WHERE table_name = 'alarms'
        ORDER BY ordinal_position;
    "
    
    # Check indexes
    echo "📊 Current indexes:"
    docker exec "${container_name}" psql -U admin -d alarms_db -c "
        SELECT indexname 
        FROM pg_indexes 
        WHERE tablename = 'alarms' 
        ORDER BY indexname;
    "
}

# Function to test connection
test_connection() {
    local container_name=$1
    
    echo "🔍 Testing database connection..."
    
    if docker exec "${container_name}" psql -U admin -d alarms_db -c "SELECT version();" > /dev/null 2>&1; then
        echo "✅ Database connection successful"
        return 0
    else
        echo "❌ Database connection failed"
        return 1
    fi
}

# Main execution
main() {
    # Check if Docker is running
    if ! docker info > /dev/null 2>&1; then
        echo "❌ Docker is not running or not accessible"
        exit 1
    fi
    
    # Find PostgreSQL container
    if ! find_postgres_container; then
        echo "❌ Cannot find PostgreSQL container"
        echo ""
        echo "🔧 Troubleshooting:"
        echo "   1. Make sure Docker is running"
        echo "   2. Start your PostgreSQL container"
        echo "   3. Check container name in docker-compose.yml"
        exit 1
    fi
    
    # Store container name
    CONTAINER_NAME=$(docker ps --format "table {{.Names}}\t{{.Image}}" | grep "postgres" | head -1 | awk '{print $1}')
    
    # Test connection
    if ! test_connection "$CONTAINER_NAME"; then
        echo "❌ Cannot connect to database"
        exit 1
    fi
    
    # Check if migration file exists
    if [ ! -f "microservices/database_migration.sql" ]; then
        echo "❌ Migration file not found: microservices/database_migration.sql"
        exit 1
    fi
    
    # Run migration
    run_migration "$CONTAINER_NAME"
    
    # Verify migration
    verify_migration "$CONTAINER_NAME"
    
    echo ""
    echo "🎉 Migration completed successfully!"
    echo ""
    echo "📝 Next steps:"
    echo "   1. Restart your microservices"
    echo "   2. Test timezone conversion: python test_timezone_conversion.py"
    echo "   3. Create a test alarm to verify timezone handling"
}

# Run main function
main "$@" 