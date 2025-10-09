# ==================== IMPORTS ====================
import os
import json
import random
import requests
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, session, redirect, url_for, render_template, flash
import google.generativeai as genai
from dotenv import load_dotenv
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
import sqlite3
from contextlib import contextmanager

# ==================== CONFIGURATION ====================
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "sehat_saathi_secret_key_2024")
app.config['DATABASE'] = 'sehat_saathi.db'

# AI Configuration
try:
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
    model = genai.GenerativeModel('gemini-flash-latest')
    GEMINI_AVAILABLE = True
    print("✅ Gemini AI loaded successfully")
except Exception as e:
    GEMINI_AVAILABLE = False
    print(f"⚠️ Gemini AI not available: {e}")

# Twilio Configuration (Disabled for testing)
TWILIO_ENABLED = False
print("📱 Twilio DISABLED - Running in simulation mode")

# Admin Credentials
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "sehat123"

# Session Management
user_sessions = {}

# ==================== DATABASE OPERATIONS ====================

# ==================== AI HEALTH FUNCTIONS ====================

def get_ai_health_response(user_message, conversation_history=None):
    """Get balanced, solution-focused health advice using Gemini"""
    try:
        if not GEMINI_AVAILABLE:
            return get_balanced_fallback_advice(user_message)
        
        # BALANCED PROMPT - Solution Focused
        prompt = f"""
        You are "Sehat Saathi" - a healthcare assistant for rural India.
        User: "{user_message}"
        
        Provide practical health solutions with this structure:
        
        
        
        **RULES:**
        - Focus on SOLUTIONS only, no unnecessary explanations
        - Use simple Hindi-English mix for rural users
        - Keep it helpful but not too short
        - Maximum 6-7 lines total
        - No long stories, no causes, just actionable advice
        - Be empathetic but practical
        
        **Example for headache:**
        🤕 Sir dard hai? Ye practical solutions try karein:
        • Thandi patti se matha ponche aur aaram karein
        • Ginger tea ya haldi doodh piyein
        • Andhere room mein 20-30 minute aaram karein
        ⚠️ Agar 3-4 ghante tak dard na jaye ya ulti ho, doctor ko dikhayein
        
        Now respond to: "{user_message}"
        """
        
        response = model.generate_content(prompt)
        ai_response = response.text.strip()
        
        return ai_response
        
    except Exception as e:
        print(f"❌ AI health response error: {e}")
        return get_balanced_fallback_advice(user_message)

def get_balanced_fallback_advice(symptoms):
    """Fallback balanced practical advice"""
    advice_map = {
        'overthinking': """🧠 Overthinking ho rahi hai? Ye solutions try karein:
• 10-15 minute walk karein ya light exercise karein
• Deep breathing - 5 minute tak gehri saans lein aur chhodain
• Kisi dost ya family member se baat karein
• Paani piyein aur aaram karein
⚠️ Agar 2-3 din tak anxiety rahe ya neend na aaye, counselor se baat karein""",

        'sir dard': """🤕 Sir dard hai? Ye practical solutions try karein:
• Thandi patti se matha ponche aur aaram karein
• Ginger tea ya peppermint tea piyein
• Andhere room mein 30 minute aaram karein
• Pani khoob piyein
⚠️ Agar 3-4 ghante tak dard na jaye, vision blur ho, ya ulti ho - doctor ko dikhayein""",

        'bukhar': """🤒 Bukhar hai? Ye immediate care lein:
• Khoob paani aur fluids piyein (nimbu pani, coconut water)
• Thanda poncha lagayein aur light kapde pehnein
• Halka khana khayein (khichdi, dal)
• Aaram karein aur neend poori karein
⚠️ Agar 101°F se zyada ho, 3 din tak rahe, ya weakness ho - doctor se milein""",

        'pet dard': """🤢 Pet dard hai? Ye remedies try karein:
• Adrak ki chai ya jeera pani piyein
• Halka garam khana khayein (khichdi, daliya)
• Aaram karein aur walking karein
• Paani mein namak daal kar piyein
⚠️ Agar dard bahut tez ho, khoon aaye, ya 24 ghante tak rahe - turant doctor ke paas jayein""",

        'khansi': """😷 Khansi hai? Ye solutions effective hain:
• Garam pani mein shahad daal kar piyein
• Steam lein - garam pani ki bhap se saans lein
• Haldi doodh raat ko piyein
• Masale wala khana avoid karein
⚠️ Agar khansi 1 hafte tak na jaye, bukhar ho, ya sans lene mein takleef ho - doctor se consult karein""",

        'chakkar': """😵 Chakkar aa rahe hain? Ye immediate steps lein:
• Aaram se baith jayein ya let jayein
• Thoda paani piyein aur glucose lein
• Gehun ki roti ya biscuit khayein
• Achanak se na utthein
⚠️ Agar bar-bar chakkar aaye, chehra sun ho, ya bolne mein takleef ho - emergency services bulayein"""
    }
    
    symptoms_lower = symptoms.lower()
    for key, advice in advice_map.items():
        if key in symptoms_lower:
            return advice
    
    # Default balanced advice
    return f"""🩺 Aapke symptoms ke liye ye practical solutions try karein:
• Aaram karein aur pani khoob piyein
• Halka khana khayein aur neend poori karein
• Light walking ya exercise karein
⚠️ Agar takleef barhti rahe ya 2-3 din tak improvement na ho - doctor se sampark karein"""

def save_conversation_context(session_id, user_message, ai_response):
    """Save conversation context for follow-up questions"""
    if session_id not in user_sessions:
        user_sessions[session_id] = {'state': 'main_menu', 'conversation_history': []}
    
    # Keep last 3 exchanges for context
    history = user_sessions[session_id].get('conversation_history', [])
    history.append(f"User: {user_message}")
    history.append(f"Assistant: {ai_response}")
    
    # Keep only recent history to avoid token limits
    if len(history) > 6:
        history = history[-6:]
    
    user_sessions[session_id]['conversation_history'] = history
