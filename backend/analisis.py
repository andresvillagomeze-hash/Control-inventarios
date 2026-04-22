"""
Funciones de análisis de rotación de inventario y series temporales.
"""

import pandas as pd
import plotly.graph_objects as go

from backend.constantes import (
    COLUMNAS_NUMERICAS,
    DARK, GREEN, GREEN_LIGHT, GRAY, GRAY_LIGHT, WHITE,
)


# ══════════════════════════════════════════════════════════════
# ██  PREPARACIÓN DE DATOS
# ══════════════════════════════════════════════════════════════

def preparar_df(df_raw: pd.DataFrame) -> pd.DataFrame:
    """Prepara el DataFrame descargado: limpia columnas internas, tipifica."""
    df = df_raw.copy()
    cols_drop = [c for c in ["id", "created_at"] if c in df.columns]
    df = df.drop(columns=cols_drop)
    if "fecha" in df.columns:
        df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
    for col in COLUMNAS_NUMERICAS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
            
    # Único cambio: Hacer que 'item' sea una combinación de su nombre original y tamaño.
    # Esto asegura que todo el dashboard analice el SKU específico y no agregados genéricos.
    if "item" in df.columns and "tamanio" in df.columns:
        df["tamanio_str"] = df["tamanio"].fillna("").astype(str).str.strip()
        df["item"] = df.apply(
            lambda r: f"{r['item']} ({r['tamanio_str']})" if r["tamanio_str"] and r["tamanio_str"] != "None" else r["item"], 
            axis=1
        )
        
    return df


# ══════════════════════════════════════════════════════════════
# ██  CLASIFICACIÓN DE PRODUCTOS
# ══════════════════════════════════════════════════════════════

def clasificar_productos(df: pd.DataFrame, umbral_cv: float = 0.15,
                          umbral_std: float = 1.0, dias_desabasto: int = 3
                          ) -> pd.DataFrame:
    """
    Clasifica cada producto (item) en:
    - 🌟 Estrella: coeficiente de variación > umbral_cv
    - 🚨 Desabastecido: inventario = 0 en las últimas N fechas
    - ⚠️ Estancado: inventario > 0 pero std ≈ 0
    """
    col_inv = "inventario_cd_en_unidades"
    if col_inv not in df.columns or "item" not in df.columns:
        return pd.DataFrame()

    # Agrupar por item
    stats = df.groupby("item")[col_inv].agg(
        ["mean", "std", "min", "max", "count"]
    ).reset_index()
    stats.columns = ["item", "inv_promedio", "inv_std", "inv_min", "inv_max", "registros"]

    # Coeficiente de variación
    stats["cv"] = stats.apply(
        lambda r: r["inv_std"] / r["inv_promedio"] if r["inv_promedio"] > 0 else 0,
        axis=1,
    )

    # Últimas N fechas para desabasto
    fechas_unicas = sorted(df["fecha"].dropna().unique())
    if len(fechas_unicas) >= dias_desabasto:
        ultimas_fechas = fechas_unicas[-dias_desabasto:]
    else:
        ultimas_fechas = fechas_unicas

    df_reciente = df[df["fecha"].isin(ultimas_fechas)]
    inv_reciente = df_reciente.groupby("item")[col_inv].mean().reset_index()
    inv_reciente.columns = ["item", "inv_reciente"]
    stats = stats.merge(inv_reciente, on="item", how="left")
    stats["inv_reciente"] = stats["inv_reciente"].fillna(0)

    # Último inventario
    if len(fechas_unicas) > 0:
        df_ultimo = df[df["fecha"] == fechas_unicas[-1]]
        inv_ultimo = df_ultimo.groupby("item")[col_inv].sum().reset_index()
        inv_ultimo.columns = ["item", "inv_ultimo"]
        stats = stats.merge(inv_ultimo, on="item", how="left")
        stats["inv_ultimo"] = stats["inv_ultimo"].fillna(0)
    else:
        stats["inv_ultimo"] = 0

    # Clasificación
    def clasificar(row):
        if row["inv_reciente"] == 0 and row["registros"] >= dias_desabasto:
            return "🚨 Desabastecido"
        if row["inv_promedio"] > 0 and row["inv_std"] <= umbral_std:
            return "⚠️ Estancado"
        if row["cv"] > umbral_cv and row["inv_promedio"] > 0:
            return "🌟 Estrella"
        return "📦 Normal"

    stats["clasificacion_rotacion"] = stats.apply(clasificar, axis=1)

    # Agregar info de clasificación y sub_clasificación
    for col in ["clasificacion", "sub_clasificacion", "clase_de_mercaderia"]:
        if col in df.columns:
            info = df.groupby("item")[col].first().reset_index()
            stats = stats.merge(info, on="item", how="left")

    return stats.sort_values("cv", ascending=False).reset_index(drop=True)


# ══════════════════════════════════════════════════════════════
# ██  SERIES TEMPORALES
# ══════════════════════════════════════════════════════════════

