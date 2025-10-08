# live_monitor.py - Ye alag file bana lo

import sqlite3
import time
from datetime import datetime

def live_monitor():
    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        print(f"🕒 Live Database Monitor - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)
        
        conn = sqlite3.connect('data/sehat_saathi.db')
        
        # Real-time counts
        patients = conn.execute("SELECT COUNT(*) FROM patients").fetchone()[0]
        appointments = conn.execute("SELECT COUNT(*) FROM appointments").fetchone()[0]
        pending = conn.execute("SELECT COUNT(*) FROM appointments WHERE status='pending'").fetchone()[0]
        confirmed = conn.execute("SELECT COUNT(*) FROM appointments WHERE status='confirmed'").fetchone()[0]
        queries = conn.execute("SELECT COUNT(*) FROM health_queries").fetchone()[0]
        
        print(f"👥 Patients: {patients}")
        print(f"📅 Total Appointments: {appointments}")
        print(f"⏳ Pending: {pending} | ✅ Confirmed: {confirmed}")
        print(f"🩺 Health Queries: {queries}")
        
        # Recent appointments
        print(f"\n🆕 Recent Appointments:")
        recent = conn.execute('''
            SELECT a.id, p.name, a.hospital_name, a.status, a.created_at 
            FROM appointments a 
            JOIN patients p ON a.patient_id = p.id 
            ORDER BY a.created_at DESC LIMIT 5
        ''').fetchall()
        
        for apt in recent:
            print(f"  {apt[0]}: {apt[1]} - {apt[2]} ({apt[3]}) - {apt[4]}")
        
        conn.close()
        print(f"\n🔄 Refreshing in 10 seconds... (Ctrl+C to stop)")
        time.sleep(10)

if __name__ == '__main__':
    live_monitor()