$fullCode = @'
import os
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
from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime, timedelta

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="EthioHealth Emergency Command Center", 
    page_icon="assets/logo.png", 
    layout="wide"
)

# ==========================================
# 1. DATABASE & CONFIG SETUP
# ==========================================
if not os.path.exists('config.yaml'):
    hashed_password = stauth.Hasher.hash('password123')
    config = {
        'credentials': {
            'usernames': {
                'dispatcher': {
                    'email': 'dispatcher@ethiohealth.com',
                    'name': 'Admin Dispatcher',
                    'password': hashed_password,
                    'trial_end': (datetime.now() + timedelta(days=365)).isoformat()
                }
            }
        },
        'cookie': {'expiry_days': 30, 'key': 'ethio_secret_key', 'name': 'ethio_auth'}
    }
    with open('config.yaml', 'w') as file:
        yaml.dump(config, file, default_flow_style=False)

with open('config.yaml') as file:
    config = yaml.load(file, Loader=SafeLoader)

DATABASE_URL = "sqlite:///ethio_health.db"
engine = create_engine(DATABASE_URL, echo=False)
Base = declarative_base()

class Dispatch(Base):
    __tablename__ = 'dispatches'
    id = Column(Integer, primary_key=True)
    caller_name = Column(String)
    caller_phone = Column(String)
    clinic = Column(String)
    ambulance = Column(String)
    hospital = Column(String)
    time = Column(DateTime, default=datetime.utcnow)

Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
session = Session()

# ==========================================
# 2. DEVELOPER INFO & SIDEBAR
# ==========================================
if os.path.exists("assets/logo.png"):
    st.logo("assets/logo.png", size="large")
    st.sidebar.image("assets/logo.png", width="stretch")
else:
    st.sidebar.warning("⚠️ Logo missing! Check assets/logo.png")

with st.sidebar.expander("ℹ️ About the Developer"):
    st.markdown("""
    **Developed by:** Shimeles Tadesse Zelelew
    **Status:** Prototype / Not Patented yet.
    This system is designed to save lives by optimizing emergency dispatch. 
    
    *Disclaimer: This is a pilot system. Do not use for actual emergency dispatch until fully certified by the Ministry of Health.*
    """)
    st.markdown("[📧 Email Me](mailto:shimeles.tadesse@example.com?subject=EthioHealth%20System%20Inquiry&body=Hello%20Shimeles,%0A%0AI%20am%20interested%20in%20the%20EthioHealth%20System.)")

st.sidebar.markdown("---")

# ==========================================
# 3. AUTHENTICATION, DEMO, & DEVELOPER BACKDOOR
# ==========================================
authenticator = stauth.Authenticate(
    config['credentials'],
    config['cookie']['name'],
    config['cookie']['key'],
    config['cookie']['expiry_days']
)

query_params = st.query_params
demo_mode = False
time_remaining = None
is_dev = False

# 👑 SECRET DEVELOPER BACKDOOR 👑
if "dev_access" in query_params and query_params["dev_access"] == "shimeles_admin_2026":
    is_dev = True
    demo_mode = False

# 48-Hour Demo Logic
if not is_dev and query_params.get("demo") == "true" and query_params.get("start"):
    try:
        start_time = datetime.fromisoformat(query_params.get("start"))
        elapsed = datetime.now() - start_time
        if elapsed < timedelta(hours=48):
            demo_mode = True
            time_remaining = timedelta(hours=48) - elapsed
        else:
            st.error("Your 48-hour demo has expired. Please register below to continue.")
            st.query_params.clear()
    except:
        st.query_params.clear()

