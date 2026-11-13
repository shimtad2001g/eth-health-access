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

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="EthioHealth Emergency Command Center", 
    page_icon="assets/logo.png", 
    layout="wide"
)

# --- LOGO INTEGRATION ---
if os.path.exists("assets/logo.png"):
    st.logo("assets/logo.png", size="large")
    st.sidebar.image("assets/logo.png", width="stretch")
else:
    st.sidebar.warning("⚠️ Logo missing! Check assets/logo.png")

# --- SIDEBAR SETTINGS ---
st.sidebar.markdown("---")
st.sidebar.subheader("⚙️ System Settings")
openai_api_key = st.sidebar.text_input("OpenAI API Key (for AI Triage)", type="password")
if openai_api_key:
    client = OpenAI(api_key=openai_api_key)

# --- REAL-WORLD API: OSRM ROUTING ---
OSRM_URL = "http://router.project-osrm.org/route/v1/driving/"

def get_route(orig_lon, orig_lat, dest_lon, dest_lat):
    url = f"{OSRM_URL}{orig_lon},{orig_lat};{dest_lon},{dest_lat}?overview=full&geometries=geojson"
    try:
        response = requests.get(url, timeout=5)
        data = response.json()
        if data.get('code') == 'Ok':
            return data['routes'][0]
    except Exception as e:
        st.error(f"Routing error: {e}")
    return None

# --- MOCK DATABASES (In production, connect to PostgreSQL/Firebase) ---
if 'hospital_db' not in st.session_state:
    st.session_state.hospital_db = {
        "Black Lion Hospital": {"beds": 5, "icu": 2, "coords": [9.0200, 38.7600]},
        "St. Paul's Hospital": {"beds": 0, "icu": 0, "coords": [9.0300, 38.7700]},
        "Zewditu Memorial": {"beds": 12, "icu": 1, "coords": [9.0100, 38.7500]}
    }

# Ambulances now have real coordinates to calculate distance
if 'ambulances' not in st.session_state:
    st.session_state.ambulances = [
        {"id": "AMB-01", "lat": 9.025, "lon": 38.755, "status": "Available"},
        {"id": "AMB-02", "lat": 9.040, "lon": 38.810, "status": "Available"},
        {"id": "AMB-03", "lat": 8.970, "lon": 38.790, "status": "Available"}
    ]

if 'active_route' not in st.session_state:
    st.session_state.active_route = None

# --- LOAD MAP DATA ---
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

# Haversine distance formula to find nearest ambulance
def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0 
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

# ==========================================
# UI LAYOUT
# ==========================================
st.title("🚑 EthioHealth Emergency Command Center")

tab1, tab2, tab3 = st.tabs(["📡 Dispatch Simulator", "🏥 Hospital Capacity", "🧠 AI Triage"])