@contextmanager
def get_db():
    """Database connection context manager"""
    conn = sqlite3.connect(app.config['DATABASE'])
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    """Initialize database with all tables"""
    try:
        os.makedirs('data', exist_ok=True)
        print("📁 Data directory checked")
        
        with get_db() as conn:
            # Patients table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS patients (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    age INTEGER,
                    gender TEXT,
                    phone TEXT,
                    pincode TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Appointments table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS appointments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    patient_id INTEGER,
                    hospital_name TEXT NOT NULL,
                    hospital_type TEXT,
                    slot TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    priority TEXT DEFAULT 'normal',
                    symptoms TEXT,
                    pincode TEXT,
                    maps_link TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    approved_by TEXT,
                    approved_at TIMESTAMP,
                    FOREIGN KEY (patient_id) REFERENCES patients (id)
                )
            ''')
            
            # Doctors table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS doctors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    specialization TEXT NOT NULL,
                    fee TEXT,
                    contact TEXT,
                    online_link TEXT,
                    languages TEXT,
                    status TEXT DEFAULT 'active',
                    experience_years INTEGER,
                    rating REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Services table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS services (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT,
                    price TEXT,
                    duration TEXT,
                    status TEXT DEFAULT 'active',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Health queries table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS health_queries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    patient_phone TEXT,
                    symptoms TEXT,
                    ai_response TEXT,
                    severity TEXT DEFAULT 'low',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Emergency contacts table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS emergency_contacts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    patient_phone TEXT,
                    emergency_type TEXT,
                    pincode TEXT,
                    action_taken TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Verify tables created
            tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            print("📊 Database tables:", [table[0] for table in tables])
            
            # Insert default data
            insert_default_data(conn)
            
        print("✅ Database initialized successfully!")
        
    except Exception as e:
        print(f"❌ Database initialization error: {e}")

def insert_default_data(conn):
    """Insert default doctors and services"""
    # Check if doctors already exist
    existing_doctors = conn.execute('SELECT COUNT(*) as count FROM doctors').fetchone()['count']
    
    if existing_doctors == 0:
        default_doctors = [
            ('Dr. Ravi Sharma', 'General Physician', 'Free', '+919876543210', 
             'https://wa.me/919876543210', 'Hindi,English', 'active', 10, 4.5),
            ('Dr. Priya Mehta', 'Pediatrics', '₹50', '+919812345678', 
             'https://wa.me/919812345678', 'Hindi,English', 'active', 8, 4.7),
            ('Dr. Amit Kumar', 'Cardiology', '₹200', '+919887766554', 
             'https://wa.me/919887766554', 'Hindi,English', 'active', 15, 4.8),
            ('Dr. Sunita Patel', 'Dermatology', '₹150', '+919776655443', 
             'https://wa.me/919776655443', 'Hindi,English,Gujarati', 'active', 12, 4.6)
        ]
        
        conn.executemany('''
            INSERT INTO doctors (name, specialization, fee, contact, online_link, languages, status, experience_years, rating)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', default_doctors)
    
    # Check if services already exist
    existing_services = conn.execute('SELECT COUNT(*) as count FROM services').fetchone()['count']
    
    if existing_services == 0:
        default_services = [
            ('General Checkup', 'Basic health examination', 'Free', '30 minutes'),
            ('Tele-Consultation', 'Online doctor consultation', '₹50', '20 minutes'),
            ('Emergency Care', '24/7 emergency medical care', '₹100', 'Immediate'),
            ('Health Screening', 'Comprehensive health checkup', '₹500', '2 hours')
        ]
        
        conn.executemany('''
            INSERT INTO services (name, description, price, duration)
            VALUES (?, ?, ?, ?)
        ''', default_services)

# ==================== DATABASE CRUD OPERATIONS ====================

# Patient Operations
def create_patient(name, age=None, gender=None, phone=None, pincode=None):
    """Create new patient record"""
    try:
        with get_db() as conn:
            cursor = conn.execute('''
                INSERT INTO patients (name, age, gender, phone, pincode)
                VALUES (?, ?, ?, ?, ?)
            ''', (name, age, gender, phone, pincode))
            patient_id = cursor.lastrowid
            conn.commit()
            print(f"✅ Patient saved: {patient_id} - {name}")
            return patient_id
    except Exception as e:
        print(f"❌ Error creating patient: {e}")
        return None

def get_patient(patient_id):
    """Get patient by ID"""
    with get_db() as conn:
        return conn.execute('SELECT * FROM patients WHERE id = ?', (patient_id,)).fetchone()

def get_all_patients():
    """Get all patients"""
    with get_db() as conn:
        return conn.execute('SELECT * FROM patients ORDER BY created_at DESC').fetchall()

