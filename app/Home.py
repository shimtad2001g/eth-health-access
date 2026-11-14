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
from branca.element import MacroElement
from jinja2 import Template

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="EthioHealth Emergency Command Center", 
    page_icon="assets/logo.png", 
    layout="wide"
)

# ==========================================
# 1. MAP LEGEND MACRO ELEMENT
# ==========================================
class MapLegend(MacroElement):
    def __init__(self):
        super().__init__()
        self._name = "MapLegend"
        self._template = Template(u"""
            {% macro script(this, kwargs) %}
                var legend = L.control({position: 'bottomleft'});
                legend.onAdd = function (map) {
                    var div = L.DomUtil.create('div', 'info legend');
                    div.innerHTML = `
                        <h4 style="margin-top: 0; margin-bottom: 5px; font-family: sans-serif;">Map Legend</h4>
                        <div style="font-size: 12px; line-height: 1.8; font-family: sans-serif; color: #333;">
                            <span style="display:inline-block; width: 15px; text-align: center; color: blue;"><i class="fa fa-user"></i></span> Clinic<br>
                            <span style="display:inline-block; width: 15px; text-align: center; color: green;"><i class="fa fa-plus"></i></span> Hospital (Beds Available)<br>
                            <span style="display:inline-block; width: 15px; text-align: center; color: red;"><i class="fa fa-plus"></i></span> Hospital (Full)<br>
                            <span style="display:inline-block; width: 15px; text-align: center; color: orange;"><i class="fa fa-ambulance"></i></span> Ambulance (Idle)<br>
                            <span style="display:inline-block; width: 15px; text-align: center; color: red;"><i class="fa fa-ambulance"></i></span> Ambulance (Dispatched)<br>
                            <span style="display:inline-block; width: 15px; text-align: center;"><span style="display:block; width: 12px; height: 4px; background: red; margin: 6px auto;"></span></span> Active Route
                        </div>
                    `;
                    div.style.backgroundColor = 'white';
                    div.style.padding = '10px 15px';
                    div.style.borderRadius = '8px';
                    div.style.boxShadow = '0 4px 15px rgba(0,0,0,0.2)';
                    div.style.zIndex = '9999';
                    div.style.border = '1px solid #ddd';
                    return div;
                };
                legend.addTo({{this._parent.get_name()}});
            {% endmacro %}
            """)

# ==========================================
# 2. INTERNATIONALIZATION (i18n) DICTIONARY
# ==========================================
LANGUAGES = [
    "English", "አማርኛ (Amharic)", "Afaan Oromoo (Oromo)", "ትግርኛ (Tigrinya)", 
    "Somali", "Sidaamu Afoo (Sidama)", "Wolayttattuwa (Wolaytta)", 
    "Gurage", "Qafar Af (Afar)", "Gamo", "Hadiyyisa (Hadiyya)",
    "Kambaatissa (Kembata)", "Gedeoffa (Gedeo)", "ስልጥኛ (Silt'e)", "Kafinoonoo (Kafa)"
]

