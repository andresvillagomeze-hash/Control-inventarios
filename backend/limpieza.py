"""
Pipeline de limpieza de datos provenientes de archivos Excel.
"""

import streamlit as st
import pandas as pd

from backend.constantes import COLUMNAS_ESQUEMA, COLUMNAS_NUMERICAS, COLUMNAS_TEXTO


def limpiar_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Pipeline de limpieza para archivos Excel de inventario:
    1. Normaliza nombres de columnas (minúsculas, sin espacios).
    2. Rellena fechas faltantes con la fecha del día (cada archivo = 1 día).
    3. Aplica .strip() a columnas de texto.
    4. Convierte columnas numéricas a tipo numérico.
    5. Rellena tránsito con 0.
    """
    # Normalizar nombres de columnas
    df.columns = (
        df.columns.str.strip().str.lower()
        .str.replace(r"\s+", "_", regex=True)
        .str.replace(r"[^\w]", "", regex=True)
    )

    # Fecha: cada archivo = 1 día, rellenar vacíos con la fecha existente
    # IMPORTANTE: El formato del Excel SIEMPRE es YYYY-MM-DD (año-mes-día).
    # Forzamos conversión a string primero para evitar que Excel/openpyxl
    # auto-interprete la fecha con día/mes invertido.
    if "fecha" in df.columns:
        # Paso 1: Convertir TODO a string para neutralizar auto-parsing de Excel
        df["fecha"] = df["fecha"].astype(str).str.strip()

        # Si Excel convirtió a datetime nativo, el str() produce "YYYY-MM-DD HH:MM:SS"
        # Extraemos solo la parte de fecha (primeros 10 caracteres)
        df["fecha"] = df["fecha"].str[:10]

        # Reemplazar valores inválidos por NaN
        df["fecha"] = df["fecha"].replace(["NaT", "nan", "None", ""], pd.NA)

        # Paso 2: Parsear explícitamente con formato YYYY-MM-DD
        df["fecha"] = pd.to_datetime(
            df["fecha"], format="%Y-%m-%d", errors="coerce"
        )

        fecha_valida = df["fecha"].dropna().iloc[0] if df["fecha"].notna().any() else None
        if fecha_valida is not None:
            df["fecha"] = df["fecha"].fillna(fecha_valida)
            st.info(f"📅 Fecha detectada en el archivo: **{fecha_valida.strftime('%d/%m/%Y')}**")
            df["fecha"] = df["fecha"].dt.strftime("%Y-%m-%d")
        else:
            st.warning("⚠️ No se encontró ninguna fecha válida en el archivo.")

    # Strip a columnas de texto
    for col in COLUMNAS_TEXTO:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip().replace("nan", None)

    # Eliminar registros obsoletos
    if "clase_de_mercaderia" in df.columns:
        df = df[df["clase_de_mercaderia"] != "E-NO OBSOLETO NO RESURTIBLE"]

    # Convertir columnas numéricas
    for col in COLUMNAS_NUMERICAS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Rellenar tránsito con 0
    if "transito" in df.columns:
        df["transito"] = df["transito"].fillna(0)

    # Extraer la marca dinámicamente
    import re
    from backend.constantes import MARCAS_EXISTENTES
    if "item" in df.columns:
        patron = "|".join(re.escape(m) for m in MARCAS_EXISTENTES)
        df["marca"] = df["item"].str.extract(f"({patron})", flags=re.IGNORECASE, expand=False).str.upper()
        df["marca"] = df["marca"].fillna("OTRA")

    # Mantener solo columnas esperadas (agregamos 'marca')
    columnas_esperadas = COLUMNAS_ESQUEMA + ["marca"]
    columnas_presentes = [c for c in columnas_esperadas if c in df.columns]
    df = df[columnas_presentes]

    return df.reset_index(drop=True)
