import streamlit as st
import ee
import folium
from streamlit_folium import st_folium
import pandas as pd

# ==========================================
# 1. SYSTEM CONFIG & AUTHENTICATION
# ==========================================
st.set_page_config(layout="wide", page_title="AgriGeo-Shield Pro",
                   initial_sidebar_state="expanded")


@st.cache_data
def ee_authenticate():
    my_project = 'enter your project id from GEE'  # YOUR PROJECT ID
    try:
        ee.Initialize(project=my_project)
    except Exception:
        ee.Authenticate()
        ee.Initialize(project=my_project)


ee_authenticate()

# ==========================================
# 2. SIDEBAR - UI/UX CONTROLS
# ==========================================
st.sidebar.title("🛠️ AgriGeo-Shield")
st.sidebar.markdown("### Spatial Intelligence Engine")
st.sidebar.markdown("---")

target_state = st.sidebar.selectbox(
    "Select State:", ["Tamil Nadu", "West Bengal"])

if target_state == "Tamil Nadu":
    dist_dict = {
        "Coimbatore": "Coimbatore",
        "Dindigul": "Dindigul",
        "Tiruchirappalli (Trichy)": "Tiruchchirappalli",
        "Madurai": "Madurai",
        "Chennai": "Chennai",
        "Salem": "Salem",
        "Erode": "Erode",
        "Tirunelveli": "Tirunelveli",
        "Vellore": "Vellore",
        "Kanyakumari": "Kanniyakumari",
        "Thanjavur": "Thanjavur"
    }
else:
    dist_dict = {
        "Santipur Region (Local)": "Custom",
        "Nadia": "Nadia",
        "Kolkata": "Kolkata",
        "Darjeeling": "Darjiling",
        "Howrah": "Haora",
        "Hooghly": "Hugli"
    }

selected_display = st.sidebar.selectbox(
    "Select Region/District:", list(dist_dict.keys()))
target_district_gaul = dist_dict[selected_display]

pop_dict = {
    "Coimbatore": "3,100,000",
    "Dindigul": "2,450,000",
    "Tiruchirappalli (Trichy)": "3,000,000",
    "Madurai": "3,500,000",
    "Chennai": "12,800,000",
    "Salem": "3,950,000",
    "Erode": "2,600,000",
    "Tirunelveli": "2,000,000",
    "Vellore": "1,850,000",
    "Kanyakumari": "2,150,000",
    "Thanjavur": "2,800,000",
    "Santipur Region (Local)": "350,000",
    "Nadia": "5,800,000",
    "Kolkata": "15,300,000",
    "Darjeeling": "2,100,000",
    "Howrah": "5,400,000",
    "Hooghly": "6,100,000"
}
display_population = pop_dict.get(selected_display, "Data Unavailable")

target_year = st.sidebar.slider("Select Analysis Year:", 2020, 2023, 2023)

st.sidebar.markdown("---")
analysis_type = st.sidebar.radio(
    "Select Intelligence Layer:",
    [
        "1. Drought Risk (LST)",
        "2. Groundwater Potential (NDWI)",
        "3. Annual Rainfall (CHIRPS)",
        "4. Heat Anomaly (Change)",
        "5. Mineral Mapping (Landsat 8)",
        "6. Land Use & Crop Masking (ESA 10m)"  # NEW LAYER
    ]
)

# ==========================================
# 3. GEOSPATIAL BACKEND ENGINE
# ==========================================
if target_district_gaul == "Custom":
    custom_geom = ee.Geometry.Point([88.4344, 23.2423]).buffer(15000)
    study_area = ee.FeatureCollection(
        [ee.Feature(custom_geom, {'name': 'Local Region'})])
else:
    gaul = ee.FeatureCollection("FAO/GAUL/2015/level2")
    state_boundary = gaul.filter(ee.Filter.eq('ADM1_NAME', target_state))
    study_area = state_boundary.filter(
        ee.Filter.eq('ADM2_NAME', target_district_gaul))

with st.sidebar:
    st.markdown("---")
    st.markdown("#### 🗺️ National Overview")
    mini_map = folium.Map(location=[22.0, 79.0], zoom_start=4,
                          tiles="CartoDB dark_matter", control_scale=False, zoom_control=False)
    try:
        mini_center = study_area.geometry().centroid().getInfo()['coordinates']
        folium.Marker(location=[mini_center[1], mini_center[0]], popup=selected_display, icon=folium.Icon(
            color="red", icon="info-sign")).add_to(mini_map)
    except:
        pass
    st_folium(mini_map, width=300, height=250,
              key="minimap", returned_objects=[])