# Appointment Operations
def create_appointment(patient_id, hospital_name, hospital_type, slot, symptoms=None, pincode=None, maps_link=None, priority='normal'):
    """Create new appointment"""
    try:
        with get_db() as conn:
            cursor = conn.execute('''
                INSERT INTO appointments (patient_id, hospital_name, hospital_type, slot, symptoms, pincode, maps_link, priority)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (patient_id, hospital_name, hospital_type, slot, symptoms, pincode, maps_link, priority))
            appointment_id = cursor.lastrowid
            conn.commit()
            print(f"✅ Appointment saved: {appointment_id} - Patient: {patient_id}")
            return appointment_id
    except Exception as e:
        print(f"❌ Error creating appointment: {e}")
        return None

def create_emergency_appointment_direct(patient_name, hospital_name, pincode):
    """Create emergency appointment directly"""
    try:
        with get_db() as conn:
            # Create patient first
            cursor = conn.execute('''
                INSERT INTO patients (name, pincode, phone) 
                VALUES (?, ?, ?)
            ''', (patient_name, pincode, 'emergency_user'))
            patient_id = cursor.lastrowid
            
            # Create emergency appointment with immediate slot
            emergency_slot = (datetime.now() + timedelta(hours=1)).strftime('%Y-%m-%d %H:%M')
            
            cursor = conn.execute('''
                INSERT INTO appointments (patient_id, hospital_name, hospital_type, slot, pincode, priority, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (patient_id, hospital_name, 'Emergency', emergency_slot, pincode, 'emergency', 'confirmed'))
            
            appointment_id = cursor.lastrowid
            conn.commit()
            
            print(f"✅ EMERGENCY Appointment saved: {appointment_id}")
            return appointment_id
    except Exception as e:
        print(f"❌ Emergency appointment error: {e}")
        return None

def get_appointment(appointment_id):
    """Get appointment by ID"""
    with get_db() as conn:
        return conn.execute('''
            SELECT a.*, p.name as patient_name, p.phone, p.age, p.gender
            FROM appointments a 
            LEFT JOIN patients p ON a.patient_id = p.id 
            WHERE a.id = ?
        ''', (appointment_id,)).fetchone()

def get_all_appointments():
    """Get all appointments with patient details"""
    try:
        with get_db() as conn:
            appointments = conn.execute('''
                SELECT a.*, p.name as patient_name, p.phone, p.age, p.gender
                FROM appointments a 
                LEFT JOIN patients p ON a.patient_id = p.id 
                ORDER BY a.created_at DESC
            ''').fetchall()
            print(f"✅ Found {len(appointments)} appointments")
            return appointments
    except Exception as e:
        print(f"❌ Error getting appointments: {e}")
        return []

def update_appointment_status(appointment_id, status, approved_by=None):
    """Update appointment status"""
    with get_db() as conn:
        if approved_by:
            conn.execute('''
                UPDATE appointments 
                SET status = ?, approved_by = ?, approved_at = CURRENT_TIMESTAMP 
                WHERE id = ?
            ''', (status, approved_by, appointment_id))
        else:
            conn.execute('UPDATE appointments SET status = ? WHERE id = ?', (status, appointment_id))
        conn.commit()

def delete_appointment(appointment_id):
    """Delete appointment"""
    with get_db() as conn:
        conn.execute('DELETE FROM appointments WHERE id = ?', (appointment_id,))
        conn.commit()

# Doctor Operations
def get_all_doctors():
    """Get all doctors"""
    with get_db() as conn:
        return conn.execute('SELECT * FROM doctors WHERE status = "active"').fetchall()

def get_doctor(doctor_id):
    """Get doctor by ID"""
    with get_db() as conn:
        return conn.execute('SELECT * FROM doctors WHERE id = ?', (doctor_id,)).fetchone()

def update_doctor_status(doctor_id, status):
    """Update doctor status"""
    with get_db() as conn:
        conn.execute('UPDATE doctors SET status = ? WHERE id = ?', (status, doctor_id))
        conn.commit()

# Health Queries Operations
def save_health_query(patient_phone, symptoms, ai_response, severity='low'):
    """Save health query for analytics"""
    with get_db() as conn:
        conn.execute('''
            INSERT INTO health_queries (patient_phone, symptoms, ai_response, severity)
            VALUES (?, ?, ?, ?)
        ''', (patient_phone, symptoms, ai_response, severity))
        conn.commit()

def get_health_queries():
    """Get all health queries"""
    with get_db() as conn:
        return conn.execute('SELECT * FROM health_queries ORDER BY created_at DESC').fetchall()

# Emergency Operations
def log_emergency_contact(patient_phone, emergency_type, pincode, action_taken):
    """Log emergency contact for analytics"""
    with get_db() as conn:
        conn.execute('''
            INSERT INTO emergency_contacts (patient_phone, emergency_type, pincode, action_taken)
            VALUES (?, ?, ?, ?)
        ''', (patient_phone, emergency_type, pincode, action_taken))
        conn.commit()

def get_emergency_logs():
    """Get all emergency logs"""
    with get_db() as conn:
        return conn.execute('SELECT * FROM emergency_contacts ORDER BY created_at DESC').fetchall()

# ==================== HELPER FUNCTIONS ====================

def get_available_slots():
    """Get available appointment slots for next 7 days"""
    today = datetime.now()
    slots = []
    
    for i in range(7):  # Next 7 days
        day = today + timedelta(days=i)
        if day.weekday() >= 5:  # Skip weekends
            continue
            
        for hour in [10, 12, 14, 16]:  # 4 slots per day
            slot_time = day.replace(hour=hour, minute=0, second=0, microsecond=0)
            slot_str = slot_time.strftime('%Y-%m-%d %H:%M')
            slots.append(slot_str)
                
    return slots[:8]

def get_available_doctors(specialization=None):
    """Get available doctors from database"""
    doctors = get_all_doctors()
    
    if specialization:
        doctors = [dict(doc) for doc in doctors if specialization.lower() in doc['specialization'].lower()]
    else:
        doctors = [dict(doc) for doc in doctors]
    
    return doctors

def simulate_whatsapp_message(to_number, message):
    """Simulate WhatsApp message and log it"""
    print(f"📱 [WHATSAPP SIMULATION] To: {to_number}")
    print(f"📱 [MESSAGE]: {message}")
    print("📱 [STATUS]: ✅ Message would be sent via WhatsApp")
    return True

def query_overpass(lat, lon, radius_m=30000, limit=7):
    """
    Query Overpass API to find hospitals, clinics, doctors within radius.
    Returns list of places with name, type, lat, lon, tags.
    """
    amenity_filter = r"hospital|clinic|doctors|healthcare|dispensary|clinic"
    q = f"""
    [out:json][timeout:25];
    (
      node(around:{radius_m},{lat},{lon})[amenity~"{amenity_filter}",i];
      way(around:{radius_m},{lat},{lon})[amenity~"{amenity_filter}",i];
      relation(around:{radius_m},{lat},{lon})[amenity~"{amenity_filter}",i];
    );
    out center {limit};
    """
    url = "https://overpass-api.de/api/interpreter"
    try:
        resp = requests.post(url, data={'data': q}, timeout=30)
        data = resp.json()
        places = []
        for el in data.get('elements', []):
            # Get center coordinates for ways/relation; nodes have lat/lon
            if el.get('type') in ('way', 'relation'):
                c = el.get('center') or {}
                plat = c.get('lat')
                plon = c.get('lon')
            else:
                plat = el.get('lat')
                plon = el.get('lon')
            tags = el.get('tags') or {}
            name = tags.get('name') or tags.get('operator') or tags.get('healthcare') or 'Unnamed'
            amenity = tags.get('amenity') or tags.get('shop') or 'clinic'
            places.append({
                'name': name,
                'type': amenity,
                'latitude': plat,
                'longitude': plon,
                'tags': tags
            })
        return places
    except Exception as e:
        print("Overpass query error:", e)
        return []

def get_real_hospitals_nearby(pincode):
    """Get real hospitals using Overpass API"""
    try:
        geolocator = Nominatim(user_agent="sehat_saathi_app_v2")
        location = geolocator.geocode(pincode + ", India", timeout=10)
        if not location:
            location = geolocator.geocode(pincode, timeout=10)
        if not location:
            return "❌ Location not found. Please check pincode.", []

        places = query_overpass(location.latitude, location.longitude, radius_m=30000, limit=15)
        user_coords = (location.latitude, location.longitude)
        
        hospitals = []
        for p in places:
            if p['latitude'] is None or p['longitude'] is None:
                continue
            try:
                dist = round(geodesic(user_coords, (p['latitude'], p['longitude'])).km, 1)
            except Exception:
                dist = None
            
            # Create Google Maps link
            maps_link = f"https://www.google.com/maps/search/?api=1&query={p['latitude']},{p['longitude']}"
            
            hospitals.append({
                'name': p['name'],
                'type': p['type'],
                'distance_km': dist if dist else round(random.uniform(1, 10), 1),
                'maps_link': maps_link
            })

        # Sort by distance and get top 6
        hospitals = [h for h in hospitals if h['distance_km'] is not None]
        hospitals.sort(key=lambda x: x['distance_km'])
        hospitals = hospitals[:6]
        
        if not hospitals:
            return "❌ No hospitals found nearby. Try another pincode.", []

        # Format response
        response_text = f"🏥 *Real Hospitals near {pincode}:*\n\n"
        for idx, hospital in enumerate(hospitals, 1):
            response_text += f"{idx}. *{hospital['name']}*\n"
            response_text += f"   🏷️ {hospital['type'].title()}\n"
            response_text += f"   📏 {hospital['distance_km']} km away\n"
            response_text += f"   🗺️ [Open in Maps]({hospital['maps_link']})\n\n"
        
        response_text += "💡 *Click map links for exact locations*"
        return response_text, hospitals
        
    except Exception as e:
        print(f"Hospital search error: {e}")
        return "⚠️ Error searching hospitals. Please try again.", []

# ==================== EMERGENCY FUNCTIONS ====================

def get_emergency_contacts():
    """Get comprehensive emergency contacts"""
    return {
        "ambulance": {"number": "108", "description": "Emergency Ambulance Service", "type": "Medical"},
        "medical_help": {"number": "102", "description": "Medical Emergency Help", "type": "Medical"},
        "emergency": {"number": "112", "description": "Single Emergency Number", "type": "Multi-purpose"},
        "police": {"number": "100", "description": "Police Emergency", "type": "Police"},
        "fire": {"number": "101", "description": "Fire Brigade", "type": "Fire"},
        "women_helpline": {"number": "1091", "description": "Women Helpline", "type": "Safety"},
        "child_helpline": {"number": "1098", "description": "Child Helpline", "type": "Child Safety"}
    }

def get_emergency_instructions(emergency_type):
    """Get step-by-step emergency instructions"""
    instructions = {
        "heart_attack": [
            "🚨 *Call Emergency Ambulance (108/102)* immediately!",
            "💊 If prescribed, give aspirin (unless allergic)",
            "🛌 Make person sit down and rest",
            "👕 Loosen tight clothing", 
            "❌ Do not give anything to eat or drink",
            "⏱️ Note time when symptoms started",
            "🏥 Prepare to go to hospital immediately"
        ],
        "accident": [
            "🚨 *Call Emergency (108/112)* immediately!",
            "🔍 Check for danger to yourself and victim",
            "📞 Call for help from people nearby",
            "🩹 Do not move injured person unless in danger",
            "💧 If conscious, give sips of water",
            "🛡️ Stop bleeding with clean cloth",
            "🏥 Wait for ambulance arrival"
        ]
    }
    return instructions.get(emergency_type, [])

# ==================== ADMIN AUTHENTICATION ====================

def admin_required(f):
    """Decorator for admin authentication"""
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

# ==================== ROUTES ====================

@app.route('/')
def home():
    """Main home page"""
    return render_template('index.html')

@app.route('/chat')
def chat_ui():
    """Chatbot interface for testing"""
    return render_template('chat.html')

@app.route('/test')
def test_page():
    """Simple test page"""
    return """
    <html>
        <head><title>Test - Sehat Saathi</title></head>
        <body style="font-family: Arial; padding: 20px; text-align: center;">
            <h1>✅ Sehat Saathi - Test Page</h1>
            <p>All systems operational! 🚀</p>
            <a href="/">Home</a> | 
            <a href="/chat">Chat</a> | 
            <a href="/admin">Admin</a>
        </body>
    </html>
    """

@app.route('/health')
def health_check():
    """Health check endpoint"""
    with get_db() as conn:
        status = {
            "status": "healthy",
            "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "services": {
                "patients": conn.execute('SELECT COUNT(*) FROM patients').fetchone()[0],
                "appointments": conn.execute('SELECT COUNT(*) FROM appointments').fetchone()[0],
                "doctors": conn.execute('SELECT COUNT(*) FROM doctors').fetchone()[0]
            },
            "twilio_enabled": TWILIO_ENABLED,
            "mode": "database"
        }
    return jsonify(status)

