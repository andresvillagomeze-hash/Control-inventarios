"""
Dashboard de Inventarios · La Favorita
Entry point — orquesta la configuración, el tema y las pestañas.
"""

import streamlit as st
import pandas as pd
from backend.constantes import (
    DARK, GREEN, GREEN_LIGHT, GRAY, GRAY_LIGHT, WHITE,
)
from backend.database import verificar_o_crear_tabla, cargar_tabla
from backend.constantes import NOMBRE_TABLA

from views import resumen, analisis_producto, carga_datos


# ══════════════════════════════════════════════════════════════
# ██  CONFIGURACIÓN DE PÁGINA
# ══════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="Dashboard Inventarios · La Favorita",
    page_icon="📦",
    layout="wide",
)


# ══════════════════════════════════════════════════════════════
# ██  CSS PERSONALIZADO
# ══════════════════════════════════════════════════════════════

st.markdown(f"""
<style>
    /* ── Fondo general ─── */
    .stApp {{
        background-color: {DARK};
        color: {WHITE};
    }}

    /* ── Header ─── */
    .dashboard-header {{
        background: linear-gradient(135deg, {DARK} 0%, {GRAY} 100%);
        border-bottom: 3px solid {GREEN};
        padding: 1.5rem 2rem;
        margin: -1rem -1rem 1.5rem -1rem;
        border-radius: 0 0 12px 12px;
    }}
    .dashboard-header h1 {{
        color: {WHITE};
        font-size: 2rem;
        margin: 0;
    }}
    .dashboard-header span {{
        color: {GREEN};
    }}

    /* ── Tabs ─── */
    .stTabs [data-baseweb="tab-list"] {{
        gap: 8px;
        background-color: {GRAY};
        padding: 6px;
        border-radius: 12px;
    }}
    .stTabs [data-baseweb="tab"] {{
        background-color: transparent;
        color: {WHITE};
        border-radius: 8px;
        padding: 10px 24px;
        font-weight: 500;
    }}
    .stTabs [aria-selected="true"] {{
        background-color: {GREEN} !important;
        color: {DARK} !important;
        font-weight: 700;
    }}

    /* ── Metric cards ─── */
    div[data-testid="stMetric"] {{
        background: linear-gradient(145deg, {GRAY} 0%, {GRAY_LIGHT} 100%);
        border: 1px solid {GREEN}33;
        border-radius: 12px;
        padding: 1rem 1.2rem;
        box-shadow: 0 4px 15px rgba(0,0,0,0.3);
    }}
    div[data-testid="stMetric"] label {{
        color: {GREEN_LIGHT} !important;
        font-size: 0.85rem;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }}
    div[data-testid="stMetric"] [data-testid="stMetricValue"] {{
        color: {WHITE} !important;
        font-size: 1.8rem;
        font-weight: 700;
    }}

    /* ── Expanders ─── */
    .streamlit-expanderHeader {{
        background-color: {GRAY};
        border-radius: 8px;
        color: {WHITE};
    }}

    /* ── Sidebar ─── */
    section[data-testid="stSidebar"] {{
        background-color: {GRAY};
        border-right: 2px solid {GREEN}33;
    }}

    /* ── Dataframes ─── */
    .stDataFrame {{
        border-radius: 8px;
        overflow: hidden;
    }}

    /* ── Botones ─── */
    .stButton > button[kind="primary"] {{
        background-color: {GREEN};
        color: {DARK};
        font-weight: 700;
        border: none;
        border-radius: 8px;
    }}
    .stButton > button[kind="primary"]:hover {{
        background-color: {GREEN_LIGHT};
    }}

    /* ── Info / Success / Warning boxes ─── */
    .stAlert {{
        border-radius: 8px;
    }}

    /* ── Selectbox ─── */
    div[data-baseweb="select"] {{
        border-radius: 8px;
    }}

    /* ── Checkbox / Toggle / Radio ─── */
    input[type="checkbox"]:checked + div {{
        background-color: {GREEN} !important;
        border-color: {GREEN} !important;
    }}

    /* ── Progress bar ─── */
    .stProgress > div > div > div {{
        background-color: {GREEN} !important;
    }}

    /* ── File uploader ─── */
    section[data-testid="stFileUploader"] button {{
        color: {GREEN} !important;
        border-color: {GREEN} !important;
    }}
    section[data-testid="stFileUploader"] button:hover {{
        background-color: {GREEN}22 !important;
    }}

    /* ── Links y acentos globales ─── */
    a {{
        color: {GREEN_LIGHT} !important;
    }}

    /* ── Widget labels ─── */
    .stSlider label, .stSelectbox label, .stMultiSelect label,
    .stFileUploader label {{
        color: {WHITE} !important;
    }}

    /* ── Primary color override ─── */
    :root {{
        --primary-color: {GREEN};
    }}
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════
# ██  HEADER
# ══════════════════════════════════════════════════════════════

st.markdown(f"""
<div class="dashboard-header">
    <h1>📦 Dashboard de <span>Inventarios</span></h1>
    <p style="color: {GREEN_LIGHT}; margin: 0.3rem 0 0 0; font-size: 0.95rem;">
        Rotación de productos en punto de venta · La Favorita
    </p>
</div>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════
# ██  INICIALIZACIÓN
# ══════════════════════════════════════════════════════════════

tabla_lista = verificar_o_crear_tabla()

if not tabla_lista:
    st.stop()

df_raw = cargar_tabla(NOMBRE_TABLA)

# ── Sidebar: filtros y parámetros ─────────────────────────────
with st.sidebar:
    # ── Filtro de rango de fechas ──
    st.markdown("### 📅 Rango de fechas")

    import datetime

    hoy = datetime.date.today()
    inicio_mes = hoy.replace(day=1)

    # Determinar rango disponible en los datos
    if not df_raw.empty and "fecha" in df_raw.columns:
        fechas_db = pd.to_datetime(df_raw["fecha"], errors="coerce").dropna()
        fecha_min_db = fechas_db.min().date() if not fechas_db.empty else inicio_mes
        fecha_max_db = fechas_db.max().date() if not fechas_db.empty else hoy
    else:
        fecha_min_db = inicio_mes
        fecha_max_db = hoy

    fecha_inicio = st.date_input(
        "Desde",
        value=max(inicio_mes, fecha_min_db),
        min_value=fecha_min_db,
        max_value=fecha_max_db,
        key="fecha_inicio",
    )
    fecha_fin = st.date_input(
        "Hasta",
        value=fecha_max_db,
        min_value=fecha_min_db,
        max_value=fecha_max_db,
        key="fecha_fin",
    )

    st.markdown("---")

    # ── Parámetros de clasificación ──
    st.markdown("### ⚙️ Parámetros de clasificación")
    umbral_cv = st.slider(
        "Umbral Coef. Variación (Estrella)",
        min_value=0.05, max_value=1.0, value=0.15, step=0.05,
        help="Productos con CV mayor a este valor se consideran de alta rotación.",
    )
    umbral_std = st.slider(
        "Umbral Std (Estancado)",
        min_value=0.0, max_value=10.0, value=1.0, step=0.5,
        help="Productos con desviación estándar menor a este valor se consideran estancados.",
    )
    dias_desabasto = st.slider(
        "Días para desabasto",
        min_value=1, max_value=10, value=3,
        help="Un producto con inventario 0 en los últimos N días se marca como desabastecido.",
    )

# ── Filtrar datos por rango de fechas ─────────────────────────
if not df_raw.empty and "fecha" in df_raw.columns:
    df_filtrado_fecha = df_raw.copy()
    # Comparar como strings YYYY-MM-DD (mismo formato que la base)
    str_inicio = fecha_inicio.strftime("%Y-%m-%d")
    str_fin = fecha_fin.strftime("%Y-%m-%d")
    df_filtrado_fecha = df_filtrado_fecha[
        (df_filtrado_fecha["fecha"] >= str_inicio)
        & (df_filtrado_fecha["fecha"] <= str_fin)
    ]
else:
    df_filtrado_fecha = df_raw


# ══════════════════════════════════════════════════════════════
# ██  PESTAÑAS
# ══════════════════════════════════════════════════════════════

tab1, tab2, tab3 = st.tabs([
    "🏠 Resumen de Rotación",
    "🔍 Análisis por Producto",
    "📤 Carga de Datos",
])

with tab1:
    resumen.render(df_filtrado_fecha, umbral_cv, umbral_std, dias_desabasto)

with tab2:
    analisis_producto.render(df_filtrado_fecha)

with tab3:
    carga_datos.render(df_raw)  # Tab de carga siempre ve todos los datos