start_date = f'{target_year}-01-01'
end_date = f'{target_year}-12-31'
prev_start = f'{target_year-1}-01-01'
prev_end = f'{target_year-1}-12-31'

# Data Collections
lst_col = ee.ImageCollection("MODIS/061/MOD11A2").select('LST_Day_1km')
ndwi_col = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
rain_col = ee.ImageCollection("UCSB-CHG/CHIRPS/DAILY")
l8_col = ee.ImageCollection("LANDSAT/LC08/C02/T1_TOA")
# ESA WorldCover for LULC (10m Resolution)
lulc_image = ee.ImageCollection("ESA/WorldCover/v200").first().clip(study_area)

# Processing
l8_image = l8_col.filterDate(start_date, end_date).filterBounds(
    study_area.geometry()).filter(ee.Filter.lt('CLOUD_COVER', 20)).median().clip(study_area)
lst_current = lst_col.filterDate(start_date, end_date).mean().multiply(
    0.02).subtract(273.15).clip(study_area)
lst_prev = lst_col.filterDate(prev_start, prev_end).mean().multiply(
    0.02).subtract(273.15).clip(study_area)
lst_anomaly = lst_current.subtract(lst_prev)
ndwi_current = ndwi_col.filterDate(start_date, end_date).median(
).normalizedDifference(['B3', 'B8']).clip(study_area)
rain_current = rain_col.filterDate(start_date, end_date).sum().clip(study_area)
clay_index = l8_image.select('B6').divide(
    l8_image.select('B7')).rename('Clay_Alteration')

with st.spinner(f"🛰️ Fetching satellite intelligence for {selected_display}..."):
    try:
        avg_lst = round(lst_current.reduceRegion(ee.Reducer.mean(), study_area.geometry(
        ), 1000, bestEffort=True).getInfo().get('LST_Day_1km', 0), 2)
        avg_ndwi = round(ndwi_current.reduceRegion(ee.Reducer.mean(
        ), study_area.geometry(), 1000, bestEffort=True).getInfo().get('nd', 0), 3)
        avg_rain = round(rain_current.reduceRegion(ee.Reducer.mean(), study_area.geometry(
        ), 5000, bestEffort=True).getInfo().get('precipitation', 0), 0)
        avg_clay_idx = round(clay_index.reduceRegion(ee.Reducer.mean(), study_area.geometry(
        ), 1000, bestEffort=True).getInfo().get('Clay_Alteration', 0), 2)
    except:
        avg_lst, avg_ndwi, avg_rain, avg_clay_idx = 0, 0, 0, 0

if avg_lst >= 35 and avg_rain < 800:
    total_interp = "Severe Drought Risk 🔴"
elif avg_lst >= 32 and avg_rain < 1000:
    total_interp = "Moderate Eco-Stress 🟡"
elif avg_rain > 1600:
    total_interp = "Flood/Saturation Risk 🔵"
else:
    total_interp = "Optimal & Stable 🟢"

# ==========================================
# 4. TOP DASHBOARD: KPIs
# ==========================================
st.title(f"🌍 Intelligence Overview: {selected_display}")
st.markdown(
    "#### *AI-powered geospatial decision engine for climate-resilient agriculture.*")
st.markdown("<br>", unsafe_allow_html=True)

kpi1, kpi2, kpi3, kpi4 = st.columns(4)
kpi1.metric("👥 Total Population", display_population)
kpi2.metric("🌡️ Avg Temp (LST)", f"{avg_lst} °C")
kpi3.metric("💧 Moisture (NDWI)", avg_ndwi)
kpi4.metric("🌧️ Annual Rainfall", f"{avg_rain} mm")

st.markdown("---")

# ==========================================
# 5. DYNAMIC MAP LEGEND BUILDER
# ==========================================