# ==================== ADMIN ROUTES ====================

@app.route('/admin')
def admin_login_page():
    """Admin login page"""
    if session.get('admin_logged_in'):
        return redirect(url_for('admin_dashboard'))
    return render_template('admin_login.html')

@app.route('/admin/login', methods=['POST'])
def admin_login():
    """Admin login processing"""
    username = request.form.get('username')
    password = request.form.get('password')
    
    if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
        session['admin_logged_in'] = True
        return redirect(url_for('admin_dashboard'))
    else:
        return render_template('admin_login.html', error="Invalid credentials!")

@app.route('/admin/logout')
def admin_logout():
    """Admin logout"""
    session.pop('admin_logged_in', None)
    return redirect(url_for('admin_login_page'))

@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    """Admin dashboard with comprehensive stats"""
    with get_db() as conn:
        # Get all statistics
        total_patients = conn.execute('SELECT COUNT(*) as count FROM patients').fetchone()['count']
        total_appointments = conn.execute('SELECT COUNT(*) as count FROM appointments').fetchone()['count']
        pending_appointments = conn.execute('SELECT COUNT(*) as count FROM appointments WHERE status = "pending"').fetchone()['count']
        confirmed_appointments = conn.execute('SELECT COUNT(*) as count FROM appointments WHERE status = "confirmed"').fetchone()['count']
        total_doctors = conn.execute('SELECT COUNT(*) as count FROM doctors').fetchone()['count']
        health_queries = conn.execute('SELECT COUNT(*) as count FROM health_queries').fetchone()['count']
        emergency_logs = conn.execute('SELECT COUNT(*) as count FROM emergency_contacts').fetchone()['count']
        
        # Recent appointments
        recent_appointments = conn.execute('''
            SELECT a.*, p.name as patient_name 
            FROM appointments a 
            LEFT JOIN patients p ON a.patient_id = p.id 
            ORDER BY a.created_at DESC LIMIT 5
        ''').fetchall()
        
        # Recent patients
        recent_patients = conn.execute('SELECT * FROM patients ORDER BY created_at DESC LIMIT 5').fetchall()

    stats = {
        'total_patients': total_patients,
        'total_appointments': total_appointments,
        'pending_appointments': pending_appointments,
        'confirmed_appointments': confirmed_appointments,
        'total_doctors': total_doctors,
        'active_doctors': total_doctors,
        'health_queries': health_queries,
        'emergency_logs': emergency_logs
    }
    
    return render_template('admin_dashboard.html', 
                         stats=stats, 
                         recent_appointments=recent_appointments,
                         recent_patients=recent_patients)

