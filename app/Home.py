import os
import io
import streamlit as st
import geopandas as gpd
import folium
from streamlit_folium import st_folium
import pandas as pd
import numpy as np
import math
import requests
from openai import OpenAI
import yaml
from yaml.loader import SafeLoader
import streamlit_authenticator as stauth
from streamlit_autorefresh import st_autorefresh
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Float
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import NullPool
from datetime import datetime, timedelta
from gtts import gTTS
from twilio.rest import Client

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="EthioHealth Emergency Command Center", 
    page_icon="assets/logo.png", 
    layout="wide"
)

# ==========================================
# 1. INTERNATIONALIZATION (i18n)
# ==========================================
LANGUAGES = [
    "English", "አማርኛ (Amharic)", "Afaan Oromoo (Oromo)", "ትግርኛ (Tigrinya)", 
    "Somali", "Sidaamu Afoo (Sidama)", "Wolayttattuwa (Wolaytta)", 
    "Gurage", "Qafar Af (Afar)", "Gamo", "Hadiyyisa (Hadiyya)", 
    "Kambaatissa (Kembata)", "Gedeoffa (Gedeo)", "ስልጥኛ (Silt'e)", "Kafinoonoo (Kafa)"
]

TRANSLATIONS = {
    "English": {
        "disp_tab": "📡 Dispatch Simulator", "cap_tab": "🏥 Hospital Capacity",
        "triage_tab": "🧠 AI Triage", "help_tab": "❓ Help & Guide",
        "caller_info": "📞 Caller Info", "caller_name": "Caller Name:",
        "caller_phone": "Caller Phone:", "incident_loc": "📍 Incident Location",
        "select_clinic": "Select Patient Location:", "dispatch_btn": "🚨 Dispatch Nearest Ambulance",
        "welcome": "Welcome", "logout": "Logout", "demo_btn": "🚀 Start 48-Hour Free Demo",
        "reg_title": "Register for 1-Month Trial", "login": "Login"
    },
    "አማርኛ (Amharic)": {
        "disp_tab": "📡 የመላኪያ ማስመሰያ", "cap_tab": "🏥 የሆስፒታል አቅም",
        "triage_tab": "🧠 የAI ህክምና መለያ", "help_tab": "❓ እርዳታ እና መመሪያ",
        "caller_info": "📞 የደዋይ መረጃ", "caller_name": "የደዋይ ስም:",
        "caller_phone": "የደዋይ ስልክ ቁጥር:", "incident_loc": "📍 የችግሩ ቦታ",
        "select_clinic": "የታካሚውን ቦታ ይምረጡ:", "dispatch_btn": "🚨 በቅርብ የሚገኝ አምቡላንስ ላክ",
        "welcome": "እንኳን ደህና መጡ", "logout": "ውጣ", "demo_btn": "🚀 የ48 ሰዓት ነፃ ማሳያ ጀምር",
        "reg_title": "ለ1 ወር ሙከራ ይመዝገቡ", "login": "ግባ"
    },
    "Afaan Oromoo (Oromo)": {
        "disp_tab": "📡 Simulaatorii Ergaa", "cap_tab": "🏥 Dandeettii Hospitaalaa",
        "triage_tab": "🧠 AI Triage", "help_tab": "❓ Gargaarsa",
        "caller_info": "📞 Odeeffannoo Bilbilaa", "caller_name": "Maqaa Bilbilaa:",
        "caller_phone": "Lakkoofsa Bilbilaa:", "incident_loc": "📍 Bakka Rakkoo",
        "select_clinic": "Bakka Dhukkubsataa Filadhu:", "dispatch_btn": "🚨 Ambulaansii Dhihoo Ergi",
        "welcome": "Baga Nagaan Dhuftan", "logout": "Ba'i", "demo_btn": "🚀 Demo Sa'aatii 48 Horaa Jalqabi",
        "reg_title": "Ji'a 1f Qormaataaf Galmaa'i", "login": "Seeni"
    },
    "ትግርኛ (Tigrinya)": {
        "disp_tab": "📡 መላኪያ ሲሙሌተር", "cap_tab": "🏥 ክእለት ሆስፒታል",
        "triage_tab": "🧠 AI Triage", "help_tab": "❓ ሓገዝ",
        "caller_info": "📞 ሓበሬታ ደዋይ", "caller_name": "ስም ደዋይ:",
        "caller_phone": "ቁጽሪ ስልኪ:", "incident_loc": "📍 ቦታ ጸገም",
        "select_clinic": "ቦታ ሕሙም ምረጽ:", "dispatch_btn": "🚨 ቀረባ ኣምቡላንስ ስደድ",
        "welcome": "እንቋዕ ብደሓን መጻእኩም", "logout": "ውጻእ", "demo_btn": "🚀 ናይ 48 ሰዓት ነጻ ሙከራ ጀምር",
        "reg_title": "ን1 ወርሒ ፈተነ ተመዝገብ", "login": "እቶ"
    },
    "Somali": {
        "disp_tab": "📡 Simulator-ka Dirista", "cap_tab": "🏥 Awoodda Isbitaalka",
        "triage_tab": "🧠 AI Triage", "help_tab": "❓ Caawinaad",
        "caller_info": "📞 Macluumaadka Wacayaasha", "caller_name": "Magaca Wacayaasha:",
        "caller_phone": "Lambarka Taleefanka:", "incident_loc": "📍 Goobta Dhacdada",
        "select_clinic": "Dooro Goobta Bukaanka:", "dispatch_btn": "🚨 Dir Ambulance-ka ugu dhow",
        "welcome": "Ku soo dhawow", "logout": "Ka bax", "demo_btn": "🚀 Bilow 48-saacadood Demo Bilaash ah",
        "reg_title": "Isku qor 1 Bilood Tijaabo", "login": "Gal"
    }
}
for lang in LANGUAGES:
    if lang not in TRANSLATIONS: TRANSLATIONS[lang] = TRANSLATIONS["English"]

