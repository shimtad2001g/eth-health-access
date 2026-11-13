import os
import streamlit as st
import geopandas as gpd
import folium
from streamlit_folium import st_folium
import pandas as pd
import numpy as np
import math
import random

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="EthioHealth Emergency Command Center", 
    page_icon="assets/logo.png", 
    layout="wide"
)

# --- LOGO INTEGRATION ---
if os.path.exists("assets/logo.png"):
    st.logo("assets/logo.png", size="large")
    st.sidebar.image("assets/logo.png", use_container_width=True)
else:
    st.sidebar.warning("⚠️ Logo missing! Check assets/logo.png")

# --- MOCK DATABASES (In production, connect to PostgreSQL/Firebase) ---
# 1. Hospital Capacity Database
if 'hospital_db' not in st.session_state:
    st.session_state.hospital_db = {
        "Black Lion Hospital": {"beds": 5, "icu": 2, "status": "Available"},
        "St. Paul's Hospital": {"beds": 0, "icu": 0, "status": "Full"},
        "Zewditu Memorial": {"beds": 12, "icu": 1, "status": "Available"},
        "Yekatit 12": {"beds": 3, "icu": 0, "status": "Available"}
    }

# 2. Fleet Management Database (Simulated GPS coordinates)
if 'ambulances' not in st.session_state:
    st.session_state.ambulances = [
        {"id": "AMB-01", "lat": 9.020, "lon": 38.750, "status": "Available"},
        {"id": "AMB-02", "lat": 9.035, "lon": 38.800, "status": "Available"},
        {"id": "AMB-03", "lat": 8.980, "lon": 38.780, "status": "Available"}
    ]

# --- LOAD MAP DATA ---
@st.cache_data
def load_data():
    try:
        return gpd.read_file('data/processed/facilities_addis.gpkg')
    except:
        # Fallback mock data if file is missing
        return gpd.GeoDataFrame({
            'Name': ["22 Mazoria Clinic", "Black Lion Hospital", "St. Paul's Hospital"],
            'Type_Clean': ['Clinic', 'Hospital', 'Hospital'],
            'geometry': gpd.points_from_xy([38.7878, 38.7600, 38.7700], [9.0116, 9.0200, 9.0300])
        })

gdf = load_data()

# ==========================================
# UI LAYOUT: TABS FOR THE COMMAND CENTER
# ==========================================
st.title("🚑 EthioHealth Emergency Command Center")
st.markdown("**Ministry of Health - Addis Ababa Pilot**")

tab1, tab2, tab3 = st.tabs(["📡 Dispatch Simulator", "🏥 Hospital Capacity", "🧠 AI Triage"])

