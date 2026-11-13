import geopandas as gpd
import requests
import json

print('Loading facilities...')
gdf = gpd.read_file('data/processed/facilities_addis.gpkg')

# Pick one Clinic (Origin) and one Hospital (Destination)
clinic = gdf[gdf['Type_Clean'] == 'Clinic'].iloc[0]
hospital = gdf[gdf['Type_Clean'] == 'Hospital'].iloc[0]

# OSRM expects coordinates in (Longitude, Latitude) format
orig_lon, orig_lat = clinic.geometry.x, clinic.geometry.y
dest_lon, dest_lat = hospital.geometry.x, hospital.geometry.y

print('\n--- EMERGENCY ROUTING TEST ---')
print(f"Origin Clinic: {clinic['Name']} ({orig_lon:.4f}, {orig_lat:.4f})")
print(f"Destination Hospital: {hospital['Name']} ({dest_lon:.4f}, {dest_lat:.4f})")

# OSRM API URL
url = f'http://localhost:5000/route/v1/driving/{orig_lon},{orig_lat};{dest_lon},{dest_lat}?overview=false'

print('\nCalling OSRM API...')
response = requests.get(url)
data = response.json()

if data.get('code') == 'Ok':
    route = data['routes'][0]
    distance_km = route['distance'] / 1000
    duration_mins = route['duration'] / 60
    
    print('\n✅ ROUTE FOUND!')
    print(f'  Distance: {distance_km:.2f} km')
    print(f'  Est. Travel Time: {duration_mins:.1f} minutes')
else:
    print('\n❌ Route not found. OSRM Response:')
    print(json.dumps(data, indent=2))