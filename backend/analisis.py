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

def clasificar_productos(df: pd.DataFrame, dias_estancado_umbral: int = 3,
                          dias_desabasto: int = 3) -> pd.DataFrame:
    """
    Clasifica cada producto (item) en:
    - 🌟 Estrella: CV > P50(cv)  Y  inventario promedio >= P50(inv_promedio)
    - 🚨 Desabastecido: inventario = 0 en las últimas N fechas consecutivas
    - ⚠️ Estancado: inventario > 0 y constante por más de K fechas consecutivas

    Los umbrales de CV e inventario mínimo se calculan automáticamente
    como el percentil 50 (mediana) de los datos.
    """
    col_inv = "inventario_cd_en_unidades"
    if col_inv not in df.columns or "item" not in df.columns:
        return pd.DataFrame()

    # 1. Calcular días consecutivos de desabasto y de stock estancado desde la fecha más reciente
    dias_consecutivos = []
    for item_name, grupo in df.groupby("item"):
        # Ordenamos descendente por fecha para ir desde el día más reciente hacia atrás
        grupo_sorted = grupo.sort_values("fecha", ascending=False)
        inventarios = grupo_sorted[col_inv].tolist()
        
        # Días consecutivos desabastecido (inventario es 0 o NaN)
        consec_desabasto = 0
        for val in inventarios:
            if pd.isna(val) or val == 0:
                consec_desabasto += 1
            else:
                break
                
        # Días consecutivos estancado (inventario tiene el mismo valor que el último registro)
        consec_estancado = 0
        if inventarios:
            latest_val = inventarios[0]
            if pd.notna(latest_val):
                for val in inventarios:
                    if pd.notna(val) and val == latest_val:
                        consec_estancado += 1
                    else:
                        break
        
        dias_consecutivos.append({
            "item": item_name,
            "dias_desabasto": consec_desabasto,
            "dias_estancado": consec_estancado
        })
        
    df_consec = pd.DataFrame(dias_consecutivos)

    # 2. Agrupar por item para estadísticas básicas
    stats = df.groupby("item")[col_inv].agg(
        ["mean", "std", "min", "max", "count"]
    ).reset_index()
    stats.columns = ["item", "inv_promedio", "inv_std", "inv_min", "inv_max", "registros"]

    # Coeficiente de variación
    stats["cv"] = stats.apply(
        lambda r: r["inv_std"] / r["inv_promedio"] if r["inv_promedio"] > 0 else 0,
        axis=1,
    )

    # Combinar con los días consecutivos calculados
    if not df_consec.empty:
        stats = stats.merge(df_consec, on="item", how="left")
    else:
        stats["dias_desabasto"] = 0
        stats["dias_estancado"] = 0
    stats["dias_desabasto"] = stats["dias_desabasto"].fillna(0).astype(int)
    stats["dias_estancado"] = stats["dias_estancado"].fillna(0).astype(int)

    # ── Calcular umbrales automáticos (mediana) ──
    umbral_cv = stats["cv"].quantile(0.50)
    umbral_inv_min = stats["inv_promedio"].quantile(0.50)
    _cv_p90 = round(umbral_cv, 4)
    _inv_p90 = round(umbral_inv_min, 2)

    # Últimas N fechas para desabasto (como soporte)
    fechas_unicas = sorted(df["fecha"].dropna().unique())
    if len(fechas_unicas) >= dias_desabasto:
        ultimas_fechas = fechas_unicas[-dias_desabasto:]
    else:
        ultimas_fechas = fechas_unicas

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
        if row["dias_desabasto"] >= dias_desabasto and row["registros"] >= dias_desabasto:
            return "🚨 Desabastecido"
        if row["inv_ultimo"] > 0 and row["dias_estancado"] > dias_estancado_umbral:
            return "⚠️ Estancado"
        if row["cv"] > umbral_cv and row["inv_promedio"] >= umbral_inv_min:
            return "🌟 Estrella"
        return "📦 Normal"

    stats["clasificacion_rotacion"] = stats.apply(clasificar, axis=1)

    # Agregar info de clasificación y sub_clasificación
    for col in ["clasificacion", "sub_clasificacion", "clase_de_mercaderia"]:
        if col in df.columns:
            info = df.groupby("item")[col].first().reset_index()
            stats = stats.merge(info, on="item", how="left")

    result = stats.sort_values("cv", ascending=False).reset_index(drop=True)
    result.attrs["umbral_cv_p90"] = _cv_p90
    result.attrs["umbral_inv_min_p90"] = _inv_p90
    return result


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
