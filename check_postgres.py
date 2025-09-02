import psycopg2
from psycopg2.extras import RealDictCursor

# Database configuration (same as in app.py)
DB_HOST = "localhost"
DB_NAME = "alarms_db"
DB_USER = "admin"
DB_PASSWORD = "ZZ4charlie"

try:
    conn = psycopg2.connect(
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST
    )
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    # Check what tables exist
    cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
    tables = cursor.fetchall()
    print("Tables in PostgreSQL database:", [t['table_name'] for t in tables])
    
    # Check if alarms table exists and count alarms
    cursor.execute("SELECT COUNT(*) FROM alarms")
    count = cursor.fetchone()['count']
    print(f"Found {count} alarms in PostgreSQL database")
    
    if count > 0:
        # Show a few sample alarms
        cursor.execute("SELECT * FROM alarms LIMIT 5")
        sample_alarms = cursor.fetchall()
        print("Sample alarms:")
        for alarm in sample_alarms:
            print(f"  - {alarm}")
        
        # Ask if user wants to delete all alarms
        response = input(f"\nDelete all {count} alarms? (y/n): ")
        if response.lower() == 'y':
            cursor.execute("DELETE FROM alarms")
            conn.commit()
            print(f"Deleted {count} alarms from PostgreSQL database")
        else:
            print("Alarms not deleted")
    
    cursor.close()
    conn.close()
    
except Exception as e:
    print(f"Error: {e}") 