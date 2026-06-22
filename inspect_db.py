import sqlite3

db = sqlite3.connect('web/healthopt.db')
c = db.cursor()

# Check if database file exists and has tables
try:
    c.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = c.fetchall()
    print(f"\n=== Tables in healthopt.db ===")
    if not tables:
        print("No tables found (empty database)")
    else:
        for table in tables:
            print(f"  - {table[0]}")
        
        # For each table, show schema and row count
        for table in tables:
            tname = table[0]
            c.execute(f"PRAGMA table_info({tname})")
            columns = c.fetchall()
            print(f"\n--- Table: {tname} ---")
            for col in columns:
                print(f"  {col[1]} ({col[2]})")
            
            c.execute(f"SELECT COUNT(*) FROM {tname}")
            count = c.fetchone()[0]
            print(f"  Total rows: {count}")
            
            # Sample first 3 rows if table has data
            if count > 0:
                c.execute(f"SELECT * FROM {tname} LIMIT 3")
                rows = c.fetchall()
                print(f"  Sample data (first 3 rows):")
                for row in rows:
                    print(f"    {row}")
except Exception as e:
    print(f"Error: {e}")
finally:
    db.close()
