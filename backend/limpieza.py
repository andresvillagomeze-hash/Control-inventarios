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
    if "fecha" in df.columns:
        # Intentar múltiples formatos para parsear correctamente
        # Priorizar formato dd/mm/yyyy (dayfirst) que es el estándar en México/LATAM
        raw_sample = df["fecha"].dropna().iloc[0] if df["fecha"].notna().any() else None

        if raw_sample is not None:
            # Si Excel ya lo convirtió a datetime, usarlo directamente
            if isinstance(raw_sample, pd.Timestamp):
                df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
            elif hasattr(raw_sample, 'year'):  # datetime.datetime nativo
                df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
            else:
                # Es string: parsear con dayfirst=True (formato dd/mm/yyyy)
                df["fecha"] = pd.to_datetime(
                    df["fecha"], errors="coerce", dayfirst=True
                )

            fecha_valida = df["fecha"].dropna().iloc[0] if df["fecha"].notna().any() else None
            if fecha_valida is not None:
                df["fecha"] = df["fecha"].fillna(fecha_valida)
                st.info(f"📅 Fecha detectada en el archivo: **{fecha_valida.strftime('%d/%m/%Y')}**")
                df["fecha"] = df["fecha"].dt.strftime("%Y-%m-%d")
            else:
                st.warning("⚠️ No se encontró ninguna fecha válida en el archivo.")
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

    # Mantener solo columnas esperadas
    columnas_presentes = [c for c in COLUMNAS_ESQUEMA if c in df.columns]
    df = df[columnas_presentes]

    return df.reset_index(drop=True)
