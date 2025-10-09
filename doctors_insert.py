import sqlite3
import os

def insert_doctors():
    # Use same database path as app
    db_path = 'sehat_saathi.db'
    if os.environ.get('RENDER'):
        db_path = '/var/data/sehat_saathi.db'
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    doctors = [
        ('Dr. Ravi Sharma', 'General Physician', 'Free', '+919876543210', 
         'https://wa.me/919876543210', 'Hindi,English', 'active', 10, 4.5),
        ('Dr. Priya Mehta', 'Pediatrics', '₹50', '+919812345678', 
         'https://wa.me/919812345678', 'Hindi,English', 'active', 8, 4.7),
        ('Dr. Amit Kumar', 'Cardiology', '₹200', '+919887766554', 
         'https://wa.me/919887766554', 'Hindi,English', 'active', 15, 4.8),
        ('Dr. Sunita Patel', 'Dermatology', '₹150', '+919776655443', 
         'https://wa.me/919776655443', 'Hindi,English,Gujarati', 'active', 12, 4.6)
    ]
    
    # Clear and insert
    cursor.execute('DELETE FROM doctors')
    cursor.executemany('''
        INSERT INTO doctors (name, specialization, fee, contact, online_link, languages, status, experience_years, rating)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', doctors)
    
    conn.commit()
    
    # Verify
    count = cursor.execute('SELECT COUNT(*) FROM doctors').fetchone()[0]
    print(f"✅ Inserted {count} doctors")
    
    conn.close()

if __name__ == '__main__':
    insert_doctors()