# Standard Login
if not demo_mode and not is_dev:
    authenticator.login()
    
    if st.session_state.get('authentication_status') is False:
        st.error('Username/password is incorrect')
    elif st.session_state.get('authentication_status') is None:
        st.info('Please login or start a demo below.')
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("### Try the System")
            if st.button("🚀 Start 48-Hour Free Demo", use_container_width=True):
                now_str = datetime.now().isoformat()
                st.query_params["demo"] = "true"
                st.query_params["start"] = now_str
                st.rerun()
                
        with col2:
            st.markdown("### Register for 1-Month Trial")
            with st.form("register_form"):
                new_name = st.text_input("Full Name")
                new_email = st.text_input("Official Email")
                new_org = st.text_input("Organization (e.g., MoH, NGO)")
                new_pass = st.text_input("Password", type="password")
                agree = st.checkbox("I agree to use this system responsibly and ethically. I understand this is a pilot system.")
                
                if st.form_submit_button("Register Account"):
                    if new_name and new_email and new_pass and agree:
                        username_key = new_name.lower().replace(" ", "")
                        if username_key in config['credentials']['usernames']:
                            st.error("Username/Name already exists.")
                        else:
                            hashed_pw = stauth.Hasher.hash(new_pass)
                            trial_end = (datetime.now() + timedelta(days=30)).isoformat()
                            
                            config['credentials']['usernames'][username_key] = {
                                'email': new_email,
                                'name': new_name,
                                'password': hashed_pw,
                                'trial_end': trial_end
                            }
                            
                            with open('config.yaml', 'w') as file:
                                yaml.dump(config, file, default_flow_style=False)
                            
                            st.success(f"Registration successful! Log in using your username: {username_key}")
                    else:
                        st.warning("Please fill all fields and agree to the ethical terms.")
        
    if not st.session_state.get('authentication_status') and not demo_mode and not is_dev:
        st.stop()

# --- LOGGED IN / DEMO / DEV UI ---
if is_dev:
    st.success("👑 **DEVELOPER ACCESS GRANTED** - Unlimited Full System Control.")
    name = "Developer (Admin)"
elif demo_mode:
    st.warning(f"⚠️ **DEMO MODE ACTIVE** - Time remaining: {str(time_remaining).split('.')[0]}. Data will not be saved. [Register here](#) to save data.")
    name = "Demo User"
else:
    name = st.session_state.get('name')
    authenticator.logout('Logout', 'sidebar')

# Check Trial Expiration
if not demo_mode and not is_dev and not st.session_state.get('authentication_status') == False:
    user_key = st.session_state.get('username')
    user_data = config['credentials']['usernames'].get(user_key)
    if user_data and 'trial_end' in user_data:
        trial_end = datetime.fromisoformat(user_data['trial_end'])
        if datetime.now() > trial_end:
            st.error("Your 1-month trial has expired. Please email the developer for full access.")
            st.stop()

# ==========================================
# 4. APP LOGIC (OSRM, MAP, etc.)
# ==========================================
OSRM_URL = "http://router.project-osrm.org/route/v1/driving/"

def get_route(orig_lon, orig_lat, dest_lon, dest_lat):
    url = f"{OSRM_URL}{orig_lon},{orig_lat};{dest_lon},{dest_lat}?overview=full&geometries=geojson"
    try:
        response = requests.get(url, timeout=5)
        data = response.json()
        if data.get('code') == 'Ok':
            return data['routes'][0]
    except Exception:
        pass
    return None

if 'hospital_db' not in st.session_state:
    st.session_state.hospital_db = {
        "Black Lion Hospital": {"beds": 5, "icu": 2, "coords": [9.0200, 38.7600]},
        "St. Paul's Hospital": {"beds": 0, "icu": 0, "coords": [9.0300, 38.7700]},
        "Zewditu Memorial": {"beds": 12, "icu": 1, "coords": [9.0100, 38.7500]}
    }

if 'ambulances' not in st.session_state:
    st.session_state.ambulances = [
        {"id": "AMB-01", "lat": 9.025, "lon": 38.755, "status": "Available"},
        {"id": "AMB-02", "lat": 9.040, "lon": 38.810, "status": "Available"},
        {"id": "AMB-03", "lat": 8.970, "lon": 38.790, "status": "Available"}
    ]