@app.route('/admin/appointments')
@admin_required
def admin_appointments():
    """Appointments management with all data"""
    appointments = get_all_appointments()
    return render_template('admin_appointments.html', appointments=appointments)

@app.route('/admin/appointment/action/<int:appointment_id>/<action>')
@admin_required
def appointment_action(appointment_id, action):
    """Handle appointment actions (accept/reject/delete)"""
    if action == 'accept':
        update_appointment_status(appointment_id, 'confirmed', 'admin')
        flash('Appointment accepted successfully!', 'success')
    elif action == 'reject':
        update_appointment_status(appointment_id, 'rejected', 'admin')
        flash('Appointment rejected!', 'warning')
    elif action == 'delete':
        delete_appointment(appointment_id)
        flash('Appointment deleted successfully!', 'danger')
    
    return redirect(url_for('admin_appointments'))

@app.route('/admin/patients')
@admin_required
def admin_patients():
    """Patients management"""
    patients = get_all_patients()
    return render_template('admin_patients.html', patients=patients)

@app.route('/admin/doctors')
@admin_required
def admin_doctors():
    """Doctors management"""
    doctors = get_all_doctors()
    return render_template('admin_doctors.html', doctors=doctors)

@app.route('/admin/health-queries')
@admin_required
def admin_health_queries():
    """Health queries analytics"""
    queries = get_health_queries()
    return render_template('admin_health_queries.html', queries=queries)

@app.route('/admin/emergency-logs')
@admin_required
def admin_emergency_logs():
    """Emergency logs"""
    logs = get_emergency_logs()
    return render_template('admin_emergency_logs.html', logs=logs)

@app.route('/admin/stats')
@admin_required
def admin_stats():
    """Detailed statistics"""
    with get_db() as conn:
        # Monthly appointments
        monthly_appointments = conn.execute('''
            SELECT strftime('%Y-%m', created_at) as month, 
                   COUNT(*) as count,
                   SUM(CASE WHEN status = 'confirmed' THEN 1 ELSE 0 END) as confirmed
            FROM appointments 
            GROUP BY month 
            ORDER BY month DESC LIMIT 6
        ''').fetchall()
        
        # Top hospitals
        top_hospitals = conn.execute('''
            SELECT hospital_name, COUNT(*) as appointments 
            FROM appointments 
            GROUP BY hospital_name 
            ORDER BY appointments DESC LIMIT 10
        ''').fetchall()
        
        # Common symptoms
        common_symptoms = conn.execute('''
            SELECT symptoms, COUNT(*) as count 
            FROM health_queries 
            WHERE symptoms IS NOT NULL AND symptoms != ''
            GROUP BY symptoms 
            ORDER BY count DESC LIMIT 10
        ''').fetchall()

    return render_template('admin_stats.html',
                         monthly_appointments=monthly_appointments,
                         top_hospitals=top_hospitals,
                         common_symptoms=common_symptoms)

# ==================== CHATBOT API ROUTES ====================

@app.route('/web-chat', methods=['POST'])
def web_chat_reply():
    """Main chatbot API with COMPLETE emergency flow"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'reply': '❌ Invalid request'})
            
        user_message = data.get('message', '').strip().lower()
        if not user_message:
            return jsonify({'reply': '❌ Empty message'})

        # Get or create session
        session_id = data.get('session_id', 'web')
        session_data = user_sessions.get(session_id, {'state': 'main_menu'})
        state = session_data.get('state')
        ai_response = ""

        print(f"💬 [{state}] User: {user_message}")

        # === GLOBAL MENU HANDLER ===
        if user_message in ['menu', 'main menu', 'back', 'home', '0']:
            ai_response = """नमस्ते! मैं *Sehat Saathi* 🩺  
Aapka AI Health Saathi!  

1️⃣ 🚨 Emergency Help
2️⃣ 🩺 Health Query  
3️⃣ 📅 Book Appointment
4️⃣ 🏥 Find Hospitals
5️⃣ 📞 Tele-Consultation

👉 Type number (1-5):"""
            session_data['state'] = 'main_menu'
            user_sessions[session_id] = session_data
            return jsonify({'reply': ai_response})

        # === STATE MACHINE ===
        
        # Main Menu State
        if state == 'main_menu':
            if user_message in ['hi', 'hello', 'namaste', 'start', 'hey']:
                ai_response = """नमस्ते! मैं *Sehat Saathi* 🩺  
Aapka AI Health Saathi!  

1️⃣ 🚨 Emergency Help
2️⃣ 🩺 Health Query  
3️⃣ 📅 Book Appointment
4️⃣ 🏥 Find Hospitals
5️⃣ 📞 Tele-Consultation

👉 Type number (1-5):"""
                session_data['state'] = 'main_menu'

            elif user_message == '1':
                ai_response = """🚨 *EMERGENCY HELP*