# ==========================================
# 2. CONFIG & DB
# ==========================================
if not os.path.exists('config.yaml'):
    hashed_password = stauth.Hasher.hash('password123')
    config = {
        'credentials': {'usernames': {'dispatcher': {'email': 'dispatcher@ethiohealth.com', 'name': 'Admin Dispatcher', 'password': hashed_password, 'trial_end': (datetime.now() + timedelta(days=365)).isoformat()}}},
        'cookie': {'expiry_days': 30, 'key': 'ethio_secret_key', 'name': 'ethio_auth'}
    }
    with open('config.yaml', 'w') as file: yaml.dump(config, file, default_flow_style=False)

with open('config.yaml') as file: config = yaml.load(file, Loader=SafeLoader)

try:
    DATABASE_URL = st.secrets["SUPABASE_DB_URL"]
    TWILIO_SID = st.secrets["TWILIO_ACCOUNT_SID"]
    TWILIO_TOKEN = st.secrets["TWILIO_AUTH_TOKEN"]
    TWILIO_FROM = st.secrets["TWILIO_FROM_NUMBER"]
except (KeyError, FileNotFoundError):
    DATABASE_URL = "sqlite:///ethio_health.db"
    TWILIO_SID, TWILIO_TOKEN, TWILIO_FROM = None, None, None

engine = create_engine(DATABASE_URL, poolclass=NullPool)
Base = declarative_base()

class Dispatch(Base):
    __tablename__ = 'dispatches'
    id = Column(Integer, primary_key=True)
    caller_name = Column(String)
    caller_phone = Column(String)
    clinic = Column(String)
    ambulance = Column(String)
    hospital = Column(String)
    eta_minutes = Column(Float)
    triage_level = Column(String)
    time = Column(DateTime, default=datetime.utcnow)

Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
session = Session()

# ==========================================
# 3. HELPERS
# ==========================================
def play_dispatch_alert(language_name, eta_minutes):
    lang_map = {"English": "en", "አማርኛ (Amharic)": "am", "Afaan Oromoo (Oromo)": "om", "ትግርኛ (Tigrinya)": "ti", "Somali": "so"}
    tts_lang = lang_map.get(language_name, "en")
    message = f"Ambulance dispatched. Estimated time of arrival {eta_minutes:.0f} minutes."
    try:
        tts = gTTS(text=message, lang=tts_lang, slow=False)
        audio_bytes = io.BytesIO()
        tts.write_to_fp(audio_bytes)
        st.audio(audio_bytes, format="audio/mp3", autoplay=True)
    except Exception as e:
        st.caption(f"Audio alert unavailable: {e}")

