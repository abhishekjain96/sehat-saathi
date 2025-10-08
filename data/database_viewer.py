# database_viewer.py - Ye file bana lo aur run karo

import sqlite3
import pandas as pd
from tabulate import tabulate

def view_database():
    conn = sqlite3.connect('data/sehat_saathi.db')
    
    print("🔍 DATABASE TABLES:")
    tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    for table in tables:
        table_name = table[0]
        print(f"\n📊 TABLE: {table_name}")
        print("-" * 50)
        
        # Get data from table
        data = conn.execute(f"SELECT * FROM {table_name}").fetchall()
        columns = [desc[0] for desc in conn.execute(f"PRAGMA table_info({table_name})").fetchall()]
        
        if data:
            # Display as table
            df = pd.DataFrame(data, columns=columns)
            print(tabulate(df, headers='keys', tablefmt='grid', showindex=False))
        else:
            print("No data found")
    
    conn.close()

if __name__ == '__main__':
    view_database()