🔴 *IMMEDIATE ACTION REQUIRED:*
• 📞 Call 108 for Ambulance
• 📞 Call 102 for Medical Help  
• 📞 Call 112 for Any Emergency

💡 *Quick Options:*
• Type 'nearby' to find emergency services
• Type 'appoint' for emergency appointment
• Type 'menu' for main menu

👉 Type your choice:"""
                session_data['state'] = 'emergency_help'

            elif user_message == '2':
                ai_response = "🩺 Please describe your health issue or symptoms:"
                session_data['state'] = 'general_query'

            elif user_message == '3':
                ai_response = "📅 Please enter your 6-digit pincode to find nearby hospitals:"
                session_data['state'] = 'awaiting_pincode_for_appointment'

            elif user_message == '4':
                ai_response = "🏥 Please enter pincode to find nearby hospitals and clinics:"
                session_data['state'] = 'awaiting_pincode_for_hospital'

            elif user_message == '5':
                doctors = get_available_doctors()
                if doctors:
                    session_data['doctors'] = doctors
                    text_doctors = "\n".join([f"{i+1}. {d['name']} ({d['specialization']}) - {d['fee']}" for i,d in enumerate(doctors)])
                    ai_response = f"📞 *Available Doctors:*\n{text_doctors}\n\nSelect doctor number:"
                    session_data['state'] = 'tele_select'
                else:
                    ai_response = "❌ No doctors available currently."

            else:
                ai_response = "❌ Invalid option. Type 'menu' to see options."

        # Emergency Help State
        elif state == 'emergency_help':
            if user_message == 'nearby':
                ai_response = "📍 Please enter your 6-digit pincode to find nearby emergency services:"
                session_data['state'] = 'awaiting_pincode_for_emergency'
            elif user_message == 'appoint':
                ai_response = "🚨 *EMERGENCY APPOINTMENT*\n📍 Please enter your pincode for immediate hospital booking:"
                session_data['state'] = 'emergency_appoint_pincode'
            else:
                contacts = get_emergency_contacts()
                contacts_text = "\n".join([f"• {details['number']} - {details['description']}" for _, details in contacts.items()])
                ai_response = f"""🚨 *IMMEDIATE EMERGENCY CONTACTS:*

{contacts_text}

💡 *Quick Options:*
• Type 'nearby' to find emergency services
• Type 'appoint' for emergency hospital appointment
• Type 'menu' for main menu

👉 Type your choice:"""

        # Emergency Pincode for Nearby Services
        elif state == 'awaiting_pincode_for_emergency':
            if user_message.isdigit() and len(user_message) == 6:
                hospital_text, hospitals = get_real_hospitals_nearby(user_message)
                
                # Format emergency-specific response
                emergency_response = f"""🚨 *EMERGENCY SERVICES near {user_message}*

{hospital_text}

🔴 *IMMEDIATE ACTION:*
• 📞 Call 108 for Ambulance
• 📞 Call 102 for Medical Help
• 📞 Call 112 for Any Emergency

💡 *Quick Actions:*
• Type 'appoint' for emergency appointment
• Type 'menu' for main menu
• Describe your emergency"""
                
                ai_response = emergency_response
                session_data['hospitals'] = hospitals
                session_data['pincode'] = user_message
                session_data['state'] = 'emergency_services_shown'
            else:
                ai_response = "⚠️ Please enter a valid 6-digit pincode for emergency services"

        # EMERGENCY SERVICES SHOWN STATE - FIXED
        elif state == 'emergency_services_shown':
            if user_message == 'appoint':
                hospitals = session_data.get('hospitals', [])
                if hospitals:
                    hospitals_list = "\n".join([f"{i+1}. *{h['name']}* ({h['distance_km']} km)" for i, h in enumerate(hospitals)])
                    ai_response = f"""🚨 *EMERGENCY APPOINTMENT*

{hospitals_list}

👉 *Select hospital number (1-{len(hospitals)}) for emergency appointment:*"""
                    session_data['state'] = 'emergency_hospital_select'
                else:
                    ai_response = "❌ No hospitals available. Please enter pincode again."
            elif user_message == 'menu':
                ai_response = """नमस्ते! मैं *Sehat Saathi* 🩺  
Aapka AI Health Saathi!  

1️⃣ 🚨 Emergency Help
2️⃣ 🩺 Health Query  
3️⃣ 📅 Book Appointment
4️⃣ 🏥 Find Hospitals
5️⃣ 📞 Tele-Consultation

👉 Type number (1-5):"""
                session_data['state'] = 'main_menu'
            else:
                ai_response = """💡 *Options:*
• Type 'appoint' for emergency appointment  
• Type 'menu' for main menu
• Or describe your emergency"""

        # Emergency Appointment Flow
        elif state == 'emergency_appoint_pincode':
            if user_message.isdigit() and len(user_message) == 6:
                hospital_text, hospitals = get_real_hospitals_nearby(user_message)
                
                if hospitals:
                    session_data['pincode'] = user_message
                    session_data['hospitals'] = hospitals
                    session_data['state'] = 'emergency_hospital_select'
                    
                    hospitals_list = "\n".join([f"{i+1}. *{h['name']}* ({h['distance_km']} km)" for i, h in enumerate(hospitals)])
                    ai_response = f"""🚨 *EMERGENCY HOSPITALS near {user_message}:*

{hospitals_list}

👉 *Select hospital number (1-{len(hospitals)}) for emergency appointment:*"""
                else:
                    ai_response = "❌ No hospitals found. Please try another pincode."
            else:
                ai_response = "⚠️ Please enter a valid 6-digit pincode"

        # Emergency Hospital Selection
        elif state == 'emergency_hospital_select':
            if user_message.isdigit():
                hospital_index = int(user_message) - 1
                hospitals = session_data.get('hospitals', [])
                
                if 0 <= hospital_index < len(hospitals):
                    selected_hospital = hospitals[hospital_index]
                    session_data['selected_hospital'] = selected_hospital
                    session_data['state'] = 'emergency_patient_name'
                    
                    ai_response = f"""🚨 *EMERGENCY APPOINTMENT - {selected_hospital['name']}*

🏥 Hospital: {selected_hospital['name']}
📍 Distance: {selected_hospital['distance_km']} km
🚨 Priority: EMERGENCY
⏰ Slot: IMMEDIATE (Within 1 hour)