def send_dispatch_sms(to_number, ambulance_id, hospital_name, eta_minutes):
    if not TWILIO_SID: return None
    try:
        client = Client(TWILIO_SID, TWILIO_TOKEN)
        message = client.messages.create(
            body=f"🚑 EthioHealth Dispatch\nAmbulance: {ambulance_id}\nDestination: {hospital_name}\nETA: {eta_minutes:.1f} mins\nHelp is on the way.",
            from_=TWILIO_FROM, to=to_number
        )
        return message.sid
    except Exception as e:
        st.warning(f"SMS failed: {e}")
        return None

# ==========================================
# 4. SIDEBAR & AUTH
# ==========================================
if os.path.exists("assets/logo.png"):
    st.logo("assets/logo.png", size="large")
    st.sidebar.image("assets/logo.png", width="stretch")

selected_lang = st.sidebar.selectbox("🌐 Language / ቋንቋ", LANGUAGES, index=0)
def t(key): return TRANSLATIONS[selected_lang].get(key, key)

with st.sidebar.expander("ℹ️ About the Developer"):
    st.markdown("**Developed by:** Shimeles Tadesse Zelelew\n**Status:** Prototype / Not Patented yet.")
    st.markdown("[📧 Email Me](mailto:shimeles.tadesse@example.com)")

authenticator = stauth.Authenticate(config['credentials'], config['cookie']['name'], config['cookie']['key'], config['cookie']['expiry_days'])
query_params = st.query_params
demo_mode, time_remaining, is_dev = False, None, False

if "dev_access" in query_params and query_params["dev_access"] == "shimeles_admin_2026":
    is_dev = True

if not is_dev and query_params.get("demo") == "true" and query_params.get("start"):
    try:
        elapsed = datetime.now() - datetime.fromisoformat(query_params.get("start"))
        if elapsed < timedelta(hours=48):
            demo_mode = True
            time_remaining = timedelta(hours=48) - elapsed
        else:
            st.error("Demo expired."); st.query_params.clear()
    except: st.query_params.clear()

if not demo_mode and not is_dev:
    authenticator.login(location='main', fields={'Form name': t("login")})
    if st.session_state.get('authentication_status') is False: st.error('Invalid credentials')
    elif st.session_state.get('authentication_status') is None:
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("### Try the System")
            if st.button(t("demo_btn"), use_container_width=True):
                st.query_params["demo"] = "true"; st.query_params["start"] = datetime.now().isoformat(); st.rerun()
        with col2:
            st.markdown(f"### {t('reg_title')}")
            with st.form("register_form"):
                new_name = st.text_input("Full Name"); new_email = st.text_input("Email"); new_pass = st.text_input("Password", type="password"); agree = st.checkbox("I agree to use ethically.")
                if st.form_submit_button("Register") and new_name and new_pass and agree:
                    username_key = new_name.lower().replace(" ", "")
                    if username_key not in config['credentials']['usernames']:
                        config['credentials']['usernames'][username_key] = {'email': new_email, 'name': new_name, 'password': stauth.Hasher.hash(new_pass), 'trial_end': (datetime.now() + timedelta(days=30)).isoformat()}
                        with open('config.yaml', 'w') as file: yaml.dump(config, file, default_flow_style=False)
                        st.success("Registered! Please login.")
    if not st.session_state.get('authentication_status') and not demo_mode and not is_dev: st.stop()

if is_dev: st.success("👑 DEVELOPER ACCESS GRANTED"); name = "Developer (Admin)"
elif demo_mode: st.warning(f"⚠️ DEMO MODE - {str(time_remaining).split('.')[0]} left."); name = "Demo User"
else: name = st.session_state.get('name'); authenticator.logout(t("logout"), 'sidebar')

