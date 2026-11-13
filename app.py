import streamlit as st
import os

# --- LOGO & PAGE CONFIGURATION ---
st.set_page_config(
    page_title="Ethio Health Access",
    page_icon="assets/logo.png",
    layout="wide",
)

# Add the logo to the top-left corner and sidebar
if os.path.exists("assets/logo.png"):
    st.logo(
        "assets/logo.png",
        size="large",
        link="https://ethio-health-access.streamlit.app/",
        icon_image="assets/logo.png",
    )
else:
    st.warning("⚠️ Logo asset missing — check assets/logo.png")
# ---------------------------------

# --- (Your existing app code is down here) ---
# st.title("Welcome to my app")
# ...