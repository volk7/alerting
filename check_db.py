import sqlite3

try:
    conn = sqlite3.connect('alarms.db')
    cursor = conn.cursor()
    
    # Check what tables exist
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    print("Tables in database:", tables)
    
    # If alarms table exists, check count and clear
    if ('alarms',) in tables:
        cursor.execute("SELECT COUNT(*) FROM alarms")
        count = cursor.fetchone()[0]
        print(f"Found {count} alarms in database")
        
        if count > 0:
            cursor.execute("DELETE FROM alarms")
            conn.commit()
            print(f"Deleted {count} alarms")
        else:
            print("No alarms to delete")
    else:
        print("No 'alarms' table found")
    
    conn.close()
    
except Exception as e:
    print(f"Error: {e}") 