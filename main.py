import streamlit as st
import ee
import folium
from streamlit_folium import st_folium
import pandas as pd
import plotly.express as px

# ==========================================
# 1. SYSTEM CONFIG & AUTHENTICATION
# ==========================================
st.set_page_config(layout="wide", page_title="AgriGeo-Shield Pro",
                   initial_sidebar_state="expanded")

@st.cache_data
def ee_authenticate():
    my_project = 'emerald-skill-479306-i0'  # YOUR PROJECT ID
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

target_state = st.sidebar.selectbox("Select State:", ["Tamil Nadu", "West Bengal"])

if target_state == "Tamil Nadu":
    dist_dict = {
        "Coimbatore": "Coimbatore", "Dindigul": "Dindigul", "Tiruchirappalli (Trichy)": "Tiruchchirappalli",
        "Madurai": "Madurai", "Chennai": "Chennai", "Salem": "Salem", "Erode": "Erode",
        "Tirunelveli": "Tirunelveli", "Vellore": "Vellore", "Kanyakumari": "Kanniyakumari", "Thanjavur": "Thanjavur"
    }
else:
    dist_dict = {
        "Santipur Region (Local)": "Custom", "Nadia": "Nadia", "Kolkata": "Kolkata",
        "Darjeeling": "Darjiling", "Howrah": "Haora", "Hooghly": "Hugli"
    }

selected_display = st.sidebar.selectbox("Select Region/District:", list(dist_dict.keys()))
target_district_gaul = dist_dict[selected_display]

pop_dict = {
    "Coimbatore": "3,100,000", "Dindigul": "2,450,000", "Tiruchirappalli (Trichy)": "3,000,000",
    "Madurai": "3,500,000", "Chennai": "12,800,000", "Salem": "3,950,000", "Erode": "2,600,000",
    "Tirunelveli": "2,000,000", "Vellore": "1,850,000", "Kanyakumari": "2,150,000", "Thanjavur": "2,800,000",
    "Santipur Region (Local)": "350,000", "Nadia": "5,800,000", "Kolkata": "15,300,000",
    "Darjeeling": "2,100,000", "Howrah": "5,400,000", "Hooghly": "6,100,000"
}
display_population = pop_dict.get(selected_display, "Data Unavailable")

# THE UPGRADE: Added Dual Year Selectors
target_year = st.sidebar.slider("Select Analysis Year (Main):", 2018, 2023, 2023)
compare_year = st.sidebar.slider("Compare vs Year (Chart):", 2018, 2023, 2022)

st.sidebar.markdown("---")
analysis_type = st.sidebar.radio(
    "Select Intelligence Layer:",
    [
        "1. Drought Risk (LST)",
        "2. Groundwater Potential (NDWI)",
        "3. Crop Health (NDVI)",
        "4. Annual Rainfall (CHIRPS)",
        "5. Heat Anomaly (Change)",
        "6. Mineral Mapping (Landsat 8)",
        "7. Land Use & Crop Masking (ESA 10m)"
    ]
)

# ==========================================
# 3. GEOSPATIAL BACKEND ENGINE
# ==========================================
if target_district_gaul == "Custom":
    custom_geom = ee.Geometry.Point([88.4344, 23.2423]).buffer(15000)
    study_area = ee.FeatureCollection([ee.Feature(custom_geom, {'name': 'Local Region'})])
else:
    gaul = ee.FeatureCollection("FAO/GAUL/2015/level2")
    state_boundary = gaul.filter(ee.Filter.eq('ADM1_NAME', target_state))
    study_area = state_boundary.filter(ee.Filter.eq('ADM2_NAME', target_district_gaul))

with st.sidebar:
    st.markdown("---")
    st.markdown("#### National Overview")
    mini_map = folium.Map(location=[22.0, 79.0], zoom_start=4, tiles="CartoDB dark_matter", control_scale=False, zoom_control=False)
    try:
        mini_center = study_area.geometry().centroid().getInfo()['coordinates']
        folium.Marker(location=[mini_center[1], mini_center[0]], popup=selected_display, icon=folium.Icon(color="red", icon="info-sign")).add_to(mini_map)
    except:
        pass
    st_folium(mini_map, width=300, height=250, key="minimap", returned_objects=[])

start_date = f'{target_year}-01-01'
end_date = f'{target_year}-12-31'
prev_start = f'{target_year-1}-01-01'
prev_end = f'{target_year-1}-12-31'

