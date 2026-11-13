import os
import streamlit as st
import geopandas as gpd
import folium
from streamlit_folium import st_folium
import requests
import math

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="EthioHealth Access", 
    page_icon="assets/logo.png", 
    layout="wide"
)

# --- LOGO INTEGRATION ---
if os.path.exists("assets/logo.png"):
    st.logo("assets/logo.png", size="large")
    st.sidebar.image("assets/logo.png", use_container_width=True)
else:
    st.sidebar.warning("⚠️ Logo missing! Check assets/logo.png")

# USE PUBLIC OSRM FOR CLOUD DEPLOYMENT
OSRM_URL = "https://router.project-osrm.org"

@st.cache_data
def load_data():
    return gpd.read_file('data/processed/facilities_addis.gpkg')

def get_route(orig_lon, orig_lat, dest_lon, dest_lat):
    url = f"{OSRM_URL}/route/v1/driving/{orig_lon},{orig_lat};{dest_lon},{dest_lat}?overview=full&geometries=geojson"
    try:
        r = requests.get(url, timeout=5)
        data = r.json()
        if data.get('code') == 'Ok':
            return data['routes'][0]
    except Exception:
        return None
    return None

# Load data once
gdf = load_data()

# --- VALIDATION & ACCURACY METRICS (SIDEBAR) ---
st.sidebar.markdown("---")
st.sidebar.subheader("📊 Data & System Validation")

total_facilities = len(gdf)
valid_coords = gdf.geometry.is_valid.sum()
data_accuracy = (valid_coords / total_facilities) * 100

st.sidebar.metric(label="Data Completeness", value=f"{data_accuracy:.1f}%")
st.sidebar.caption(f"Validated {valid_coords} of {total_facilities} facility coordinates.")

st.sidebar.metric(label="Routing Engine", value="OSRM (Active)")
st.sidebar.caption("Live cloud-based route validation against OpenStreetMap.")
st.sidebar.markdown("---")

# --- MAIN APP UI ---
st.title("🚑 EthioHealth Access - Addis Ababa Pilot")
st.markdown("Select a clinic to find the fastest route to a nearby hospital.")

col1, col2 = st.columns([1, 3])

with col1:
    st.header("Dispatch Simulator")
    clinics = gdf[gdf['Type_Clean'] == 'Clinic'].copy()
    selected_clinic = st.selectbox("Select Patient Location (Clinic):", clinics['Name'].tolist())
    
    if selected_clinic:
        clinic_row = clinics[clinics['Name'] == selected_clinic].iloc[0]
        c_lon, c_lat = clinic_row.geometry.x, clinic_row.geometry.y
        st.info(f"Coordinates: {c_lat:.4f}, {c_lon:.4f}")
        
        hospitals = gdf[gdf['Type_Clean'].isin(['Hospital', 'Health Center'])].copy()
        
        if st.button("🚨 Find Nearest Hospital", type="primary"):
            with st.spinner("Routing via OSRM..."):
                hospitals['dist_deg'] = ((hospitals.geometry.x - c_lon)**2 + (hospitals.geometry.y - c_lat)**2)**0.5
                top_candidates = hospitals.nsmallest(10, 'dist_deg')
                
                best_route, best_hospital, min_time = None, None, float('inf')
                for _, row in top_candidates.iterrows():
                    route = get_route(c_lon, c_lat, row.geometry.x, row.geometry.y)
                    if route and route['duration'] < min_time:
                        min_time = route['duration']
                        best_route = route
                        best_hospital = row
                        
                if best_route:
                    st.success(f"Nearest Hospital: {best_hospital['Name']}")
                    st.write(f"**Distance:** {best_route['distance']/1000:.2f} km")
                    st.write(f"**Time:** {best_route['duration']/60:.1f} minutes")
                    
                    # --- ROUTING EFFICIENCY METRIC ---
                    R = 6371.0
                    lat1, lon1 = math.radians(c_lat), math.radians(c_lon)
                    lat2, lon2 = math.radians(best_hospital.geometry.y), math.radians(best_hospital.geometry.x)
                    dlat = lat2 - lat1
                    dlon = lon2 - lon1
                    a = math.sin(dlat / 2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2)**2
                    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
                    straight_dist = R * c
                    
                    drive_dist = best_route['distance'] / 1000
                    efficiency = (straight_dist / drive_dist) * 100 if drive_dist > 0 else 0
                    
                    st.info(f"**Routing Efficiency:** {efficiency:.1f}% (Directness of route)")
                    # ---------------------------------

                    st.session_state['route_geom'] = best_route['geometry']['coordinates']
                    st.session_state['dest_coords'] = [best_hospital.geometry.y, best_hospital.geometry.x]
                else:
                    st.error("No route found!")

with col2:
    m = folium.Map(location=[9.0116, 38.7878], zoom_start=12)
    for _, row in hospitals.iterrows():
        folium.Marker([row.geometry.y, row.geometry.x], popup=row['Name'], icon=folium.Icon(color='green', icon='plus', prefix='fa')).add_to(m)
    for _, row in clinics.iterrows():
        folium.CircleMarker([row.geometry.y, row.geometry.x], radius=3, color='blue', fill=True, fill_opacity=0.5, popup=row['Name']).add_to(m)

    if 'route_geom' in st.session_state:
        route_coords = [[lat, lon] for lon, lat in st.session_state['route_geom']]
        folium.PolyLine(route_coords, color="red", weight=5, opacity=0.8).add_to(m)
        folium.Marker(st.session_state['dest_coords'], popup="Destination", icon=folium.Icon(color='red', icon='ambulance', prefix='fa')).add_to(m)
        if selected_clinic:
            folium.Marker([c_lat, c_lon], popup="Origin", icon=folium.Icon(color='blue', icon='user', prefix='fa')).add_to(m)

    st_folium(m, width=1000, height=600)