def draw_legend(title, colors, labels):
    html = f"<div style='margin-bottom: 5px;'><b>📊 MAP INDEX: {title}</b><br><div style='display: flex; flex-direction: row; margin-top: 5px; flex-wrap: wrap;'>"
    for c, l in zip(colors, labels):
        html += f"<div style='display:flex; align-items:center; margin-right:15px; margin-bottom:5px;'><div style='background-color:{c}; width:30px; height:15px; border:1px solid #333; margin-right:5px;'></div><span style='font-size:13px;'>{l}</span></div>"
    html += "</div></div>"
    st.markdown(html, unsafe_allow_html=True)


# ==========================================
# 6. MAIN MAP RENDERING & EXPORT SETUP
# ==========================================
try:
    center = study_area.geometry().centroid().getInfo()['coordinates']
    m = folium.Map(location=[center[1], center[0]],
                   zoom_start=10, tiles="CartoDB positron")
except:
    m = folium.Map(location=[10.2789, 77.9339], zoom_start=9)


def add_ee_layer(ee_object, vis_params, name):
    map_id = ee.Image(ee_object).getMapId(vis_params)
    folium.raster_layers.TileLayer(
        tiles=map_id['tile_fetcher'].url_format, attr='GEE', name=name, overlay=True
    ).add_to(m)


active_image = None
export_scale = 1000
export_name = "Export"

if "LST" in analysis_type:
    active_image = lst_current
    export_scale = 1000
    export_name = f"LST_{target_year}_{selected_display.replace(' ', '_')}"
    v_min, v_max = round(avg_lst - 3, 1), round(avg_lst + 3, 1)
    step = round((v_max - v_min) / 5, 1)
    colors = ['#313695', '#91bfdb', '#ffffbf', '#fc8d59', '#d73027', '#a50026']
    labels = [f"<{v_min}°C", f"{v_min} - {round(v_min+step,1)}°C", f"{round(v_min+step,1)} - {round(v_min+step*2,1)}°C",
              f"{round(v_min+step*2,1)} - {round(v_min+step*3,1)}°C", f"{round(v_min+step*3,1)} - {v_max}°C", f">{v_max}°C"]
    draw_legend(
        f"High-Res Land Surface Temp (Dynamic Stretch: {v_min}°C to {v_max}°C)", colors, labels)
    add_ee_layer(lst_current, {'min': v_min,
                 'max': v_max, 'palette': colors}, "LST Heatmap")

elif "NDWI" in analysis_type:
    active_image = ndwi_current
    export_scale = 10
    export_name = f"NDWI_{target_year}_{selected_display.replace(' ', '_')}"
    v_min, v_max = round(avg_ndwi - 0.2, 2), round(avg_ndwi + 0.2, 2)
    step = round((v_max - v_min) / 5, 2)
    colors = ['#d73027', '#fc8d59', '#fee08b', '#d9ef8b', '#91cf60', '#1a9850']
    labels = [f"<{v_min}", f"{v_min} to {round(v_min+step,2)}", f"{round(v_min+step,2)} to {round(v_min+step*2,2)}",
              f"{round(v_min+step*2,2)} to {round(v_min+step*3,2)}", f"{round(v_min+step*3,2)} to {v_max}", f">{v_max}"]
    draw_legend(
        f"Moisture NDWI (Dynamic Stretch around {avg_ndwi})", colors, labels)
    add_ee_layer(ndwi_current, {
                 'min': v_min, 'max': v_max, 'palette': colors}, "Moisture Index")

elif "Rainfall" in analysis_type:
    active_image = rain_current
    export_scale = 5500
    export_name = f"Rainfall_{target_year}_{selected_display.replace(' ', '_')}"
    r_min = max(0, int(avg_rain - 300))
    r_max = int(avg_rain + 300)
    step = (r_max - r_min) // 5
    colors = ['#ffffcc', '#c7e9b4', '#7fcdbb', '#41b6c4', '#2c7fb8', '#253494']
    labels = [f"<{r_min} mm", f"{r_min}-{r_min+step} mm", f"{r_min+step}-{r_min+step*2} mm",
              f"{r_min+step*2}-{r_min+step*3} mm", f"{r_min+step*3}-{r_max} mm", f">{r_max} mm"]
    draw_legend(
        f"Annual Precipitation (Dynamic Scale for {selected_display})", colors, labels)
    add_ee_layer(rain_current, {
                 'min': r_min, 'max': r_max, 'palette': colors}, "Annual Rainfall")

