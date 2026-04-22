"""
Pestaña 2: Análisis por Producto / Categoría / Subcategoría.
"""

import streamlit as st
import plotly.graph_objects as go

from backend.constantes import GREEN, GREEN_LIGHT, COLUMNAS_ESQUEMA
from backend.analisis import (
    preparar_df, clasificar_productos,
    serie_temporal_item, serie_temporal_agrupada,
    plotly_layout,
)


def render(df_raw):
    """Renderiza la pestaña de análisis por producto."""
    if df_raw.empty:
        st.info("📭 No hay datos. Ve a la pestaña **📤 Carga de Datos** para subir archivos Excel.")
        return

    df = preparar_df(df_raw)
    col_inv = "inventario_cd_en_unidades"

    st.markdown("#### 🔎 Filtros de búsqueda")
    f1, f2, f3 = st.columns(3)

    # Filtro de categoría
    categorias = (
        ["Todas"] + sorted(df["clasificacion"].dropna().unique().tolist())
        if "clasificacion" in df.columns else ["Todas"]
    )
    with f1:
        cat_sel = st.selectbox("📁 Categoría", categorias, key="cat_sel")

    # Filtro de subcategoría (cascada)
    if cat_sel != "Todas" and "sub_clasificacion" in df.columns:
        subcats = ["Todas"] + sorted(
            df[df["clasificacion"] == cat_sel]["sub_clasificacion"].dropna().unique().tolist()
        )
    else:
        subcats = (
            ["Todas"] + sorted(df["sub_clasificacion"].dropna().unique().tolist())
            if "sub_clasificacion" in df.columns else ["Todas"]
        )
    with f2:
        subcat_sel = st.selectbox("📂 Subcategoría", subcats, key="subcat_sel")

    # Filtro de producto (cascada)
    df_filtrado = df.copy()
    if cat_sel != "Todas" and "clasificacion" in df.columns:
        df_filtrado = df_filtrado[df_filtrado["clasificacion"] == cat_sel]
    if subcat_sel != "Todas" and "sub_clasificacion" in df.columns:
        df_filtrado = df_filtrado[df_filtrado["sub_clasificacion"] == subcat_sel]

    items_disponibles = (
        sorted(df_filtrado["item"].dropna().unique().tolist())
        if "item" in df.columns else []
    )
    with f3:
        item_sel = st.selectbox(
            "🏷️ Producto",
            ["Todos"] + items_disponibles,
            key="item_sel",
        )

    st.markdown("---")

    # ── Gráfica temporal ──
    if item_sel != "Todos":
        serie = serie_temporal_item(df, item_sel)
        titulo = f"Inventario de {item_sel}"
    elif subcat_sel != "Todas":
        serie = serie_temporal_agrupada(df, "sub_clasificacion", subcat_sel)
        titulo = f"Inventario total — {subcat_sel}"
    elif cat_sel != "Todas":
        serie = serie_temporal_agrupada(df, "clasificacion", cat_sel)
        titulo = f"Inventario total — {cat_sel}"
    else:
        serie = df.groupby("fecha")[col_inv].sum().reset_index().sort_values("fecha")
        titulo = "Inventario total — Todos los productos"

    if not serie.empty:
        fig_line = go.Figure()
        fig_line.add_trace(go.Scatter(
            x=serie["fecha"],
            y=serie[col_inv],
            mode="lines+markers",
            name="Inventario",
            line=dict(color=GREEN, width=3),
            marker=dict(size=6, color=GREEN_LIGHT),
            fill="tozeroy",
            fillcolor="rgba(98, 178, 47, 0.1)",
        ))
        fig_line = plotly_layout(fig_line, titulo)
        fig_line.update_xaxes(title_text="Fecha")
        fig_line.update_yaxes(title_text="Unidades")
        st.plotly_chart(fig_line, use_container_width=True)

        # ── Métricas ──
        inv_values = serie[col_inv]
        mc1, mc2, mc3, mc4, mc5 = st.columns(5)
        mc1.metric("Promedio", f"{inv_values.mean():,.0f}")
        mc2.metric("Máximo", f"{inv_values.max():,.0f}")
        mc3.metric("Mínimo", f"{inv_values.min():,.0f}")
        mc4.metric("Días en 0", f"{(inv_values == 0).sum()}")
        mc5.metric("Tendencia",
                   "📈 Subiendo" if len(inv_values) > 1 and inv_values.iloc[-1] > inv_values.iloc[0]
                   else "📉 Bajando" if len(inv_values) > 1 and inv_values.iloc[-1] < inv_values.iloc[0]
                   else "➡️ Estable")

        # ── Tabla de detalle si es un producto
        if item_sel != "Todos":
            st.markdown("---")
            with st.expander("📋 Ver datos detallados", expanded=False):
                df_detalle = df_filtrado[df_filtrado["item"] == item_sel].sort_values("fecha", ascending=False)
                cols_show = [c for c in COLUMNAS_ESQUEMA if c in df_detalle.columns]
                st.dataframe(df_detalle[cols_show], use_container_width=True, hide_index=True)
    else:
        st.warning("⚠️ No hay datos para la selección actual.")

    # ── Top productos si hay categoría seleccionada ──
    if cat_sel != "Todas" and item_sel == "Todos":
        st.markdown("---")
        st.markdown("#### 🏆 Top productos en esta selección")
        stats_filtro = clasificar_productos(df_filtrado)
        if not stats_filtro.empty:
            display_cols = ["item", "clasificacion_rotacion", "inv_promedio", "cv", "inv_ultimo"]
            display_cols = [c for c in display_cols if c in stats_filtro.columns]
            st.dataframe(
                stats_filtro[display_cols].head(15),
                use_container_width=True, hide_index=True,
            )
