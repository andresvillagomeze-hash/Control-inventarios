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
    """Verifica si las nuevas tablas existen."""
    try:
        supabase.table("productos").select("codigo_de_barras_padre").limit(1).execute()
        supabase.table("inventario_diario").select("fecha").limit(1).execute()
        return True
    except Exception as e:
        st.error(f"❌ No se encontraron las tablas nuevas: {e}")
        return False


# ── Lectura ──────────────────────────────────────────────────

@st.cache_data(ttl=300)
def obtener_rango_fechas() -> tuple:
    """Consulta ligera: obtiene solo la fecha mínima y máxima de la tabla de hechos."""
    try:
        res_min = (
            supabase.table("inventario_diario")
            .select("fecha")
            .order("fecha", desc=False)
            .limit(1)
            .execute()
        )
        res_max = (
            supabase.table("inventario_diario")
            .select("fecha")
            .order("fecha", desc=True)
            .limit(1)
            .execute()
        )
        fecha_min = res_min.data[0]["fecha"] if res_min.data else None
        fecha_max = res_max.data[0]["fecha"] if res_max.data else None
        return fecha_min, fecha_max
    except Exception:
        return None, None


@st.cache_data(ttl=300)
def cargar_tabla(fecha_inicio: str = None, fecha_fin: str = None) -> pd.DataFrame:
    """Carga registros haciendo JOIN en Pandas de productos + inventario_diario."""
    # 1. Cargar catálogo de productos (como son ~77, se trae de golpe)
    try:
        res_prod = supabase.table("productos").select("*").execute()
        df_productos = pd.DataFrame(res_prod.data)
    except Exception:
        return pd.DataFrame()
        
    if df_productos.empty:
        return pd.DataFrame()

    # 2. Cargar hechos de inventario diario con paginación
    all_data = []
    page_size = 1000
    offset = 0
    while True:
        query = supabase.table("inventario_diario").select("*")
        if fecha_inicio:
            query = query.gte("fecha", fecha_inicio)
        if fecha_fin:
            query = query.lte("fecha", fecha_fin)
        response = query.range(offset, offset + page_size - 1).execute()
        
        if not response.data:
            break
        all_data.extend(response.data)
        if len(response.data) < page_size:
            break  # última página
        offset += page_size
        
    df_inventario = pd.DataFrame(all_data)
    if df_inventario.empty:
        return pd.DataFrame()
        
    # 3. Merge local
    df_merged = pd.merge(
        df_inventario,
        df_productos,
        on="codigo_de_barras_padre",
        how="left"
    )
    
    # Mantener el campo proveedor en None (por compatibilidad temporal si alguna vista lo usaba)
    if "proveedor" not in df_merged.columns:
        df_merged["proveedor"] = df_merged["marca"]
        
    return df_merged


# ── Inserción ────────────────────────────────────────────────

def insertar_datos(df: pd.DataFrame) -> int:
    """Inserta DataFrame separando en dimensiones y hechos."""
    if df.empty:
        return 0
        
    # 1. Insertar (UPSERT) en la tabla de productos
    cols_productos = [
        "codigo_de_barras_padre", "item", "marca", "clasificacion",
        "sub_clasificacion", "clase_de_mercaderia", "tamanio", "acabado",
        "unidades_de_manejo"
    ]
    df_productos = df[[c for c in cols_productos if c in df.columns]].copy()
    df_productos = df_productos.drop_duplicates(subset=["codigo_de_barras_padre"])
    
    registros_prod = df_productos.to_dict(orient="records")
    for rec in registros_prod:
        for k, v in rec.items():
            if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                rec[k] = None
    
    if registros_prod:
        supabase.table("productos").upsert(
            registros_prod, 
            on_conflict="codigo_de_barras_padre"
        ).execute()

    # 2. Insertar (UPSERT) en inventario_diario
    cols_inventario = [
        "fecha", "codigo_de_barras_padre", "inventario_cd_en_unidades",
        "inventario_cd_en_cajas", "transito"
    ]
    df_inventario = df[[c for c in cols_inventario if c in df.columns]].copy()
    
    # Agrupar por fecha y código de barras para evitar error de duplicados en el UPSERT
    # ("ON CONFLICT DO UPDATE command cannot affect row a second time")
    df_inventario = df_inventario.groupby(
        ["fecha", "codigo_de_barras_padre"], 
        as_index=False, 
        dropna=True
    ).sum(min_count=1)
    
    registros_inv = df_inventario.to_dict(orient="records")
    for rec in registros_inv:
        for k, v in rec.items():
            if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                rec[k] = None
                
    insertados = 0
    batch_size = 500
    for i in range(0, len(registros_inv), batch_size):
        batch = registros_inv[i : i + batch_size]
        # Upsert previene errores de duplicados de clave primaria (fecha, sku)
        supabase.table("inventario_diario").upsert(batch).execute()
        insertados += len(batch)
        
    return insertados


# ── Duplicados ───────────────────────────────────────────────

def obtener_fechas_cargadas() -> set:
    """Consulta las fechas únicas ya presentes en la tabla inventario_diario."""
    try:
        all_fechas = set()
        page_size = 1000
        offset = 0
        while True:
            response = (
                supabase.table("inventario_diario")
                .select("fecha")
                .range(offset, offset + page_size - 1)
                .execute()
            )
            if not response.data:
                break
            all_fechas.update(row["fecha"] for row in response.data if row.get("fecha"))
            if len(response.data) < page_size:
                break
            offset += page_size
        return all_fechas
    except Exception:
        pass
    return set()

def obtener_marcas() -> list:
    """Consulta las marcas únicas existentes en el catálogo de productos."""
    try:
        res = supabase.table("productos").select("marca").execute()
        if res.data:
            marcas = list({row["marca"] for row in res.data if row["marca"]})
            return sorted(marcas)
    except Exception:
        pass
    # Respaldo si falla la consulta
    from backend.constantes import MARCAS_EXISTENTES
    return MARCAS_EXISTENTES