elif "Mineral" in analysis_type:
    active_image = clay_index
    export_scale = 30
    export_name = f"Mineral_Clay_Index_{target_year}_{selected_display.replace(' ', '_')}"
    colors = ['#ffffcc', '#a1dab4', '#41b6c4', '#2c7fb8', '#253494']
    labels = ['Low Mineral Alteration', 'Slight Alteration',
              'Moderate Clay Content', 'High Clay Content', 'Hydrothermal Alteration Zone']
    draw_legend("Landsat 8 Clay & Hydrothermal Index (B6 / B7)", colors, labels)
    add_ee_layer(clay_index, {'min': 0.8, 'max': 1.6,
                 'palette': colors}, "Mineral Alteration")

elif "Land Use" in analysis_type:
    active_image = lulc_image
    export_scale = 10
    export_name = f"LULC_ESA10m_{selected_display.replace(' ', '_')}"
    # ESA WorldCover Palette: 10 Trees, 40 Cropland, 50 Built-up, 60 Barren, 80 Water
    vis_lulc = {'bands': ['Map'], 'min': 10, 'max': 100, 'palette': [
        '006400', 'ffbb22', 'ffff4c', 'f096ff', 'fa0000', 'b4b4b4', 'f0f0f0', '0064c8', '0096a0', '00cf75', 'fae6a0']}
    colors = ['#006400', '#ffff4c', '#fa0000', '#b4b4b4', '#0064c8']
    labels = ['Forests & Trees', 'Cropland (Net Sown Area)',
              'Built-up (Urban)', 'Barren / Uncultivable', 'Water Bodies']
    draw_legend("Land Use / Land Cover (ESA 10m Classification)",
                colors, labels)
    add_ee_layer(lulc_image, vis_lulc, "ESA WorldCover LULC")

else:
    active_image = lst_anomaly
    export_scale = 1000
    export_name = f"Heat_Anomaly_{target_year}_{selected_display.replace(' ', '_')}"
    colors = ['#313695', '#74add1', '#e0f3f8', '#fee090', '#f46d43', '#d73027']
    labels = ['Much Cooler (< -1.5°C)', 'Slightly Cooler', 'No Change',
              'Slightly Hotter', 'Hotter', 'Much Hotter (> 1.5°C)']
    draw_legend("Year-Over-Year Heat Anomaly", colors, labels)
    add_ee_layer(lst_anomaly, {'min': -1.5, 'max': 1.5,
                 'palette': colors}, "Temp Change")

outline = ee.Image().byte().paint(featureCollection=study_area, color=1, width=3)
add_ee_layer(outline, {'palette': ['#000000']}, "Boundary")

st_folium(m, width=1200, height=500, returned_objects=[])

# ==========================================
# 7. BOTTOM SECTION: AI INTERPRETATION & DOWNLOADS
# ==========================================
st.markdown("---")
col_ai, col_down = st.columns([2, 1])