# Data Collections
lst_col = ee.ImageCollection("MODIS/061/MOD11A2").select('LST_Day_1km')
ndwi_col = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
rain_col = ee.ImageCollection("UCSB-CHG/CHIRPS/DAILY")
l8_col = ee.ImageCollection("LANDSAT/LC08/C02/T1_TOA")
lulc_image = ee.ImageCollection("ESA/WorldCover/v200").first().clip(study_area)

# Processing
l8_image = l8_col.filterDate(start_date, end_date).filterBounds(study_area.geometry()).filter(ee.Filter.lt('CLOUD_COVER', 20)).median().clip(study_area)
lst_current = lst_col.filterDate(start_date, end_date).mean().multiply(0.02).subtract(273.15).clip(study_area)
lst_prev = lst_col.filterDate(prev_start, prev_end).mean().multiply(0.02).subtract(273.15).clip(study_area)
lst_anomaly = lst_current.subtract(lst_prev)
ndwi_current = ndwi_col.filterDate(start_date, end_date).median().normalizedDifference(['B3', 'B8']).clip(study_area)
ndvi_current = ndwi_col.filterDate(start_date, end_date).median().normalizedDifference(['B8', 'B4']).clip(study_area)
rain_current = rain_col.filterDate(start_date, end_date).sum().clip(study_area)

# Mineral Processing
iron_oxide = l8_image.select('B4').divide(l8_image.select('B2')).rename('Iron')
ferrous = l8_image.select('B6').divide(l8_image.select('B5')).rename('Ferrous')
clay_index = l8_image.select('B6').divide(l8_image.select('B7')).rename('Clay')
mineral_composite = ee.Image.cat([iron_oxide, ferrous, clay_index])

with st.spinner(f"🛰️ Fetching satellite intelligence for {selected_display}..."):
    try:
        avg_lst = round(lst_current.reduceRegion(ee.Reducer.mean(), study_area.geometry(), 1000, bestEffort=True).getInfo().get('LST_Day_1km', 0), 2)
        avg_ndwi = round(ndwi_current.reduceRegion(ee.Reducer.mean(), study_area.geometry(), 1000, bestEffort=True).getInfo().get('nd', 0), 3)
        avg_ndvi = round(ndvi_current.reduceRegion(ee.Reducer.mean(), study_area.geometry(), 1000, bestEffort=True).getInfo().get('nd', 0), 3)
        avg_rain = round(rain_current.reduceRegion(ee.Reducer.mean(), study_area.geometry(), 5000, bestEffort=True).getInfo().get('precipitation', 0), 0)
        avg_clay_idx = round(clay_index.reduceRegion(ee.Reducer.mean(), study_area.geometry(), 1000, bestEffort=True).getInfo().get('Clay', 0), 2)
    except:
        avg_lst, avg_ndwi, avg_ndvi, avg_rain, avg_clay_idx = 0, 0, 0, 0, 0

# ==========================================
# THE UPGRADE: DYNAMIC RISK SCORE ENGINE
# ==========================================
risk_score = 0
if avg_lst >= 35: risk_score += 4
elif avg_lst >= 32: risk_score += 2
if avg_rain < 800: risk_score += 4
elif avg_rain < 1000: risk_score += 2
if avg_ndvi < 0.2: risk_score += 2
elif avg_ndvi < 0.4: risk_score += 1

risk_score = min(10, risk_score) # Cap at 10

if risk_score >= 7:
    total_interp = "Severe Drought Risk"
    v_color = "#E74C3C" # Red
    v_icon = "🔴"
elif risk_score >= 4:
    total_interp = "Moderate Eco-Stress"
    v_color = "#F1C40F" # Yellow
    v_icon = "🟡"
else:
    total_interp = "Optimal & Stable"
    v_color = "#2ECC71" # Green
    v_icon = "🟢"

# ==========================================
# 4. TOP DASHBOARD: KPIs
# ==========================================
st.title(f"Intelligence Overview: {selected_display}")
st.markdown("#### *AI-powered geospatial decision engine for climate-resilient agriculture.*")
st.markdown("<br>", unsafe_allow_html=True)

kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
kpi1.metric(" Total Population", display_population)
kpi2.metric(" Avg Temp (LST)", f"{avg_lst} °C")
kpi3.metric(" Moisture (NDWI)", avg_ndwi)
kpi4.metric(" Biomass (NDVI)", avg_ndvi)
kpi5.metric(" Annual Rainfall", f"{avg_rain} mm")

