import os
import streamlit as st
import geopandas as gpd
import folium
from streamlit_folium import st_folium
import requests

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="EthioHealth Access", 
    page_icon="assets/logo.png", # Set the browser tab icon to your logo
    layout="wide"
)

# --- LOGO INTEGRATION ---
if os.path.exists("assets/logo.png"):
    st.logo("assets/logo.png", size="large") # Top left corner
    st.sidebar.image("assets/logo.png", use_container_width=True) # Sidebar
else:
    st.sidebar.warning("⚠️ Logo missing! Check assets/logo.png")
# ------------------------

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

st.title("🚑 EthioHealth Access - Addis Ababa Pilot")
st.markdown("Select a clinic to find the fastest route to a nearby hospital.")

gdf = load_data()
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