TRANSLATIONS = {
    "English": {
        "lang_select": "🌐 Select Language", "disp_tab": "📡 Dispatch Simulator",
        "cap_tab": "🏥 Hospital Capacity", "triage_tab": "🧠 AI Triage", "help_tab": "❓ Help & Guide",
        "caller_info": "📞 Caller Info", "caller_name": "Caller Name:", "caller_phone": "Caller Phone:",
        "incident_loc": "📍 Incident Location", "select_clinic": "Select Patient Location:",
        "dispatch_btn": "🚨 Dispatch Nearest Ambulance", "fleet_status": "🚑 Fleet Status",
        "welcome": "Welcome", "logout": "Logout", "demo_btn": "🚀 Start 48-Hour Free Demo",
        "reg_title": "Register for 1-Month Trial", "login": "Login", "help_title": "❓ System User Guide & Help"
    },
    "አማርኛ (Amharic)": {
        "lang_select": "🌐 ቋንቋ ይምረጡ", "disp_tab": "📡 የመላኪያ ማስመሰያ", "cap_tab": "🏥 የሆስፒታል አቅም",
        "triage_tab": "🧠 የAI ህክምና መለያ", "help_tab": "❓ እርዳታ እና መመሪያ", "caller_info": "📞 የደዋይ መረጃ",
        "caller_name": "የደዋይ ስም:", "caller_phone": "የደዋይ ስልክ ቁጥር:", "incident_loc": "📍 የችግሩ ቦታ",
        "select_clinic": "የታካሚውን ቦታ ይምረጡ:", "dispatch_btn": "🚨 በቅርብ የሚገኝ አምቡላንስ ላክ",
        "fleet_status": "🚑 የአምቡላንስ ሁኔታ", "welcome": "እንኳን ደህና መጡ", "logout": "ውጣ",
        "demo_btn": "🚀 የ48 ሰዓት ነፃ ማሳያ ጀምር", "reg_title": "ለ1 ወር ሙከራ ይመዝገቡ",
        "login": "ግባ", "help_title": "❓ የስርዓቱ የተጠቃሚ መመሪያ እና እርዳታ"
    },
    "Afaan Oromoo (Oromo)": {
        "lang_select": "🌐 Afaan Filadhu", "disp_tab": "📡 Simulaatorii Ergaa", "cap_tab": "🏥 Dandeettii Hospitaalaa",
        "triage_tab": "🧠 AI Triage", "help_tab": "❓ Gargaarsa", "caller_info": "📞 Odeeffannoo Bilbilaa",
        "caller_name": "Maqaa Bilbilaa:", "caller_phone": "Lakkoofsa Bilbilaa:", "incident_loc": "📍 Bakka Rakkoo",
        "select_clinic": "Bakka Dhukkubsataa Filadhu:", "dispatch_btn": "🚨 Ambulaansii Dhihoo Ergi",
        "fleet_status": "🚑 Haala Ambulaansii", "welcome": "Baga Nagaan Dhuftan", "logout": "Ba'i",
        "demo_btn": "🚀 Demo Sa'aatii 48 Horaa Jalqabi", "reg_title": "Ji'a 1f Qormaataaf Galmaa'i",
        "login": "Seeni", "help_title": "❓ Qajeelfama Fayyadamaa"
    },
    "ትግርኛ (Tigrinya)": {
        "lang_select": "🌐 ቋንቋ ምረጽ", "disp_tab": "📡 መላኪያ ሲሙሌተር", "cap_tab": "🏥 ክእለት ሆስፒታል",
        "triage_tab": "🧠 AI Triage", "help_tab": "❓ ሓገዝ", "caller_info": "📞 ሓበሬታ ደዋይ",
        "caller_name": "ስም ደዋይ:", "caller_phone": "ቁጽሪ ስልኪ:", "incident_loc": "📍 ቦታ ጸገም",
        "select_clinic": "ቦታ ሕሙም ምረጽ:", "dispatch_btn": "🚨 ቀረባ ኣምቡላንስ ስደድ",
        "fleet_status": "🚑 ኩነታት ኣምቡላንስ", "welcome": "እንቋዕ ብደሓን መጻእኩም", "logout": "ውጻእ",
        "demo_btn": "🚀 ናይ 48 ሰዓት ነጻ ሙከራ ጀምር", "reg_title": "ን1 ወርሒ ፈተነ ተመዝገብ",
        "login": "እቶ", "help_title": "❓ መምርሒ ተጠቃሚ"
    },
    "Somali": {
        "lang_select": "🌐 Dooro Luuqadda", "disp_tab": "📡 Simulator-ka Dirista", "cap_tab": "🏥 Awoodda Isbitaalka",
        "triage_tab": "🧠 AI Triage", "help_tab": "❓ Caawinaad", "caller_info": "📞 Macluumaadka Wacayaasha",
        "caller_name": "Magaca Wacayaasha:", "caller_phone": "Lambarka Taleefanka:", "incident_loc": "📍 Goobta Dhacdada",
        "select_clinic": "Dooro Goobta Bukaanka:", "dispatch_btn": "🚨 Dir Ambulance-ka ugu dhow",
        "fleet_status": "🚑 Xaaladda Ambulance-ka", "welcome": "Ku soo dhawow", "logout": "Ka bax",
        "demo_btn": "🚀 Bilow 48-saacadood Demo Bilaash ah", "reg_title": "Isku qor 1 Bilood Tijaabo",
        "login": "Gal", "help_title": "❓ Hagaha Isticmaalaha"
    }
}

for lang in LANGUAGES:
    if lang not in TRANSLATIONS:
        TRANSLATIONS[lang] = TRANSLATIONS["English"]

# ==========================================
# 3. DATABASE & CONFIG SETUP
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

# Try/Except block prevents crash if table already exists
try:
    Base.metadata.create_all(engine)
except Exception as e:
    pass # Table already exists, safely ignore

Session = sessionmaker(bind=engine)
session = Session()

# ==========================================
# 4. SIDEBAR & LANGUAGE SELECTION
# ==========================================
if os.path.exists("assets/logo.png"):
    st.logo("assets/logo.png", size="large")
    st.sidebar.image("assets/logo.png", width="stretch")
else:
    st.sidebar.warning("⚠️ Logo missing! Check assets/logo.png")

selected_lang = st.sidebar.selectbox("🌐 Language / ቋንቋ", LANGUAGES, index=0)

def t(key):
    return TRANSLATIONS[selected_lang].get(key, key)

