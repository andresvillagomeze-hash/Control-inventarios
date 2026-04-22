"""
Conexión a Supabase y operaciones CRUD.
"""

import math
import streamlit as st
import pandas as pd
from supabase import create_client, Client

from backend.constantes import NOMBRE_TABLA


# ── Conexión ─────────────────────────────────────────────────

@st.cache_resource
def init_supabase() -> Client:
    """Crea y cachea el cliente de Supabase usando los secrets de Streamlit."""
    url: str = st.secrets["SUPABASE_URL"]
    key: str = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)


supabase: Client = init_supabase()


# ── Verificar / crear tabla ──────────────────────────────────

def verificar_o_crear_tabla() -> bool:
    """Verifica si la tabla existe; intenta crearla vía RPC si no."""
    try:
        supabase.table(NOMBRE_TABLA).select("id").limit(1).execute()
        return True
    except Exception:
        try:
            supabase.rpc("crear_tabla_inventarios", {}).execute()
            st.success("✅ Tabla 'inventarios' creada exitosamente.")
            return True
        except Exception as e:
            st.error(f"❌ No se pudo crear la tabla: {e}")
            return False


# ── Lectura ──────────────────────────────────────────────────

@st.cache_data(ttl=300)
def cargar_tabla(nombre_tabla: str) -> pd.DataFrame:
    """Carga todos los registros de una tabla de Supabase."""
    response = supabase.table(nombre_tabla).select("*").execute()
    return pd.DataFrame(response.data)


# ── Inserción ────────────────────────────────────────────────

def insertar_datos(df: pd.DataFrame, nombre_tabla: str) -> int:
    """Inserta DataFrame en Supabase, limpiando NaN → None."""
    registros = df.to_dict(orient="records")
    for rec in registros:
        for k, v in rec.items():
            if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                rec[k] = None
    insertados = 0
    batch_size = 500
    for i in range(0, len(registros), batch_size):
        batch = registros[i : i + batch_size]
        supabase.table(nombre_tabla).insert(batch).execute()
        insertados += len(batch)
    return insertados


# ── Duplicados ───────────────────────────────────────────────

def obtener_fechas_cargadas() -> set:
    """Consulta las fechas únicas ya presentes en la tabla inventarios."""
    try:
        response = supabase.table(NOMBRE_TABLA).select("fecha").execute()
        if response.data:
            return set(row["fecha"] for row in response.data if row.get("fecha"))
    except Exception:
        pass
    return set()
