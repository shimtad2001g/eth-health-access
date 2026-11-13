import geopandas as gpd
import pandas as pd
from pathlib import Path

IN_SHP = "data/interim/facilities/Ethiopian_health_Facilities/Ethiopian Health Facilities.shp"
OUT_GPKG = "data/processed/facilities_addis.gpkg"
OUT_ETH_GPKG = "data/processed/facilities_ethiopia.gpkg"

print(f"Loading: {IN_SHP}")
gdf = gpd.read_file(IN_SHP)

if 'Status' in gdf.columns:
    gdf = gdf[gdf['Status'].astype(str).str.lower() == 'approved']
    print(f"Facilities after 'Approved' filter: {len(gdf):,}")

ownership_map = {
    'Public/Government': 'Public',
    'Other Government': 'Public',
    'Private for profit': 'Private',
    'Private Not for profit': 'Private'
}
gdf['Ownership_Clean'] = gdf['Ownership'].map(ownership_map).fillna('Other')

type_map = {
    'Hospital': 'Hospital',
    'Specialty Center': 'Hospital',
    'Health Center': 'Health Center',
    'Clinic': 'Clinic',
    'Specialty Clinic': 'Clinic',
    'Health Post': 'Health Post',
    'Pharmacy': 'Pharmacy'
}
gdf['Type_Clean'] = gdf['Type'].map(type_map)

valid_types = ['Hospital', 'Health Center', 'Clinic', 'Health Post', 'Pharmacy']
gdf = gdf[gdf['Type_Clean'].isin(valid_types)].copy()
print(f"Facilities after type filtering: {len(gdf):,}")

gdf.to_file(OUT_ETH_GPKG, driver="GPKG")
print(f"Saved full Ethiopia dataset to {OUT_ETH_GPKG}")

print("Filtering to Addis Ababa bounding box...")
addis = gdf.cx[38.60:39.00, 8.80:9.10].copy()
print(f"Facilities in Addis Ababa pilot: {len(addis):,}")

print("\n--- ADDIS ABABA FACILITY SUMMARY ---")
print(addis.groupby(['Type_Clean', 'Ownership_Clean']).size().unstack(fill_value=0))

addis.to_file(OUT_GPKG, driver="GPKG")
print(f"\nSaved Addis Ababa pilot dataset to {OUT_GPKG}")