with st.sidebar.expander("ℹ️ About the Developer"):
    st.markdown("""
    **Developed by:** Shimeles Tadesse Zelelew
    **Status:** Prototype / Not Patented yet.
    *Disclaimer: This is a pilot system. Do not use for actual emergency dispatch until fully certified by the Ministry of Health.*
    """)
    st.markdown("[📧 Email Me](mailto:shimeles.tadesse@example.com?subject=EthioHealth%20System%20Inquiry&body=Hello%20Shimeles,%0A%0AI%20am%20interested%20in%20the%20EthioHealth%20System.)")

st.sidebar.markdown("---")

# ==========================================
# 5. AUTHENTICATION, DEMO, & DEVELOPER BACKDOOR
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

if "dev_access" in query_params and query_params["dev_access"] == "shimeles_admin_2026":
    is_dev = True
    demo_mode = False

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

if not demo_mode and not is_dev:
    authenticator.login(location='main', fields={'Form name': t("login")})
    
    if st.session_state.get('authentication_status') is False:
        st.error('Username/password is incorrect')
    elif st.session_state.get('authentication_status') is None:
        st.info('Please login or start a demo below.')
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("### Try the System")
            if st.button(t("demo_btn"), use_container_width=True):
                now_str = datetime.now().isoformat()
                st.query_params["demo"] = "true"
                st.query_params["start"] = now_str
                st.rerun()
                
        with col2:
            st.markdown(f"### {t('reg_title')}")
            with st.form("register_form"):
                new_name = st.text_input("Full Name")
                new_email = st.text_input("Official Email")
                new_pass = st.text_input("Password", type="password")
                agree = st.checkbox("I agree to use this system responsibly and ethically.")
                
                if st.form_submit_button("Register Account"):
                    if new_name and new_email and new_pass and agree:
                        username_key = new_name.lower().replace(" ", "")
                        if username_key in config['credentials']['usernames']:
                            st.error("Username/Name already exists.")
                        else:
                            hashed_pw = stauth.Hasher.hash(new_pass)
                            trial_end = (datetime.now() + timedelta(days=30)).isoformat()
                            config['credentials']['usernames'][username_key] = {
                                'email': new_email, 'name': new_name, 'password': hashed_pw, 'trial_end': trial_end
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
    st.warning(f"⚠️ **DEMO MODE ACTIVE** - Time remaining: {str(time_remaining).split('.')[0]}.")
    name = "Demo User"
else:
    name = st.session_state.get('name')
    authenticator.logout(t("logout"), 'sidebar')

if not demo_mode and not is_dev and not st.session_state.get('authentication_status') == False:
    user_key = st.session_state.get('username')
    user_data = config['credentials']['usernames'].get(user_key)
    if user_data and 'trial_end' in user_data:
        trial_end = datetime.fromisoformat(user_data['trial_end'])
        if datetime.now() > trial_end:
            st.error("Your 1-month trial has expired.")
            st.stop()

# ==========================================
# 6. APP LOGIC (OSRM, MAP, etc.)
# ==========================================
OSRM_URL = "http://router.project-osrm.org/route/v1/driving/"

def get_route(orig_lon, orig_lat, dest_lon, dest_lat):
    url = f"{OSRM_URL}{orig_lon},{orig_lat};{dest_lon},{dest_lat}?overview=full&geometries=geojson"
    try:
        response = requests.get(url, timeout=5)
        data = response.json()
        if data.get('code') == 'Ok': return data['routes'][0]
    except: pass
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
st.write(f"{t('welcome')}, **{name}**!")

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    t("disp_tab"), t("cap_tab"), t("triage_tab"), t("help_tab"), "🌐 Health Ecosystem"
])

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
                                    caller_name=caller_name, caller_phone=caller_phone, 
                                    clinic=selected_clinic, ambulance=nearest_amb['id'], hospital=assigned_hosp
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
        # Create the base map (defaults to OpenStreetMap)
        m = folium.Map(location=[9.0116, 38.7878], zoom_start=12)
        
        # Add Google Satellite Imagery Layer (Highly reliable)
        folium.TileLayer(
            tiles='https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}',
            attr='Google',
            name='Satellite Imagery',
            overlay=False,
            control=True
        ).add_to(m)
        
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
        
        # Add LayerControl to toggle between Street Map and Satellite
        folium.LayerControl().add_to(m)
        
        # Add the Dynamic Legend to the Map
        m.add_child(MapLegend())
        
        st_folium(m, width="stretch", height=600)