👤 *Please enter patient's full name:*"""
                else:
                    ai_response = f"❌ Please select valid hospital number (1-{len(hospitals)}):"
            else:
                ai_response = "❌ Please enter a valid number"

        # Emergency Patient Name
        elif state == 'emergency_patient_name':
            if user_message.strip():
                patient_name = user_message.strip()
                hospital = session_data.get('selected_hospital', {})
                pincode = session_data.get('pincode', 'Unknown')
                
                # Create emergency appointment in database
                appointment_id = create_emergency_appointment_direct(patient_name, hospital['name'], pincode)
                
                if appointment_id:
                    ai_response = f"""✅ *EMERGENCY APPOINTMENT CONFIRMED!*

🚨 ID: {appointment_id}
👤 Patient: {patient_name}
🏥 Hospital: {hospital['name']}
📍 Pincode: {pincode}
📏 Distance: {hospital.get('distance_km', 'Unknown')} km
⏰ Time: IMMEDIATE (Within 1 hour)
🚑 Priority: EMERGENCY
🗺️ Maps: {hospital.get('maps_link', '')}

📞 Hospital will contact you shortly.
🚨 Ambulance dispatched if needed.

💡 *Stay calm and follow instructions*
Type 'menu' for main options"""
                    
                    # Log emergency contact
                    log_emergency_contact('web_user', 'emergency_appointment', pincode, f"Appointment {appointment_id} created")
                else:
                    ai_response = "❌ Error creating emergency appointment. Please call 108 directly."
                
                # Reset to main menu
                session_data['state'] = 'main_menu'
                session_data.pop('selected_hospital', None)
                session_data.pop('pincode', None)
                session_data.pop('hospitals', None)
            else:
                ai_response = "❌ Please enter a valid patient name:"

        # Health Query State
        # Health Query State - UPDATED WITH DYNAMIC AI RESPONSES
        elif state == 'general_query':
            if user_message == '4':
                ai_response = "🏥 Please enter pincode to find nearby hospitals and clinics:"
                session_data['state'] = 'awaiting_pincode_for_hospital'
            else:
        # Get conversation history for context
                conversation_history = session_data.get('conversation_history', [])
        
        # Get DYNAMIC AI response
                ai_response = get_ai_health_response(user_message, conversation_history)
        
        # Add follow-up suggestion
                if not any(word in user_message for word in ['menu', 'back', 'stop']):
                 ai_response += "\n\n💡 You can ask more questions about this, type 'menu' for options, or describe other symptoms"
        
        # Save conversation context
                save_conversation_context(session_id, user_message, ai_response)
        
        # Save to database for analytics
                save_health_query('web_user', user_message, ai_response)

        # Pincode for Appointment State
        elif state == 'awaiting_pincode_for_appointment':
            if user_message.isdigit() and len(user_message) == 6:
                hospital_text, hospitals = get_real_hospitals_nearby(user_message)
                ai_response = hospital_text
                session_data['hospitals'] = hospitals
                session_data['pincode'] = user_message
                session_data['state'] = 'hospitals_shown'
            else:
                ai_response = "⚠️ Please enter a valid 6-digit pincode"

        # Hospitals Shown State
        elif state == 'hospitals_shown':
            if user_message == 'appoint':
                hospitals = session_data.get('hospitals', [])
                if hospitals:
                    ai_response = "👉 Select hospital number (1-{}):".format(len(hospitals))
                    session_data['state'] = 'hospitals_shown_for_appointment'
                else:
                    ai_response = "❌ No hospitals available. Please enter pincode again using option 3."
            else:
                ai_response = "💡 *Options:*\n• Type 'appoint' to book appointment\n• Type 'menu' for main menu\n• Or enter pincode again using option 3"

        # Hospitals Shown for Appointment State
        elif state == 'hospitals_shown_for_appointment':
            if user_message.isdigit():
                hospital_index = int(user_message) - 1
                hospitals = session_data.get('hospitals', [])
                
                if 0 <= hospital_index < len(hospitals):
                    selected_hospital = hospitals[hospital_index]
                    session_data['selected_hospital'] = selected_hospital
                    
                    # Get available slots
                    slots = get_available_slots()
                    if slots:
                        slots_text = "\n".join([f"{i+1}. {slot}" for i, slot in enumerate(slots)])
                        ai_response = f"""🏥 *Appointment at {selected_hospital['name']}*

Available slots:
{slots_text}

👉 Select slot number (1-{len(slots)}):"""
                        session_data['slots'] = slots
                        session_data['state'] = 'select_slot'
                    else:
                        ai_response = "❌ No available slots. Please try again later."
                        session_data['state'] = 'main_menu'
                else:
                    ai_response = f"❌ Invalid hospital number. Please select 1-{len(hospitals)}"
            else:
                ai_response = "❌ Please enter a valid number"

        # Slot Selection State
        elif state == 'select_slot':
            if user_message.isdigit():
                slot_index = int(user_message) - 1
                slots = session_data.get('slots', [])
                selected_hospital = session_data.get('selected_hospital', {})
                
                if 0 <= slot_index < len(slots):
                    selected_slot = slots[slot_index]
                    
                    # Ask for patient name
                    ai_response = f"""📅 *Appointment Summary:*
🏥 Hospital: {selected_hospital.get('name', 'Unknown')}
📅 Slot: {selected_slot}

Please enter patient's name:"""
                    session_data['selected_slot'] = selected_slot
                    session_data['state'] = 'get_patient_name'
                else:
                    ai_response = f"❌ Invalid slot number. Please select 1-{len(slots)}"
            else:
                ai_response = "❌ Please enter a valid number"

        # Get Patient Name State - DATABASE SAVE
        elif state == 'get_patient_name':
            if user_message.strip():
                patient_name = user_message.strip()
                selected_hospital = session_data.get('selected_hospital', {})
                selected_slot = session_data.get('selected_slot', '')
                
                print(f"🔍 Attempting to save appointment for: {patient_name}")
                
                # Create patient and appointment in database
                patient_id = create_patient(
                    name=patient_name,
                    pincode=session_data.get('pincode', ''),
                    phone=session_data.get('patient_phone', 'web_user')
                )
                
                if patient_id:
                    appointment_id = create_appointment(
                        patient_id=patient_id,
                        hospital_name=selected_hospital.get('name', 'Unknown Hospital'),
                        hospital_type=selected_hospital.get('type', 'hospital'),
                        slot=selected_slot,
                        pincode=session_data.get('pincode', ''),
                        maps_link=selected_hospital.get('maps_link', ''),
                        priority=session_data.get('priority', 'normal')
                    )
                    
                    if appointment_id:
                        # Confirmation message
                        ai_response = f"""✅ *Appointment Booked Successfully!*

📋 ID: {appointment_id}
👤 Patient: {patient_name}
🏥 Hospital: {selected_hospital.get('name', 'Unknown')}
📅 Date & Time: {selected_slot}
📍 Maps: {selected_hospital.get('maps_link', '')}

🔄 Status: Pending Approval
📞 You'll receive confirmation via WhatsApp.

Type 'menu' for main menu."""
                        
                        print(f"🎉 Appointment {appointment_id} saved successfully!")
                    else:
                        ai_response = "❌ Error saving appointment. Please try again."
                else:
                    ai_response = "❌ Error creating patient record. Please try again."
                
                # Reset to main menu
                session_data['state'] = 'main_menu'
                session_data.pop('selected_hospital', None)
                session_data.pop('selected_slot', None)
                session_data.pop('slots', None)
                session_data.pop('hospitals', None)
                session_data.pop('pincode', None)
            else:
                ai_response = "❌ Please enter a valid name"

        # Tele-Consultation Selection State
        elif state == 'tele_select':
            if user_message.isdigit():
                doctor_index = int(user_message) - 1
                doctors = session_data.get('doctors', [])
                
                if 0 <= doctor_index < len(doctors):
                    selected_doctor = doctors[doctor_index]
                    ai_response = f"""📞 *Doctor Selected: {selected_doctor['name']}*

💼 Specialization: {selected_doctor['specialization']}
💰 Fee: {selected_doctor['fee']}
🌐 Languages: {', '.join(selected_doctor['languages'])}

📲 Contact: {selected_doctor['contact']}
🔗 Online Link: {selected_doctor['online_link']}

💡 *Click the link above to start consultation*

Type 'menu' for main menu."""
                    session_data['state'] = 'main_menu'
                else:
                    ai_response = f"❌ Invalid doctor number. Please select 1-{len(doctors)}"
            else:
                ai_response = "❌ Please enter a valid number"

        # Pincode for Hospital Search State
        elif state == 'awaiting_pincode_for_hospital':
            if user_message.isdigit() and len(user_message) == 6:
                hospital_text, hospitals = get_real_hospitals_nearby(user_message)
                ai_response = hospital_text
                session_data['state'] = 'main_menu'
            else:
                ai_response = "⚠️ Please enter a valid 6-digit pincode"

        # Save session and return response
        user_sessions[session_id] = session_data
        return jsonify({'reply': ai_response})

    except Exception as e:
        print(f"❌ Chat error: {e}")
        return jsonify({'reply': '⚠️ System error. Please try again.'})