with col_ai:
    st.markdown(f"### 🎯 Regional Verdict: {total_interp}")

    if "LST" in analysis_type:
        st.info(
            f"**Layer Interpretation:** This map displays MODIS Land Surface Temperature (LST). Red zones indicate high thermal stress and potential agricultural drought. The regional average is {avg_lst}°C.")
        if avg_lst >= 35:
            st.error("**🤖 AI Action Plan:** Critical thermal stress detected. Pivot to drought-resistant crops (Sorghum, Pearl Millet) for the next cycle.")
        else:
            st.success(
                "**🤖 AI Action Plan:** Temperatures are within manageable agricultural ranges. Proceed with standard Kharif/Rabi cycle.")

    elif "NDWI" in analysis_type:
        st.info(
            f"**Layer Interpretation:** Sentinel-2 Normalized Difference Water Index (NDWI). Blue/Green areas represent surplus moisture, while red/orange indicate severe deficit. The regional average is {avg_ndwi}.")
        if avg_ndwi < 0:
            st.error("**🤖 AI Action Plan:** Severe surface water deficit detected. Pause planting of water-intensive crops like Paddy or Sugarcane. Implement micro-irrigation systems.")
        else:
            st.success(
                "**🤖 AI Action Plan:** Good soil moisture index. Ideal conditions for major cash crops. Continue standard irrigation scheduling.")

    elif "Rainfall" in analysis_type:
        st.info(
            f"**Layer Interpretation:** CHIRPS daily precipitation data aggregated annually. Total regional rainfall is {avg_rain}mm.")
        if avg_rain < 600:
            st.error("**🤖 AI Action Plan:** Rainfall is dangerously low. Restrict agricultural groundwater usage to prevent aquifer depletion. Prioritize dryland farming techniques.")
        elif avg_rain > 1600:
            st.error("**🤖 AI Action Plan:** High flood risk detected. Ensure agricultural drainage channels and canals are cleared before monsoon peaks.")
        else:
            st.success(
                "**🤖 AI Action Plan:** Rainfall is sufficient to support the local agricultural economy and naturally recharge groundwater aquifers.")

    elif "Mineral" in analysis_type:
        st.info(
            f"**Layer Interpretation:** Landsat 8 Band 6/7 ratio. High ratios (dark blue) isolate clay-rich topsoil or hydrothermally altered rock formations. The index is {avg_clay_idx}.")
        st.warning("**🤖 AI Action Plan:** \n* **For Groundwater:** Target the dark blue zones (hydrothermal alteration fault lines) for high-yield borewell drilling. \n* **For Agriculture:** High clay indices indicate good surface water retention. Excellent for paddy, but requires deep plowing to prevent waterlogging.")

    elif "Land Use" in analysis_type:
        st.info("**Layer Interpretation:** High-resolution 10m ESA WorldCover classification. This separates the landscape based on distinct spectral signatures, accurately mapping the 9-fold classification system (Net Sown Area vs. Non-Agricultural Uses).")
        st.warning("**🤖 AI Action Plan:** \n* **Spatial Masking:** Use the yellow zones (Cropland / Net Sown Area) to mask the LST and NDWI arrays. This ensures thermal and drought recommendations are generated strictly for cultivable lands, ignoring the false heat signatures of red zones (Built-up/Urban concrete) and the false cooling effects of green zones (Dense Forests).")

    else:
        st.info("**Layer Interpretation:** Temporal Heat Anomaly. Dynamically subtracts last year's average LST from this year's LST.")
        st.warning("**🤖 AI Action Plan:** Review the deep red zones on the map. These areas represent newly formed Urban Heat Islands or freshly degraded agricultural lands. Prioritize these zones for afforestation.")

with col_down:
    st.markdown("### 📥 Export Architecture")

    with st.expander("ℹ️ How Export Logic Works"):
        st.write("""
        **The Solution to Payload Limits:**
        * **Local Preview:** Generates a quick, compressed local link for rapid viewing.
        * **Cloud-to-Drive Sync:** Leverages `ee.batch.Export` to offload processing to Google's backend. Extracts true WGS84 10m–30m raw GeoTIFFs directly to Google Drive.
        """)

    try:
        safe_local_scale = max(500, export_scale)
        local_url = active_image.getDownloadURL({
            'scale': safe_local_scale,
            'crs': 'EPSG:4326',
            'region': study_area.geometry()
        })
        st.link_button("⬇️ Fast Local Preview (Compressed)",
                       local_url, use_container_width=True)
    except Exception:
        st.error("Local download unavailable for this region size.")

    if st.button(f"☁️ Export High-Res GeoTIFF to Google Drive", type="primary", use_container_width=True):
        with st.spinner(f"Initiating Google Cloud backend task for {export_name}.tif at {export_scale}m resolution..."):
            try:
                task = ee.batch.Export.image.toDrive(
                    image=active_image,
                    description=export_name,
                    folder='AgriGeo_Shield_Exports',
                    fileNamePrefix=export_name,
                    region=study_area.geometry().bounds(),
                    scale=export_scale,
                    crs='EPSG:4326',
                    maxPixels=1e13
                )
                task.start()
                st.success(
                    f"✅ **Task Started!** High-res {export_scale}m data is rendering. Check your Google Drive 'AgriGeo_Shield_Exports' folder in a few minutes.")
            except Exception as e:
                st.error(f"Failed to initiate export: {e}")

    csv = pd.DataFrame({"Region": [selected_display], "Year": [target_year], "Status": [
                       total_interp], "Avg_Rain_mm": [avg_rain], "Avg_LST": [avg_lst]}).to_csv(index=False)
    st.download_button(label="📄 Download Regional Statistics (CSV)", data=csv,
                       file_name=f"{selected_display}_report_{target_year}.csv", mime='text/csv', use_container_width=True)