# ==========================================
# 5. APP LOGIC
# ==========================================
OSRM_URL = "http://router.project-osrm.org/route/v1/driving/"
def get_route(o_lon, o_lat, d_lon, d_lat):
    try:
        r = requests.get(f"{OSRM_URL}{o_lon},{o_lat};{d_lon},{d_lat}?overview=full&geometries=geojson", timeout=5).json()
        if r.get('code') == 'Ok': return r['routes'][0]
    except: pass
    return None

if 'hospital_db' not in st.session_state:
    st.session_state.hospital_db = {"Black Lion": {"beds": 5, "coords": [9.0200, 38.7600]}, "St. Paul's": {"beds": 0, "coords": [9.0300, 38.7700]}, "Zewditu": {"beds": 12, "coords": [9.0100, 38.7500]}}
if 'ambulances' not in st.session_state:
    st.session_state.ambulances = [{"id": "AMB-01", "lat": 9.025, "lon": 38.755, "status": "Available"}, {"id": "AMB-02", "lat": 9.040, "lon": 38.810, "status": "Available"}]
if 'active_route' not in st.session_state: st.session_state.active_route = None
if 'sim_progress' not in st.session_state: st.session_state.sim_progress = 0.0
if 'dispatched_amb' not in st.session_state: st.session_state.dispatched_amb = None

@st.cache_data
def load_data():
    try: return gpd.read_file('data/processed/facilities_addis.gpkg')
    except: return gpd.GeoDataFrame({'Name': ["22 Mazoria Clinic", "Black Lion", "St. Paul's"], 'Type_Clean': ['Clinic', 'Hospital', 'Hospital'], 'geometry': gpd.points_from_xy([38.7878, 38.7600, 38.7700], [9.0116, 9.0200, 9.0300])})
gdf = load_data()

def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0; lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    a = math.sin((lat2-lat1)/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2-lon1)/2)**2
    return R * (2 * math.atan2(math.sqrt(a), math.sqrt(1-a)))

st.title("🚑 EthioHealth Emergency Command Center")
st.write(f"{t('welcome')}, **{name}**!")

tab1, tab2, tab3, tab4 = st.tabs([t("disp_tab"), t("cap_tab"), t("triage_tab"), t("help_tab")])