def serie_temporal_item(df: pd.DataFrame, item: str) -> pd.DataFrame:
    """Devuelve la serie temporal de inventario para un item específico."""
    col_inv = "inventario_cd_en_unidades"
    df_item = df[df["item"] == item].copy()
    if df_item.empty:
        return df_item
    serie = df_item.groupby("fecha")[col_inv].sum().reset_index()
    serie = serie.sort_values("fecha")
    return serie


def serie_temporal_agrupada(df: pd.DataFrame, col_grupo: str, valor: str) -> pd.DataFrame:
    """Serie temporal agregada por categoría o subcategoría."""
    col_inv = "inventario_cd_en_unidades"
    df_filtrado = df[df[col_grupo] == valor].copy()
    if df_filtrado.empty:
        return df_filtrado
    serie = df_filtrado.groupby("fecha")[col_inv].sum().reset_index()
    serie = serie.sort_values("fecha")
    return serie


# ══════════════════════════════════════════════════════════════
# ██  CONSUMO MENSUAL
# ══════════════════════════════════════════════════════════════

def calcular_consumo_mensual(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calcula las unidades consumidas por producto en el período.

    La lógica suma las caídas diarias de inventario entre lecturas consecutivas:
    consumo = Σ max(0, inv[t-1] − inv[t])  para cada par de días consecutivos.

    Retorna DataFrame con columnas:
    - Producto: nombre del item (ya incluye tamaño)
    - Código de Barras Padre
    - Unidades Consumidas
    - Cajas Consumidas
    """
    col_inv = "inventario_cd_en_unidades"
    if col_inv not in df.columns or "item" not in df.columns or "fecha" not in df.columns:
        return pd.DataFrame()

    # Obtener código de barras padre y unidades_de_manejo por producto
    info_cols = {}
    if "codigo_de_barras_padre" in df.columns:
        info_cols["codigo_de_barras_padre"] = df.groupby("item")["codigo_de_barras_padre"].first()
    if "unidades_de_manejo" in df.columns:
        info_cols["unidades_de_manejo"] = df.groupby("item")["unidades_de_manejo"].first()

    # Calcular consumo: sumar las caídas diarias de inventario
    resultados = []
    for item_name, grupo in df.groupby("item"):
        serie = grupo.groupby("fecha")[col_inv].sum().sort_index()
        # Consumo = suma de decrementos entre días consecutivos
        diffs = serie.diff()
        consumo = abs(diffs[diffs < 0].sum())  # suma de caídas (valores negativos → positivos)
        resultados.append({"item": item_name, "consumo_unidades": consumo})

    df_consumo = pd.DataFrame(resultados)

    if df_consumo.empty:
        return pd.DataFrame()

    # Agregar código de barras padre
    if "codigo_de_barras_padre" in info_cols:
        df_consumo = df_consumo.merge(
            info_cols["codigo_de_barras_padre"].reset_index(),
            on="item", how="left",
        )
    else:
        df_consumo["codigo_de_barras_padre"] = ""

    # Calcular cajas consumidas usando unidades_de_manejo como factor de conversión
    if "unidades_de_manejo" in info_cols:
        df_consumo = df_consumo.merge(
            info_cols["unidades_de_manejo"].reset_index(),
            on="item", how="left",
        )
        df_consumo["consumo_cajas"] = df_consumo.apply(
            lambda r: round(r["consumo_unidades"] / r["unidades_de_manejo"], 2)
            if pd.notna(r["unidades_de_manejo"]) and r["unidades_de_manejo"] > 0
            else 0,
            axis=1,
        )
    else:
        df_consumo["consumo_cajas"] = 0

    # Formatear salida con las 4 columnas solicitadas
    df_export = pd.DataFrame({
        "Producto": df_consumo["item"],
        "Código de Barras Padre": df_consumo["codigo_de_barras_padre"],
        "Unidades Consumidas": df_consumo["consumo_unidades"],
        "Cajas Consumidas": df_consumo["consumo_cajas"],
    })

    return df_export.sort_values("Unidades Consumidas", ascending=False).reset_index(drop=True)


# ══════════════════════════════════════════════════════════════
# ██  PLOTLY THEME
# ══════════════════════════════════════════════════════════════

def plotly_layout(fig, title: str = ""):
    """Aplica el tema de marca a cualquier figura Plotly."""
    fig.update_layout(
        title=dict(text=title, font=dict(color=WHITE, size=18)),
        paper_bgcolor=DARK,
        plot_bgcolor=GRAY,
        font=dict(color=WHITE, family="Inter, sans-serif"),
        xaxis=dict(gridcolor=GRAY_LIGHT, linecolor=GREEN),
        yaxis=dict(gridcolor=GRAY_LIGHT, linecolor=GREEN),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color=WHITE)),
        margin=dict(l=40, r=40, t=60, b=40),
    )
    return fig