with tab2:
    st.header(t("cap_tab"))
    
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
    st.subheader("📋 Recent Dispatch Logs")
    
    if demo_mode:
        st.info("Dispatch logs are disabled in Demo Mode.")
    else:
        logs = session.query(Dispatch).order_by(Dispatch.time.desc()).limit(10).all()
        if logs:
            log_data = [{
                "Time": l.time.strftime("%Y-%m-%d %H:%M"), "Caller": l.caller_name, 
                "Phone": l.caller_phone, "Ambulance": l.ambulance, "Hospital": l.hospital
            } for l in logs]
            st.dataframe(pd.DataFrame(log_data), use_container_width=True)
        else:
            st.info("No dispatches logged yet.")

with tab3:
    st.header(t("triage_tab"))
    openai_api_key = st.sidebar.text_input("OpenAI API Key", type="password")
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
                        model="gpt-3.5-turbo", messages=[{"role": "user", "content": prompt}], max_tokens=50
                    )
                    ai_result = response.choices[0].message.content
                    if "CRITICAL" in ai_result: st.error(f"**AI Triage:** {ai_result}")
                    elif "URGENT" in ai_result: st.warning(f"**AI Triage:** {ai_result}")
                    else: st.success(f"**AI Triage:** {ai_result}")
                except Exception as e:
                    st.error(f"AI Error: {e}")

with tab4:
    st.header(t("help_title"))
    st.markdown("Welcome to the **EthioHealth Emergency Command Center**. This guide explains every visible part of the platform to ensure you can save lives efficiently.")
    
    st.markdown("---")
    st.subheader("1. Sidebar Navigation")
    st.markdown("*   **Language Selector:** Switch between 15 Ethiopian languages.\n*   **About the Developer:** Read about the system's creator.\n*   **OpenAI API Key:** Required for AI Triage.\n*   **Logout:** Securely logs you out.")
    
    st.markdown("---")
    st.subheader("2. 📡 Dispatch Simulator Tab")
    st.markdown("This is the core of the Command Center. Enter caller info, select the incident location, and click Dispatch. The system calculates the Haversine distance to find the closest ambulance and uses the OSRM routing engine to find the fastest path.")
    
    st.markdown("---")
    st.subheader("3. 🏥 Hospital Capacity Tab")
    st.markdown("Manage real-time bed availability. If beds drop to 0, the marker turns Red, and the algorithm skips it.")
    
    st.markdown("---")
    st.subheader("4. 🧠 AI Triage Tab")
    st.markdown("**What is AI Triage?** Triage is determining the priority of patients' treatments based on severity. AI Triage uses Natural Language Processing to automatically categorize the emergency.\n\n**Benefits:**\n*   Faster Response Times\n*   Reduces Human Error\n*   Standardized Prioritization\n*   Optimized Resource Allocation")
    
    st.info("💡 **Pro Tip:** If the system feels slow, it may be due to external APIs (OSRM or OpenAI).")

# --- TAB 5: HEALTH ECOSYSTEM ---
with tab5:
    st.header("🌐 National Health Ecosystem")
    st.markdown("Access Ethiopia's key open-source and cloud-based health platforms directly from this portal.")

    st.markdown("---")

    col1, col2 = st.columns(2)

    with col1:
        with st.container(border=True):
            st.subheader("📊 DHIS2 (National HMIS)")
            st.caption("Ethiopia's national Health Management Information System for aggregate data, analytics, and reporting.")
            st.markdown("[🔗 Open DHIS2 Portal](https://dhis236.moh.gov.et)")

        with st.container(border=True):
            st.subheader("📋 OpenMRS (Electronic Medical Records)")
            st.caption("Open-source EMR for patient-level data. Share detailed patient histories between facilities.")
            st.markdown("[🔗 Open OpenMRS](https://openmrs.org/) | [🚀 Try Demo](https://demo.openmrs.org/openmrs)")

        with st.container(border=True):
            st.subheader("🏥 Bahmni (Hospital Information System)")
            st.caption("Comprehensive EMR & hospital management (billing, inventory) built on OpenMRS.")
            st.markdown("[🔗 Open Bahmni](https://www.bahmni.org/)")

    with col2:
        with st.container(border=True):
            st.subheader("🚑 Resgrid (Dispatch & First Responder)")
            st.caption("Open-source Computer-Aided Dispatch (CAD) system for coordinating ambulance fleets and field personnel.")
            st.markdown("[🔗 Open Resgrid](https://resgrid.com/)")

        with st.container(border=True):
            st.subheader("🔗 OpenHIM (Interoperability Layer)")
            st.caption("Middleware that allows different health systems to communicate and share data securely.")
            st.markdown("[🔗 Open OpenHIM](http://openhim.org/)")

        with st.container(border=True):
            st.subheader("🧪 OpenELIS (Laboratory Information)")
            st.caption("Open-source lab management system for tracking test results and diagnostics.")
            st.markdown("[🔗 Open OpenELIS](https://openelis.org/)")