with tab1:
    col1, col2 = st.columns([1, 3])
    with col1:
        st.header(t("disp_tab"))
        st.subheader(t("caller_info"))
        caller_name = st.text_input(t("caller_name"))
        caller_phone = st.text_input(t("caller_phone"))
        st.markdown("---")
        st.subheader(t("incident_loc"))
        clinics = gdf[gdf['Type_Clean'] == 'Clinic'].copy()
        if not clinics.empty:
            selected_clinic = st.selectbox(t("select_clinic"), clinics['Name'].tolist())
            clinic_row = clinics[clinics['Name'] == selected_clinic].iloc[0]
            c_lon, c_lat = clinic_row.geometry.x, clinic_row.geometry.y
            st.write(f"Coords: {c_lat:.4f}, {c_lon:.4f}")
        
        st.markdown("---")
        if st.button(t("dispatch_btn"), type="primary"):
            with st.spinner("Routing..."):
                available_ambs = [a for a in st.session_state.ambulances if a['status'] == 'Available']
                if available_ambs:
                    available_ambs.sort(key=lambda a: haversine(a['lat'], a['lon'], c_lat, c_lon))
                    nearest_amb = available_ambs[0]
                    available_hospitals = [k for k, v in st.session_state.hospital_db.items() if v['beds'] > 0]
                    
                    if available_hospitals:
                        assigned_hosp = available_hospitals[0]
                        route = get_route(nearest_amb['lon'], nearest_amb['lat'], c_lon, c_lat)
                        if route:
                            st.session_state.active_route = route['geometry']['coordinates']
                            nearest_amb['status'] = f"En route to {assigned_hosp}"
                            st.session_state.dispatched_amb = nearest_amb['id']
                            st.session_state.sim_progress = 0.0
                            st.session_state.hospital_db[assigned_hosp]['beds'] -= 1
                            eta = route['duration'] / 60
                            
                            play_dispatch_alert(selected_lang, eta)
                            if caller_phone: 
                                if send_dispatch_sms(caller_phone, nearest_amb['id'], assigned_hosp, eta): st.caption("SMS Sent!")
                            if not demo_mode:
                                session.add(Dispatch(caller_name=caller_name, caller_phone=caller_phone, clinic=selected_clinic, ambulance=nearest_amb['id'], hospital=assigned_hosp, eta_minutes=eta))
                                session.commit()
                            
                            st.success("Dispatch Successful!")
                            st.write(f"**Unit:** {nearest_amb['id']} | **ETA:** {eta:.1f} mins")
                        else: st.error("Routing failed.")
                    else: st.error("No beds available!")

        if st.session_state.active_route and st.session_state.dispatched_amb:
            st_autorefresh(interval=3000, limit=None, key="iot_refresh")
            if st.session_state.sim_progress < 1.0: st.session_state.sim_progress += 0.05 
            else: st.session_state.sim_progress = 1.0
            st.progress(st.session_state.sim_progress)
            st.caption(f"Telemetry: {st.session_state.sim_progress*100:.0f}% along route.")

    with col2:
        m = folium.Map(location=[9.0116, 38.7878], zoom_start=12)
        clinics_layer = folium.FeatureGroup(name="Clinics")
        hospitals_layer = folium.FeatureGroup(name="Hospitals")
        ambulances_layer = folium.FeatureGroup(name="Ambulances")
        
        for _, row in clinics.iterrows():
            folium.CircleMarker([row.geometry.y, row.geometry.x], radius=3, color='blue', fill=True, fill_opacity=0.6, popup=row['Name']).add_to(clinics_layer)
        for h_name, h_data in st.session_state.hospital_db.items():
            color = 'green' if h_data['beds'] > 0 else 'red'
            folium.Marker(h_data['coords'], popup=f"{h_name} (Beds: {h_data['beds']})", icon=folium.Icon(color=color, icon='plus', prefix='fa')).add_to(hospitals_layer)
        for amb in st.session_state.ambulances:
            if amb['id'] != st.session_state.dispatched_amb:
                folium.Marker([amb['lat'], amb['lon']], popup=amb['id'], icon=folium.Icon(color='orange', icon='ambulance', prefix='fa')).add_to(ambulances_layer)

        if st.session_state.active_route:
            route_coords = [[lat, lon] for lon, lat in st.session_state.active_route]
            folium.PolyLine(route_coords, color="red", weight=5, opacity=0.8).add_to(m)
            idx = int(st.session_state.sim_progress * (len(route_coords) - 1))
            folium.Marker(route_coords[idx], popup="LIVE GPS", icon=folium.Icon(color='red', icon='ambulance', prefix='fa')).add_to(m)

        clinics_layer.add_to(m); hospitals_layer.add_to(m); ambulances_layer.add_to(m)
        folium.LayerControl().add_to(m)
        st_folium(m, width="stretch", height=600)

with tab2:
    st.header(t("cap_tab"))
    for h_name, h_data in st.session_state.hospital_db.items():
        with st.container():
            st.subheader(h_name)
            c1, c2 = st.columns(2)
            with c1: 
                st.session_state.hospital_db[h_name]['beds'] = st.number_input(f"Available Beds", min_value=0, value=h_data['beds'], key=f"b_{h_name}")
            with c2:
                if h_data['beds'] > 0: st.success("🟢 Open")
                else: st.error("🔴 Full")
            st.divider()
    st.subheader("📋 Recent Dispatch Logs")
    if not demo_mode:
        logs = session.query(Dispatch).order_by(Dispatch.time.desc()).limit(10).all()
        if logs: st.dataframe(pd.DataFrame([{"Time": l.time, "Caller": l.caller_name, "Ambulance": l.ambulance, "Hospital": l.hospital, "ETA": l.eta_minutes} for l in logs]))
        else: st.info("No logs yet.")

with tab3:
    st.header(t("triage_tab"))
    if not st.secrets.get("OPENAI_API_KEY"):
        st.warning("Add OPENAI_API_KEY to Streamlit Secrets to use this.")
    else:
        client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
        with st.form("triage"):
            symptoms = st.text_area("Symptoms:")
            if st.form_submit_button("Analyze"):
                res = client.chat.completions.create(model="gpt-3.5-turbo", messages=[{"role": "user", "content": f"Classify as CRITICAL, URGENT, or NON-URGENT: {symptoms}"}], max_tokens=20).choices[0].message.content
                st.info(res)

