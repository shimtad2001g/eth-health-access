# Modelling assumptions and known gaps

1. Oxford MAP travel-time surface is WALKING baseline. Never mixed with
   OSRM ambulance ETAs in any UI metric.
2. Nationwide open LiDAR does not exist for Ethiopia. ALOS AW3D30 (30 m)
   is the national DEM. Local LiDAR used only where available.
3. OSM remote-road coverage is uneven. Unpaved tracks use default speeds;
   validate in pastoral areas before trusting ETAs.
4. 24/7 mode applies night-time and rainy-season speed reductions on top of
   the base OSRM profile (toggle in UI, not baked into the graph).