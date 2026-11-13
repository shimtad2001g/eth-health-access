import streamlit as st
import os
import folium
from streamlit_folium import st_folium

# --- LOGO & PAGE CONFIGURATION ---
st.set_page_config(
    page_title="Ethio Health Access",
    page_icon="assets/logo.png",
    layout="wide",
)

if os.path.exists("assets/logo.png"):
    st.logo(
        "assets/logo.png",
        size="large",
        link="https://ethio-health-access.streamlit.app/",
        icon_image="assets/logo.png",
    )
else:
    st.sidebar.warning("⚠️ Logo asset missing — check assets/logo.png")

# --- APP UI ---
st.title("🚑 EthioHealth Access - Addis Ababa Pilot")
st.write("Select a clinic to find the fastest route to a nearby hospital.")

col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("Dispatch Simulator")
    
    clinic = st.selectbox(
        "Select Patient Location (Clinic):",
        ["22 Mazoria Internal Medicine Speciality Clinic", "Other Clinic 1", "Other Clinic 2"]
    )
    
    st.info("Coordinates: 9.0116, 38.7878")
    
    if st.button("🚨 Find Nearest Hospital", type="primary"):
        st.success("Simulating dispatch to nearest hospital...")

with col2:
    # Create a base map for Addis Ababa
    m = folium.Map(location=[9.0116, 38.7878], zoom_start=12)
    
    # Add a marker for the clinic
    folium.Marker(
        [9.0116, 38.7878], 
        popup=clinic, 
        icon=folium.Icon(color="green", icon="plus")
    ).add_to(m)
    
    # Display the map in Streamlit
    st_folium(m, use_container_width=True, height=500)