if 'active_route' not in st.session_state: st.session_state.active_route = None
if 'sim_progress' not in st.session_state: st.session_state.sim_progress = 0.0
if 'dispatched_amb' not in st.session_state: st.session_state.dispatched_amb = None

@st.cache_data
def load_data():
    try:
        return gpd.read_file('data/processed/facilities_addis.gpkg')
    except:
        return gpd.GeoDataFrame({
            'Name': ["22 Mazoria Clinic", "Black Lion Hospital", "St. Paul's Hospital"],
            'Type_Clean': ['Clinic', 'Hospital', 'Hospital'],
            'geometry': gpd.points_from_xy([38.7878, 38.7600, 38.7700], [9.0116, 9.0200, 9.0300])
        })

gdf = load_data()

def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0 
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    return R * (2 * math.atan2(math.sqrt(a), math.sqrt(1-a)))

st.title("🚑 EthioHealth Emergency Command Center")
st.write(f"Welcome, **{name}**!")

tab1, tab2, tab3, tab4 = st.tabs(["📡 Dispatch Simulator", "🏥 Hospital Capacity", "🧠 AI Triage", "❓ Help & Guide"])

with tab1:
    col1, col2 = st.columns([1, 3])
    
    with col1:
        st.header("Dispatch Console")
        st.subheader("📞 Caller Info")
        caller_name = st.text_input("Caller Name:")
        caller_phone = st.text_input("Caller Phone:")
        
        st.markdown("---")
        st.subheader("📍 Incident Location")
        clinics = gdf[gdf['Type_Clean'] == 'Clinic'].copy()
        if not clinics.empty:
            selected_clinic = st.selectbox("Select Patient Location:", clinics['Name'].tolist())
            clinic_row = clinics[clinics['Name'] == selected_clinic].iloc[0]
            c_lon, c_lat = clinic_row.geometry.x, clinic_row.geometry.y
            st.write(f"Coords: {c_lat:.4f}, {c_lon:.4f}")
        
        st.markdown("---")
        if st.button("🚨 Dispatch Nearest Ambulance", type="primary"):
            with st.spinner("Routing via OSRM..."):
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
                            
                            if not demo_mode:
                                new_dispatch = Dispatch(
                                    caller_name=caller_name, 
                                    caller_phone=caller_phone, 
                                    clinic=selected_clinic, 
                                    ambulance=nearest_amb['id'], 
                                    hospital=assigned_hosp
                                )
                                session.add(new_dispatch)
                                session.commit()
                            
                            st.success("Dispatch Successful!")
                            st.write(f"**Unit:** {nearest_amb['id']} | **ETA:** {route['duration']/60:.1f} mins")
                        else:
                            st.error("Routing failed.")
                    else:
                        st.error("No hospital beds available!")

        if st.session_state.active_route and st.session_state.dispatched_amb:
            st.markdown("---")
            st.subheader("📡 Live IoT Hardware Tracking")
            st_autorefresh(interval=3000, limit=None, key="iot_refresh")
            
            if st.session_state.sim_progress < 1.0:
                st.session_state.sim_progress += 0.05 
            else:
                st.session_state.sim_progress = 1.0
                
            st.progress(st.session_state.sim_progress)
            st.caption(f"Telemetry received. Ambulance is {st.session_state.sim_progress*100:.0f}% along the route.")

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
            if amb['id'] == st.session_state.dispatched_amb and st.session_state.active_route:
                continue 
            folium.Marker([amb['lat'], amb['lon']], popup=amb['id'], icon=folium.Icon(color='orange', icon='ambulance', prefix='fa')).add_to(ambulances_layer)

        if st.session_state.active_route:
            route_coords = [[lat, lon] for lon, lat in st.session_state.active_route]
            folium.PolyLine(route_coords, color="red", weight=5, opacity=0.8).add_to(m)
            
            total_points = len(route_coords)
            current_index = int(st.session_state.sim_progress * (total_points - 1))
            current_pos = route_coords[current_index]
            
            folium.Marker(current_pos, popup=f"LIVE GPS: {st.session_state.dispatched_amb}", icon=folium.Icon(color='red', icon='ambulance', prefix='fa')).add_to(m)

        clinics_layer.add_to(m)
        hospitals_layer.add_to(m)
        ambulances_layer.add_to(m)
        folium.LayerControl().add_to(m)
        st_folium(m, width="stretch", height=600)