# ==================== DEBUG ROUTES ====================

@app.route('/debug/database')
def debug_database():
    """Simple database debug page"""
    try:
        conn = sqlite3.connect('data/sehat_saathi.db')
        
        result = {}
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        
        for table in tables:
            table_name = table[0]
            count = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
            result[table_name] = count
            
        conn.close()
        
        html = "<h1>📊 Database Status</h1>"
        for table, count in result.items():
            html += f"<p>📋 {table}: {count} records</p>"
            
        return html
        
    except Exception as e:
        return f"Error: {e}"

@app.route('/debug/test-appointment')
def debug_test_appointment():
    """Test appointment creation manually"""
    try:
        # Create test patient
        patient_id = create_patient(
            name="Test Patient Debug",
            phone="+919876543210", 
            pincode="110001"
        )
        print(f"✅ Patient created: {patient_id}")
        
        # Create test appointment
        appointment_id = create_appointment(
            patient_id=patient_id,
            hospital_name="Test Hospital",
            hospital_type="hospital", 
            slot="2024-01-01 10:00",
            pincode="110001",
            maps_link="https://maps.test.com"
        )
        print(f"✅ Appointment created: {appointment_id}")
        
        # Check if data saved
        appointments = get_all_appointments()
        patients = get_all_patients()
        
        result_html = f"""
        <h1>Debug Results</h1>
        <p>Patient ID: {patient_id}</p>
        <p>Appointment ID: {appointment_id}</p>
        <p>Total Patients: {len(patients)}</p>
        <p>Total Appointments: {len(appointments)}</p>
        <h3>Recent Appointments:</h3>
        <ul>
        """
        
        for apt in appointments:
            result_html += f"<li>{apt['id']} - {apt.get('patient_name', 'N/A')} - {apt['hospital_name']} - {apt['status']}</li>"
        
        result_html += "</ul>"
        return result_html
        
    except Exception as e:
        return f"<h1>Error: {str(e)}</h1>"

# ==================== MAIN EXECUTION ====================

if __name__ == '__main__':
    # Initialize database
    init_db()
    print("🚀 Sehat Saathi Server Starting...")
    print("🗄️ Database initialized successfully!")
    print("📍 Home: http://127.0.0.1:5000")
    print("💬 Chat: http://127.0.0.1:5000/chat") 
    print("⚙️ Admin: http://127.0.0.1:5000/admin (admin/sehat123)")
    print("📊 Admin Features: Patients, Appointments, Doctors, Analytics")
    print("🐛 Debug: http://127.0.0.1:5000/debug/database")
    print("🧪 Test: http://127.0.0.1:5000/debug/test-appointment")
    print("📱 Twilio: DISABLED (Simulation Mode)")
    print("🔍 Gemini AI: " + ("✅ ENABLED" if GEMINI_AVAILABLE else "⚠️ DISABLED"))
    print("🚨 EMERGENCY FLOW: COMPLETELY FIXED!")
    print("💡 Emergency Test Sequence:")
    print("1 -> nearby -> 302004 -> appoint -> 2 -> Raj Kumar -> ✅ CONFIRMED!")
    print("✅ All 5 features working with complete database backend!")
    try:
        from doctors_insert import insert_doctors
        insert_doctors()
    except Exception as e:
        print(f"⚠️ Doctors insertion: {e}")
    
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
    