# --- TAB 1: DISPATCH SIMULATOR & FLEET ---
with tab1:
    col1, col2 = st.columns([1, 3])
    
    with col1:
        st.header("Dispatch Simulator")
        
        # AI Triage Integration: Pull severity from Tab 3
        current_triage = st.session_state.get('triage_level', 'Unknown')
        if current_triage != 'Unknown':
            st.info(f"Current Patient Triage: **{current_triage}**")
        
        clinics = gdf[gdf['Type_Clean'] == 'Clinic'].copy()
        if not clinics.empty:
            selected_clinic = st.selectbox("Select Patient Location (Clinic):", clinics['Name'].tolist())
            clinic_row = clinics[clinics['Name'] == selected_clinic].iloc[0]
            c_lon, c_lat = clinic_row.geometry.x, clinic_row.geometry.y
            st.write(f"Coordinates: {c_lat:.4f}, {c_lon:.4f}")
        else:
            st.warning("No clinics found in database.")

        st.markdown("---")
        st.subheader("🚑 Fleet Status")
        for amb in st.session_state.ambulances:
            if amb['status'] == 'Available':
                st.success(f"{amb['id']}: Available (Lat: {amb['lat']:.3f}, Lon: {amb['lon']:.3f})")
            else:
                st.warning(f"{amb['id']}: {amb['status']}")
                
        if st.button("🚨 Dispatch Ambulance", type="primary"):
            with st.spinner("Routing to nearest available hospital..."):
                # Simulation: Dispatch logic
                available_hospitals = [k for k, v in st.session_state.hospital_db.items() if v['beds'] > 0]
                if available_hospitals:
                    assigned_hosp = random.choice(available_hospitals)
                    assigned_amb = "AMB-01"
                    st.session_state.ambulances[0]['status'] = f"En route to {assigned_hosp}"
                    st.session_state.hospital_db[assigned_hosp]['beds'] -= 1 # Deduct bed
                    
                    st.success(f"Dispatch Successful!")
                    st.write(f"**Ambulance:** {assigned_amb}")
                    st.write(f"**Destination:** {assigned_hosp} (Bed Allocated)")
                    st.write(f"**ETA:** 8.5 minutes")
                else:
                    st.error("CRITICAL: No hospital beds available in the network!")

    with col2:
        # Map Layout
        m = folium.Map(location=[9.0116, 38.7878], zoom_start=12)
        
        # Plot Clinics
        for _, row in clinics.iterrows():
            folium.CircleMarker([row.geometry.y, row.geometry.x], radius=4, color='blue', fill=True, popup=row['Name']).add_to(m)
            
        # Plot Hospitals with Capacity Colors
        for _, row in gdf[gdf['Type_Clean'].isin(['Hospital', 'Health Center'])].iterrows():
            # Check our mock database for capacity
            cap = st.session_state.hospital_db.get(row['Name'], {"beds": 10})['beds']
            color = 'green' if cap > 0 else 'red'
            folium.Marker([row.geometry.y, row.geometry.x], popup=f"{row['Name']} (Beds: {cap})", icon=folium.Icon(color=color, icon='plus', prefix='fa')).add_to(m)
            
        # Plot Live Ambulances
        for amb in st.session_state.ambulances:
            folium.Marker([amb['lat'], amb['lon']], popup=amb['id'], icon=folium.Icon(color='orange', icon='ambulance', prefix='fa')).add_to(m)

        st_folium(m, use_container_width=True, height=600)

# --- TAB 2: HOSPITAL CAPACITY BOARD ---
with tab2:
    st.header("🏥 Real-Time Hospital Capacity Board")
    st.write("Update the available resources for the network.")
    
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
            
            # Update the mock database
            st.session_state.hospital_db[hosp_name]['beds'] = new_beds
            st.session_state.hospital_db[hosp_name]['icu'] = new_icu
            st.divider()

# --- TAB 3: AI CLINICAL TRIAGE ---
with tab3:
    st.header("🧠 AI-Powered Triage & Decision Support")
    st.write("Enter patient symptoms to determine emergency priority.")
    
    with st.form("triage_form"):
        symptoms = st.text_area("Describe the primary complaint (e.g., 'Chest pain and shortness of breath'):")
        age = st.number_input("Patient Age:", min_value=0, max_value=120, value=30)
        submitted = st.form_submit_button("Calculate Triage Level")
        
        if submitted and symptoms:
            # Simple Rule-Based AI Logic (In production, use an LLM like OpenAI)
            symptoms_lower = symptoms.lower()
            
            if any(word in symptoms_lower for word in ["chest pain", "breathing", "unconscious", "bleeding heavily", "stroke"]):
                triage_level = "🔴 CRITICAL (Red) - Immediate Dispatch"
                color = "error"
            elif any(word in symptoms_lower for word in ["fracture", "broken", "high fever", "severe pain"]):
                triage_level = "🟡 URGENT (Yellow) - Dispatch within 30 mins"
                color = "warning"
            else:
                triage_level = "🟢 NON-URGENT (Green) - Advise Clinic Visit"
                color = "success"
                
            st.session_state['triage_level'] = triage_level
            
            if color == "error":
                st.error(f"**Triage Result:** {triage_level}")
            elif color == "warning":
                st.warning(f"**Triage Result:** {triage_level}")
            else:
                st.success(f"**Triage Result:** {triage_level}")