# --- TAB 1: DISPATCH SIMULATOR & FLEET ---
with tab1:
    col1, col2 = st.columns([1, 3])
    
    with col1:
        st.header("Dispatch Simulator")
        
        clinics = gdf[gdf['Type_Clean'] == 'Clinic'].copy()
        if not clinics.empty:
            selected_clinic = st.selectbox("Select Patient Location (Clinic):", clinics['Name'].tolist())
            clinic_row = clinics[clinics['Name'] == selected_clinic].iloc[0]
            c_lon, c_lat = clinic_row.geometry.x, clinic_row.geometry.y
            st.write(f"Target Coordinates: {c_lat:.4f}, {c_lon:.4f}")
        else:
            st.warning("No clinics found in database.")

        st.markdown("---")
        st.subheader("🚑 Fleet Status")
        for amb in st.session_state.ambulances:
            if amb['status'] == 'Available':
                st.success(f"{amb['id']}: Available")
            else:
                st.warning(f"{amb['id']}: {amb['status']}")
                
        if st.button("🚨 Dispatch Nearest Ambulance", type="primary"):
            with st.spinner("Calculating optimal route via OSRM..."):
                
                # 1. Find nearest available ambulance
                available_ambs = [a for a in st.session_state.ambulances if a['status'] == 'Available']
                if not available_ambs:
                    st.error("No ambulances available!")
                else:
                    # Sort by distance to clinic
                    available_ambs.sort(key=lambda a: haversine(a['lat'], a['lon'], c_lat, c_lon))
                    nearest_amb = available_ambs[0]
                    
                    # 2. Find nearest hospital WITH BEDS
                    available_hospitals = [k for k, v in st.session_state.hospital_db.items() if v['beds'] > 0]
                    if available_hospitals:
                        assigned_hosp = available_hospitals[0]
                        
                        # 3. Get Real Route from OSRM (Ambulance -> Clinic)
                        route = get_route(nearest_amb['lon'], nearest_amb['lat'], c_lon, c_lat)
                        
                        if route:
                            # Save route to session state to draw on map
                            st.session_state.active_route = route['geometry']['coordinates']
                            
                            # Update Statuses
                            nearest_amb['status'] = f"En route to {assigned_hosp}"
                            st.session_state.hospital_db[assigned_hosp]['beds'] -= 1
                            
                            st.success("Dispatch Successful!")
                            st.write(f"**Assigned Unit:** {nearest_amb['id']} (Nearest to scene)")
                            st.write(f"**Destination:** {assigned_hosp}")
                            st.write(f"**Real Driving Distance:** {route['distance']/1000:.2f} km")
                            st.write(f"**Estimated ETA:** {route['duration']/60:.1f} minutes")
                        else:
                            st.error("Routing engine failed to find a path.")
                    else:
                        st.error("CRITICAL: No hospital beds available in the network!")

    with col2:
        m = folium.Map(location=[9.0116, 38.7878], zoom_start=12)
        
        # Plot Clinics
        for _, row in clinics.iterrows():
            folium.Marker([row.geometry.y, row.geometry.x], popup=row['Name'], icon=folium.Icon(color='blue', icon='user', prefix='fa')).add_to(m)
            
        # Plot Hospitals
        for h_name, h_data in st.session_state.hospital_db.items():
            color = 'green' if h_data['beds'] > 0 else 'red'
            folium.Marker(h_data['coords'], popup=f"{h_name} (Beds: {h_data['beds']})", icon=folium.Icon(color=color, icon='plus', prefix='fa')).add_to(m)
            
        # Plot Live Ambulances
        for amb in st.session_state.ambulances:
            folium.Marker([amb['lat'], amb['lon']], popup=amb['id'], icon=folium.Icon(color='orange', icon='ambulance', prefix='fa')).add_to(m)

        # Draw Route if active
        if st.session_state.active_route:
            route_coords = [[lat, lon] for lon, lat in st.session_state.active_route]
            folium.PolyLine(route_coords, color="red", weight=5, opacity=0.8, tooltip="Active Route").add_to(m)

        st_folium(m, width="stretch", height=600)

# --- TAB 2: HOSPITAL CAPACITY BOARD ---
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
                st.write("Status:")
                if new_beds > 0:
                    st.success("🟢 Open")
                else:
                    st.error("🔴 Full")
            
            st.session_state.hospital_db[hosp_name]['beds'] = new_beds
            st.session_state.hospital_db[hosp_name]['icu'] = new_icu
            st.divider()

# --- TAB 3: AI CLINICAL TRIAGE (LLM INTEGRATION) ---
with tab3:
    st.header("🧠 AI-Powered Triage & Decision Support")
    st.write("Uses OpenAI to analyze unstructured patient symptoms.")
    
    if not openai_api_key:
        st.warning("⚠️ Please enter your OpenAI API Key in the sidebar to use the AI Triage.")
    
    with st.form("triage_form"):
        symptoms = st.text_area("Describe the primary complaint (e.g., 'My father is clutching his chest and sweating profusely'):")
        age = st.number_input("Patient Age:", min_value=0, max_value=120, value=30)
        submitted = st.form_submit_button("Analyze with AI")
        
        if submitted and symptoms and openai_api_key:
            with st.spinner("AI analyzing symptoms..."):
                prompt = f"""
                You are an expert medical dispatcher. Based on these symptoms, classify the emergency as CRITICAL (Red), URGENT (Yellow), or NON-URGENT (Green).
                Provide a 1-sentence reason.
                Patient Age: {age}
                Symptoms: {symptoms}
                Output format: [Triage Level] - [Reason]
                """
                try:
                    response = client.chat.completions.create(
                        model="gpt-3.5-turbo",
                        messages=[{"role": "user", "content": prompt}],
                        max_tokens=50
                    )
                    ai_result = response.choices[0].message.content
                    
                    if "CRITICAL" in ai_result:
                        st.error(f"**AI Triage:** {ai_result}")
                    elif "URGENT" in ai_result:
                        st.warning(f"**AI Triage:** {ai_result}")
                    else:
                        st.success(f"**AI Triage:** {ai_result}")
                        
                except Exception as e:
                    st.error(f"AI Error: {e}")