#!/usr/bin/env python3
"""
Database Migration Script Runner
This script runs the database migration programmatically using the existing database connection.
"""

import psycopg2
import os
import sys
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Database configuration (same as in the microservices)
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://admin:ZZ4charlie@localhost:5432/alarms")

def parse_database_url(url):
    """Parse database URL to get connection parameters"""
    try:
        # Remove postgresql:// prefix
        if url.startswith('postgresql://'):
            url = url[13:]
        
        # Split into user:pass@host:port/database
        if '@' in url:
            auth_part, rest = url.split('@', 1)
            if ':' in auth_part:
                user, password = auth_part.split(':', 1)
            else:
                user, password = auth_part, ''
            
            if '/' in rest:
                host_port, database = rest.split('/', 1)
                if ':' in host_port:
                    host, port = host_port.split(':', 1)
                    port = int(port)
                else:
                    host, port = host_port, 5432
            else:
                host, port, database = rest, 5432, 'postgres'
        else:
            # No authentication
            user = password = ''
            if '/' in url:
                host_port, database = url.split('/', 1)
                if ':' in host_port:
                    host, port = host_port.split(':', 1)
                    port = int(port)
                else:
                    host, port = host_port, 5432
            else:
                host, port, database = 'localhost', 5432, url
        
        return {
            'host': host,
            'port': port,
            'database': database,
            'user': user,
            'password': password
        }
    except Exception as e:
        logger.error(f"Error parsing database URL: {e}")
        raise

def run_migration():
    """Run the database migration"""
    try:
        # Parse database connection parameters
        db_params = parse_database_url(DATABASE_URL)
        logger.info(f"Connecting to database: {db_params['host']}:{db_params['port']}/{db_params['database']}")
        
        # Connect to database
        conn = psycopg2.connect(**db_params)
        conn.autocommit = False  # We'll handle transactions manually
        cursor = conn.cursor()
        
        logger.info("✅ Connected to database successfully")
        
        # Read the migration script
        migration_file = Path("custom_migration.sql")
        if not migration_file.exists():
            logger.error(f"Migration file not found: {migration_file}")
            return False
        
        with open(migration_file, 'r') as f:
            migration_sql = f.read()
        
        logger.info(f"📄 Loaded migration script: {migration_file}")
        
        # Split the migration into individual statements
        # Remove comments and split by semicolon
        statements = []
        current_statement = ""
        in_block_comment = False
        
        for line in migration_sql.split('\n'):
            line = line.strip()
            
            # Skip empty lines
            if not line:
                continue
            
            # Handle block comments
            if '/*' in line:
                in_block_comment = True
                continue
            if '*/' in line:
                in_block_comment = False
                continue
            if in_block_comment:
                continue
            
            # Skip single line comments
            if line.startswith('--'):
                continue
            
            current_statement += line + " "
            
            # Check if statement ends with semicolon
            if line.endswith(';'):
                statements.append(current_statement.strip())
                current_statement = ""
        
        # Add any remaining statement
        if current_statement.strip():
            statements.append(current_statement.strip())
        
        logger.info(f"📝 Found {len(statements)} SQL statements to execute")
        
        # Execute each statement
        executed_count = 0
        for i, statement in enumerate(statements, 1):
            if not statement.strip():
                continue
                
            try:
                logger.info(f"🔄 Executing statement {i}/{len(statements)}")
                logger.debug(f"SQL: {statement[:100]}...")
                
                cursor.execute(statement)
                executed_count += 1
                
                # Check if this was a DO block (which might have output)
                if statement.strip().startswith('DO $$'):
                    # Fetch any notices from the DO block
                    notices = conn.notices
                    if notices:
                        for notice in notices:
                            logger.info(f"📢 Notice: {notice.strip()}")
                        conn.notices = []  # Clear notices
                
            except Exception as e:
                logger.error(f"❌ Error executing statement {i}: {e}")
                logger.error(f"Failed SQL: {statement}")
                conn.rollback()
                return False
        
        # Commit all changes
        conn.commit()
        logger.info(f"✅ Successfully executed {executed_count} statements")
        
        # Verify the migration
        logger.info("🔍 Verifying migration...")
        
        # Check if utc_time column exists
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'alarms' AND column_name = 'utc_time'
        """)
        has_utc_column = cursor.fetchone() is not None
        
        if has_utc_column:
            logger.info("✅ UTC time column exists")
            
            # Check if utc_time column has data
            cursor.execute("SELECT COUNT(*) FROM alarms WHERE utc_time IS NOT NULL")
            utc_count = cursor.fetchone()[0]
            logger.info(f"✅ {utc_count} alarms have UTC time data")
        else:
            logger.warning("⚠️ UTC time column not found")
        
        # Check indexes
        cursor.execute("""
            SELECT indexname 
            FROM pg_indexes 
            WHERE tablename = 'alarms' 
            ORDER BY indexname
        """)
        indexes = [row[0] for row in cursor.fetchall()]
        logger.info(f"✅ Found {len(indexes)} indexes on alarms table")
        
        cursor.close()
        conn.close()
        
        logger.info("🎉 Database migration completed successfully!")
        return True
        
    except psycopg2.Error as e:
        logger.error(f"❌ Database error: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return False
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return False

def test_connection():
    """Test database connection"""
    try:
        db_params = parse_database_url(DATABASE_URL)
        conn = psycopg2.connect(**db_params)
        cursor = conn.cursor()
        
        # Test basic query
        cursor.execute("SELECT version()")
        version = cursor.fetchone()[0]
        logger.info(f"✅ Database connection successful")
        logger.info(f"📊 PostgreSQL version: {version.split(',')[0]}")
        
        # Check if alarms table exists
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'alarms'
            )
        """)
        table_exists = cursor.fetchone()[0]
        
        if table_exists:
            logger.info("✅ Alarms table exists")
            
            # Get table structure
            cursor.execute("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns 
                WHERE table_name = 'alarms'
                ORDER BY ordinal_position
            """)
            columns = cursor.fetchall()
            logger.info(f"📋 Table structure ({len(columns)} columns):")
            for col_name, data_type, nullable in columns:
                logger.info(f"   - {col_name}: {data_type} ({'NULL' if nullable == 'YES' else 'NOT NULL'})")
        else:
            logger.warning("⚠️ Alarms table does not exist")
        
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        logger.error(f"❌ Connection test failed: {e}")
        return False

def main():
    """Main function"""
    logger.info("🚀 Starting Database Migration")
    logger.info("=" * 50)
    
    # Test connection first
    logger.info("🔍 Testing database connection...")
    if not test_connection():
        logger.error("❌ Cannot proceed without database connection")
        sys.exit(1)
    
    logger.info("")
    logger.info("🔄 Running migration...")
    
    # Run the migration
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
        logger.error("")
        logger.error("🔧 Troubleshooting:")
        logger.error("   1. Check database connection settings")
        logger.error("   2. Ensure PostgreSQL is running")
        logger.error("   3. Verify database permissions")
        logger.error("   4. Check migration logs above")
        sys.exit(1)

if __name__ == "__main__":
    main() 