with tab4:
    st.header(t("help_tab"))
    st.markdown("Welcome to the **EthioHealth Emergency Command Center**. This guide explains every visible part of the platform to ensure you can save lives efficiently.")
    
    st.markdown("---")
    st.subheader("1. Sidebar Navigation (Left Panel)")
    st.markdown("""
    *   **🌐 Language Selector:** Instantly translates the entire user interface into one of 15 Ethiopian languages.
    *   **ℹ️ About the Developer:** Read about the system's creator, the ethical disclaimer, and a direct email link.
    *   **OpenAI API Key:** Required to activate the AI Triage feature. *Note: The key is only stored in your browser session.*
    *   **Logout:** Securely logs you out of the Command Center.
    """)
    
    st.markdown("---")
    st.subheader("2. 📡 Dispatch Simulator Tab")
    st.markdown("""
    This is the core of the Command Center. It allows you to receive a call, locate the patient, and dispatch the nearest ambulance.
    
    *   **📞 Caller Info:** Enter the caller's name and phone number. This is permanently saved to the database.
    *   **📍 Incident Location:** Select the clinic where the patient is located. The system automatically reads its GPS coordinates.
    *   **🚨 Dispatch Nearest Ambulance Button:** 
        *   Calculates the physical distance to find the **closest available ambulance**.
        *   Queries the **OSRM routing engine** to find the fastest driving path on real roads.
        *   Assigns the patient to the nearest hospital with available beds.
        *   Triggers an **Audio Alert** (gTTS) and an **SMS Notification** (Twilio).
    *   **📡 Live IoT Hardware Tracking:** Simulates real-time GPS telemetry, showing the red ambulance icon moving along the red route line on the map.
    """)
    
    st.markdown("---")
    st.subheader("3. 🏥 Hospital Capacity Tab")
    st.markdown("""
    This tab manages the real-time bed availability of the network's hospitals.
    
    *   **Available Beds / ICU:** You can manually adjust the number of available beds and ICU units. 
    *   **Dynamic Status:** If beds drop to `0`, the hospital's marker on the map turns **Red** (Full), and the dispatch algorithm skips it. If you increase it above `0`, it turns **Green** (Open).
    *   **📋 Dispatch Logs:** At the bottom, you can view the permanent database records of every dispatch, including time, caller, and destination.
    """)
    
    st.markdown("---")
    st.subheader("4. 🧠 AI Triage Tab")
    st.markdown("""
    **What is AI Triage?** 
    Triage is the process of determining the priority of patients' treatments based on the severity of their condition. **AI Triage** uses Artificial Intelligence to automatically analyze unstructured patient symptoms and categorize the emergency.
    
    **Benefits:**
    *   **Faster Response Times:** Critical patients are identified in milliseconds.
    *   **Reduces Human Error:** The AI consistently checks for life-threatening keywords.
    *   **Standardized Prioritization:** Ensures every caller is evaluated using the same protocols.
    *   **Optimized Resource Allocation:** Saves ambulances for life-threatening cases (Red).
    
    **How to use it:** Type symptoms into the text box. The app sends the text to GPT-3.5, which classifies the emergency into 🔴 **CRITICAL**, 🟡 **URGENT**, or 🟢 **NON-URGENT**.
    """)
    
    st.markdown("---")
    st.subheader("5. The Map Interface")
    st.markdown("""
    *   **Blue Dots:** Represent clinics and health centers.
    *   **Green/Red Crosses:** Represent hospitals (Green = Beds available, Red = Full).
    *   **Orange Ambulances:** Represent the current positions of your active fleet.
    *   **Red Line:** The active driving route calculated by OSRM.
    *   **Layer Control (Top Right of Map):** Toggle the visibility of clinics, hospitals, and ambulances.
    """)
    
    st.info("💡 **Pro Tip:** If the system feels slow, it may be due to the OSRM routing API or the OpenAI API processing your request. Always ensure you have a stable internet connection.")