with tab2:
    st.header("🏥 Real-Time Hospital Capacity Board")
    
    for idx, (hosp_name, data) in enumerate(st.session_state.hospital_db.items()):
        with st.container():
            st.subheader(hosp_name)
            col_a, col_b, col_c = st.columns(3)
            with col_a:
                new_beds = st.number_input(f"Available Beds", min_value=0, value=data['beds'], key=f"bed_{hosp_name}")
            with col_b:
                new_icu = st.number_input(f"Available ICU", min_value=0, value=data['icu'], key=f"icu_{hosp_name}")
            with col_c:
                if new_beds > 0: st.success("🟢 Open")
                else: st.error("🔴 Full")
            
            st.session_state.hospital_db[hosp_name]['beds'] = new_beds
            st.session_state.hospital_db[hosp_name]['icu'] = new_icu
            st.divider()
            
    st.markdown("---")
    st.subheader("📋 Recent Dispatch Logs (From Database)")
    
    if demo_mode:
        st.info("Dispatch logs are disabled in Demo Mode. Register to save your data.")
    else:
        logs = session.query(Dispatch).order_by(Dispatch.time.desc()).limit(10).all()
        if logs:
            log_data = [{
                "Time": l.time.strftime("%Y-%m-%d %H:%M"), 
                "Caller": l.caller_name, 
                "Phone": l.caller_phone, 
                "Ambulance": l.ambulance, 
                "Hospital": l.hospital
            } for l in logs]
            st.dataframe(pd.DataFrame(log_data), use_container_width=True)
        else:
            st.info("No dispatches logged yet.")

with tab3:
    st.header("🧠 AI-Powered Triage & Decision Support")
    openai_api_key = st.sidebar.text_input("OpenAI API Key (for AI Triage)", type="password")
    if not openai_api_key:
        st.warning("⚠️ Please enter your OpenAI API Key in the sidebar.")
    else:
        client = OpenAI(api_key=openai_api_key)
    
    with st.form("triage_form"):
        symptoms = st.text_area("Describe the primary complaint:")
        age = st.number_input("Patient Age:", min_value=0, max_value=120, value=30)
        submitted = st.form_submit_button("Analyze with AI")
        
        if submitted and symptoms and openai_api_key:
            with st.spinner("AI analyzing symptoms..."):
                prompt = f"You are an expert medical dispatcher. Classify the emergency as CRITICAL (Red), URGENT (Yellow), or NON-URGENT (Green). Provide a 1-sentence reason. Patient Age: {age}. Symptoms: {symptoms}. Output format: [Triage Level] - [Reason]"
                try:
                    response = client.chat.completions.create(
                        model="gpt-3.5-turbo",
                        messages=[{"role": "user", "content": prompt}],
                        max_tokens=50
                    )
                    ai_result = response.choices[0].message.content
                    if "CRITICAL" in ai_result: st.error(f"**AI Triage:** {ai_result}")
                    elif "URGENT" in ai_result: st.warning(f"**AI Triage:** {ai_result}")
                    else: st.success(f"**AI Triage:** {ai_result}")
                except Exception as e:
                    st.error(f"AI Error: {e}")