st.markdown("---")

# ==========================================
# 4.5 TIME-SERIES CHART ENGINE (COMPARATIVE)
# ==========================================
with st.spinner(f"📊 Generating Comparative Time-Series ({target_year} vs {compare_year})..."):
    try:
        core_sample = study_area.geometry().centroid().buffer(3000)
        
        if "LST" in analysis_type or "Heat" in analysis_type:
            y_label = "Temperature (°C)"
            chart_title = "Monthly Land Surface Temperature (LST)"
        elif "NDWI" in analysis_type:
            y_label = "Moisture Index (NDWI)"
            chart_title = "Monthly Moisture Index (NDWI)"
        elif "NDVI" in analysis_type:
            y_label = "Vegetation Index (NDVI)"
            chart_title = "Monthly Crop Biomass (NDVI)"
        else:
            y_label = "Rainfall (mm)"
            chart_title = "Monthly Precipitation Accumulation"

        y_target = []
        y_compare = []
        x_months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

        def fetch_month_val(year, m):
            start = ee.Date.fromYMD(year, m, 1)
            end = start.advance(1, 'month')
            try:
                if "LST" in analysis_type or "Heat" in analysis_type:
                    img = lst_col.filterBounds(core_sample).filterDate(start, end).mean().multiply(0.02).subtract(273.15).rename('val')
                elif "NDWI" in analysis_type:
                    img = ndwi_col.filterBounds(core_sample).filterDate(start, end).median().normalizedDifference(['B3', 'B8']).rename('val')
                elif "NDVI" in analysis_type:
                    img = ndwi_col.filterBounds(core_sample).filterDate(start, end).median().normalizedDifference(['B8', 'B4']).rename('val')
                else:
                    img = rain_col.filterBounds(core_sample).filterDate(start, end).sum().rename('val')
                    
                val = img.reduceRegion(reducer=ee.Reducer.mean(), geometry=core_sample, scale=1000, maxPixels=1e6).get('val').getInfo()
                return val
            except:
                return None

        # Loop through months for BOTH years
        for m in range(1, 13):
            val_t = fetch_month_val(target_year, m)
            val_c = fetch_month_val(compare_year, m)
            
            y_target.append(val_t if val_t is not None else (y_target[-1] if len(y_target) > 0 else 0))
            y_compare.append(val_c if val_c is not None else (y_compare[-1] if len(y_compare) > 0 else 0))

        # Build the Dual-Line Plotly Chart
        df_chart = pd.DataFrame({'Month': x_months, f'{target_year} (Target)': y_target, f'{compare_year} (Compare)': y_compare})
        fig = px.line(df_chart, x='Month', y=[f'{target_year} (Target)', f'{compare_year} (Compare)'], markers=True, 
                      title=f"{chart_title}: {target_year} vs {compare_year}", template="plotly_dark")
        
        fig.update_traces(line_width=3, marker=dict(size=8))
        fig['data'][0]['line']['color'] = '#2ECC71' # Green for Target
        fig['data'][1]['line']['color'] = '#E74C3C' # Red for Compare
        fig.update_layout(margin=dict(l=20, r=20, t=40, b=20), height=350, plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', legend_title_text='')
        
        st.plotly_chart(fig, use_container_width=True)
        st.markdown("---")
        
    except Exception as e:
        st.warning(f"Time-series data could not be generated. (Error: {e})")

# ==========================================
# 5. DYNAMIC MAP LEGEND BUILDER
# ==========================================
def draw_legend(title, colors, labels):
    html = f"<div style='margin-bottom: 5px;'><b> MAP INDEX: {title}</b><br><div style='display: flex; flex-direction: row; margin-top: 5px; flex-wrap: wrap;'>"
    for c, l in zip(colors, labels):
        html += f"<div style='display:flex; align-items:center; margin-right:15px; margin-bottom:5px;'><div style='background-color:{c}; width:30px; height:15px; border:1px solid #333; margin-right:5px;'></div><span style='font-size:13px;'>{l}</span></div>"
    html += "</div></div>"
    st.markdown(html, unsafe_allow_html=True)

# ==========================================
# 6. MAIN MAP RENDERING & EXPORT SETUP
# ==========================================
try:
    center = study_area.geometry().centroid().getInfo()['coordinates']
    m = folium.Map(location=[center[1], center[0]], zoom_start=10, tiles="CartoDB positron")
except:
    m = folium.Map(location=[10.2789, 77.9339], zoom_start=9)

def add_ee_layer(ee_object, vis_params, name):
    map_id = ee.Image(ee_object).getMapId(vis_params)
    folium.raster_layers.TileLayer(tiles=map_id['tile_fetcher'].url_format, attr='GEE', name=name, overlay=True).add_to(m)

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
    labels = [f"<{v_min}°C", f"{v_min} - {round(v_min+step,1)}°C", f"{round(v_min+step,1)} - {round(v_min+step*2,1)}°C", f"{round(v_min+step*2,1)} - {round(v_min+step*3,1)}°C", f"{round(v_min+step*3,1)} - {v_max}°C", f">{v_max}°C"]
    draw_legend(f"High-Res Land Surface Temp (Dynamic Stretch: {v_min}°C to {v_max}°C)", colors, labels)
    add_ee_layer(lst_current, {'min': v_min, 'max': v_max, 'palette': colors}, "LST Heatmap")

elif "NDWI" in analysis_type:
    active_image = ndwi_current
    export_scale = 10
    export_name = f"NDWI_{target_year}_{selected_display.replace(' ', '_')}"
    v_min, v_max = round(avg_ndwi - 0.2, 2), round(avg_ndwi + 0.2, 2)
    step = round((v_max - v_min) / 5, 2)
    colors = ['#d73027', '#fc8d59', '#fee08b', '#d9ef8b', '#91cf60', '#1a9850']
    labels = [f"<{v_min}", f"{v_min} to {round(v_min+step,2)}", f"{round(v_min+step,2)} to {round(v_min+step*2,2)}", f"{round(v_min+step*2,2)} to {round(v_min+step*3,2)}", f"{round(v_min+step*3,2)} to {v_max}", f">{v_max}"]
    draw_legend(f"Moisture NDWI (Dynamic Stretch around {avg_ndwi})", colors, labels)
    add_ee_layer(ndwi_current, {'min': v_min, 'max': v_max, 'palette': colors}, "Moisture Index")

elif "NDVI" in analysis_type:
    active_image = ndvi_current
    export_scale = 10
    export_name = f"NDVI_{target_year}_{selected_display.replace(' ', '_')}"
    v_min, v_max = round(avg_ndvi - 0.2, 2), round(avg_ndvi + 0.3, 2)
    step = round((v_max - v_min) / 5, 2)
    colors = ['#d73027', '#fc8d59', '#fee08b', '#d9ef8b', '#91cf60', '#1a9850']
    labels = [f"<{v_min} (Barren)", f"{v_min} to {round(v_min+step,2)}", f"{round(v_min+step,2)} to {round(v_min+step*2,2)}", f"{round(v_min+step*2,2)} to {round(v_min+step*3,2)}", f"{round(v_min+step*3,2)} to {v_max}", f">{v_max} (Dense Crop)"]
    draw_legend(f"Crop Health NDVI (Dynamic Stretch around {avg_ndvi})", colors, labels)
    add_ee_layer(ndvi_current, {'min': v_min, 'max': v_max, 'palette': colors}, "Crop Health (NDVI)")

elif "Rainfall" in analysis_type:
    active_image = rain_current
    export_scale = 5500
    export_name = f"Rainfall_{target_year}_{selected_display.replace(' ', '_')}"
    r_min = max(0, int(avg_rain - 300))
    r_max = int(avg_rain + 300)
    step = (r_max - r_min) // 5
    colors = ['#ffffcc', '#c7e9b4', '#7fcdbb', '#41b6c4', '#2c7fb8', '#253494']
    labels = [f"<{r_min} mm", f"{r_min}-{r_min+step} mm", f"{r_min+step}-{r_min+step*2} mm", f"{r_min+step*2}-{r_min+step*3} mm", f"{r_min+step*3}-{r_max} mm", f">{r_max} mm"]
    draw_legend(f"Annual Precipitation (Dynamic Scale for {selected_display})", colors, labels)
    add_ee_layer(rain_current, {'min': r_min, 'max': r_max, 'palette': colors}, "Annual Rainfall")

elif "Mineral" in analysis_type:
    active_image = mineral_composite
    export_scale = 30
    export_name = f"Multiband_Mineral_Composite_{target_year}_{selected_display.replace(' ', '_')}"
    colors = ['#ff0000', '#00ff00', '#0000ff', '#ffffff']
    labels = ['Iron Oxides (B4/B2)', 'Ferrous Minerals (B6/B5)', 'Clay / Hydrothermal (B6/B7)', 'Mixed Mineralogy']
    draw_legend("Landsat 8 Multiband Mineral Composite (RGB)", colors, labels)
    add_ee_layer(mineral_composite, {'bands': ['Iron', 'Ferrous', 'Clay'], 'min': 0.5, 'max': 2.0}, "Mineral Composite")

elif "Land Use" in analysis_type:
    active_image = lulc_image
    export_scale = 10
    export_name = f"LULC_ESA10m_{selected_display.replace(' ', '_')}"
    vis_lulc = {'bands': ['Map'], 'min': 10, 'max': 100, 'palette': ['006400', 'ffbb22', 'ffff4c', 'f096ff', 'fa0000', 'b4b4b4', 'f0f0f0', '0064c8', '0096a0', '00cf75', 'fae6a0']}
    colors = ['#006400', '#ffbb22', '#ffff4c', '#f096ff', '#fa0000', '#b4b4b4', '#f0f0f0', '#0064c8', '#0096a0', '#00cf75', '#fae6a0']
    labels = ['Trees/Forests', 'Shrubland', 'Grassland', 'Cropland (Net Sown Area)', 'Built-up (Urban)', 'Barren/Sparse Veg', 'Snow/Ice', 'Permanent Water', 'Herbaceous Wetland', 'Mangroves', 'Moss/Lichen']
    draw_legend("Land Use / Land Cover (ESA 10m Classification)", colors, labels)
    add_ee_layer(lulc_image, vis_lulc, "ESA WorldCover LULC")

else:
    active_image = lst_anomaly
    export_scale = 1000
    export_name = f"Heat_Anomaly_{target_year}_{selected_display.replace(' ', '_')}"
    colors = ['#313695', '#74add1', '#e0f3f8', '#fee090', '#f46d43', '#d73027']
    labels = ['Much Cooler (< -1.5°C)', 'Slightly Cooler', 'No Change', 'Slightly Hotter', 'Hotter', 'Much Hotter (> 1.5°C)']
    draw_legend("Year-Over-Year Heat Anomaly", colors, labels)
    add_ee_layer(lst_anomaly, {'min': -1.5, 'max': 1.5, 'palette': colors}, "Temp Change")

outline = ee.Image().byte().paint(featureCollection=study_area, color=1, width=3)
add_ee_layer(outline, {'palette': ['#000000']}, "Boundary")
st_folium(m, width=1200, height=500, returned_objects=[])

# ==========================================
# 7. BOTTOM SECTION: AI INTERPRETATION & DOWNLOADS
# ==========================================
st.markdown("---")
col_ai, col_down = st.columns([2, 1])

with col_ai:
    # THE UPGRADE: VISUAL RISK METER & DYNAMIC HEADER
    st.markdown(f"### Regional Verdict: <span style='color:{v_color};'>{v_icon} {total_interp}</span>", unsafe_allow_html=True)
    st.markdown(f"**Drought Risk Score: {risk_score} / 10**")
    
    meter_html = f"""
    <div style="width: 100%; background-color: #2b2b2b; border-radius: 8px; margin-bottom: 20px; border: 1px solid #444;">
        <div style="width: {risk_score * 10}%; height: 24px; background-color: {v_color}; border-radius: 8px; transition: width 0.5s;"></div>
    </div>
    """
    st.markdown(meter_html, unsafe_allow_html=True)

    if "LST" in analysis_type:
        st.info(f"**Layer Interpretation:** MODIS Land Surface Temperature (LST). The regional average is {avg_lst}°C.")
        if avg_lst >= 35: st.error("**🤖 AI Action Plan:** Critical thermal stress detected. Pivot to drought-resistant crops (Sorghum, Pearl Millet) for the next cycle.")
        else: st.success("**🤖 AI Action Plan:** Temperatures are within manageable agricultural ranges. Proceed with standard Kharif/Rabi cycle.")

    elif "NDWI" in analysis_type:
        st.info(f"**Layer Interpretation:** Sentinel-2 Normalized Difference Water Index (NDWI). The regional average is {avg_ndwi}.")
        if avg_ndwi < 0: st.error("**🤖 AI Action Plan:** Severe surface water deficit detected. Pause planting of water-intensive crops like Paddy or Sugarcane.")
        else: st.success("**🤖 AI Action Plan:** Good soil moisture index. Ideal conditions for major cash crops. Continue standard irrigation.")

    elif "NDVI" in analysis_type:
        st.info(f"**Layer Interpretation:** Sentinel-2 Normalized Difference Vegetation Index (NDVI). The regional average is {avg_ndvi}.")
        if avg_ndvi < 0.2: st.error("**🤖 AI Action Plan:** Critical biomass deficit. This indicates severe crop failure or post-harvest bare soil.")
        elif avg_ndvi < 0.4: st.warning("**🤖 AI Action Plan:** Moderate vegetation health. Apply targeted nitrogen fertilizers to boost canopy growth.")
        else: st.success("**🤖 AI Action Plan:** High biomass density. Crops are demonstrating excellent photosynthetic activity.")

    elif "Rainfall" in analysis_type:
        st.info(f"**Layer Interpretation:** CHIRPS daily precipitation data aggregated annually. Total regional rainfall is {avg_rain}mm.")
        if avg_rain < 600: st.error("**🤖 AI Action Plan:** Rainfall is dangerously low. Restrict agricultural groundwater usage to prevent aquifer depletion.")
        elif avg_rain > 1600: st.error("**🤖 AI Action Plan:** High flood risk detected. Ensure agricultural drainage channels are cleared.")
        else: st.success("**🤖 AI Action Plan:** Rainfall is sufficient to naturally recharge groundwater aquifers.")

    elif "Mineral" in analysis_type:
        st.info("**Layer Interpretation:** Landsat 8 Multiband RGB Composite (Iron/Ferrous/Clay).")
        st.warning("**🤖 AI Action Plan:** \n* **Blue Dominance (Clay):** Target these zones for high-yield borewell drilling. \n* **Red/Green Dominance (Oxides):** Implement targeted organic mulching and pH-balancing fertilizers.")

    elif "Land Use" in analysis_type:
        st.info("**Layer Interpretation:** High-resolution 10m ESA WorldCover classification.")
        st.warning("**🤖 AI Action Plan:** Use the yellow zones (Cropland / Net Sown Area) to mask the LST and NDWI arrays, ignoring the false heat signatures of Built-up areas.")

    else:
        st.info("**Layer Interpretation:** Temporal Heat Anomaly.")
        st.warning("**🤖 AI Action Plan:** Review the deep red zones on the map. These represent newly formed Urban Heat Islands or freshly degraded agricultural lands.")

with col_down:
    st.markdown("### 📥 Export Architecture")
    with st.expander("ℹ How Export Logic Works"):
        st.write("**Local Preview:** Generates a quick, compressed local link.\n**Cloud-to-Drive Sync:** Extracts true WGS84 10m–30m raw GeoTIFFs directly to Google Drive.")

    try:
        safe_local_scale = max(500, export_scale)
        local_url = active_image.getDownloadURL({'scale': safe_local_scale, 'crs': 'EPSG:4326', 'region': study_area.geometry()})
        st.link_button("⬇Fast Local Preview (Compressed)", local_url, use_container_width=True)
    except:
        st.error("Local download unavailable for this region size.")

    if st.button(f" Export High-Res GeoTIFF to Google Drive", type="primary", use_container_width=True):
        with st.spinner(f"Initiating Google Cloud backend task..."):
            try:
                task = ee.batch.Export.image.toDrive(image=active_image, description=export_name, folder='AgriGeo_Shield_Exports', fileNamePrefix=export_name, region=study_area.geometry().bounds(), scale=export_scale, crs='EPSG:4326', maxPixels=1e13)
                task.start()
                st.success(" **Task Started!** Data is rendering. Check your Google Drive.")
            except Exception as e:
                st.error(f"Failed to initiate export: {e}")

    csv_data = pd.DataFrame({"Region": [selected_display], "Year": [target_year], "Status": [total_interp], "Risk Score": [risk_score], "Avg_Rain_mm": [avg_rain], "Avg_LST": [avg_lst], "Avg_NDVI": [avg_ndvi]}).to_csv(index=False).encode('utf-8')
    st.download_button(label=" Download Regional Statistics (CSV)", data=csv_data, file_name=f"{selected_display}_report_{target_year}.csv", mime='text/csv', use_container_width=True)