# --- TAB 4: HELP & DOCUMENTATION ---
with tab4:
    st.header("❓ System User Guide & Help")
    st.markdown("Welcome to the **EthioHealth Emergency Command Center**. This guide explains every visible part of the platform to ensure you can save lives efficiently.")
    
    st.markdown("---")
    
    st.subheader("1. Sidebar Navigation (Left Panel)")
    st.markdown("""
    *   **About the Developer:** Click this to read about the system's creator, the ethical disclaimer, and a direct email link to contact the developer.
    *   **OpenAI API Key:** If you want to use the AI Triage feature, you must paste your OpenAI API Key here. *Note: The key is only stored in your browser session and is never saved to our database.*
    *   **Logout:** Securely logs you out of the Command Center.
    """)
    
    st.markdown("---")
    
    st.subheader("2. 📡 Dispatch Simulator Tab")
    st.markdown("""
    This is the core of the Command Center. It allows you to receive a call, locate the patient, and dispatch the nearest ambulance.
    
    *   **📞 Caller Info:** Enter the caller's name and phone number. This is permanently saved to the database for reporting.
    *   **📍 Incident Location:** Select the clinic or health center where the patient is located. The system automatically reads the GPS coordinates of this facility.
    *   **🚨 Dispatch Nearest Ambulance Button:** 
        *   When clicked, the system calculates the physical distance (using Haversine formula) to find the **closest available ambulance**.
        *   It then queries the **OSRM routing engine** to find the fastest driving path on real roads.
        *   It assigns the patient to the nearest hospital that has available beds.
    *   **📡 Live IoT Hardware Tracking:** Once dispatched, this slider simulates real-time GPS telemetry from the ambulance. You can watch the red ambulance icon move along the red route line on the map.
    """)
    
    st.markdown("---")
    
    st.subheader("3. 🏥 Hospital Capacity Tab")
    st.markdown("""
    This tab manages the real-time bed availability of the network's hospitals.
    
    *   **Available Beds / ICU:** You can manually adjust the number of available beds and ICU units. 
    *   **Dynamic Status:** If you set beds to `0`, the hospital's marker on the map turns **Red** (Full), and the dispatch algorithm will skip it. If you set it above `0`, it turns **Green** (Open).
    *   **📋 Dispatch Logs:** At the bottom of this tab, you can view the permanent SQL database records of every dispatch, including the time, caller, and destination.
    """)
    
    st.markdown("---")
    
    st.subheader("4. 🧠 AI Triage Tab")
    st.markdown("""
    This tab uses Generative AI (OpenAI) to assist dispatchers in prioritizing emergencies.
    
    *   **How to use:** Type the patient's symptoms into the text box (e.g., *"Chest pain radiating to the left arm"*).
    *   **The AI Engine:** The app sends the symptoms to GPT-3.5, which analyzes the text and classifies the emergency into three colors:
        *   🔴 **CRITICAL (Red):** Immediate dispatch required (life-threatening).
        *   🟡 **URGENT (Yellow):** Needs medical attention within 30 minutes.
        *   🟢 **NON-URGENT (Green):** Advise the patient to visit a clinic on their own.
    """)
    
    st.markdown("---")
    
    st.subheader("5. The Map Interface")
    st.markdown("""
    *   **Blue Dots:** Represent clinics and health centers.
    *   **Green/Red Crosses:** Represent hospitals (Green = Beds available, Red = Full).
    *   **Orange Ambulances:** Represent the current positions of your active fleet.
    *   **Red Line:** The active driving route calculated by OSRM.
    *   **Layer Control (Top Right of Map):** You can toggle the visibility of clinics, hospitals, and ambulances on and off to reduce map clutter.
    """)
    
    st.info("💡 **Pro Tip:** If the system feels slow, it may be due to the OSRM routing API or the OpenAI API processing your request. Always ensure you have a stable internet connection.")
'@

Set-Content -Path app\Home.py -Value $fullCode -Encoding UTF8
Write-Host "Code successfully written to app\Home.py!" -ForegroundColor Green
notepad app\Home.py