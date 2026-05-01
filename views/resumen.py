"""
Pestaña 1: Resumen de Rotación de Inventarios.
"""

from io import BytesIO

import streamlit as st
import pandas as pd
import plotly.express as px

from backend.constantes import GREEN, GREEN_LIGHT, RED, AMBER, WHITE
from backend.analisis import preparar_df, clasificar_productos, calcular_consumo_mensual, plotly_layout


def render(df_raw, umbral_cv, umbral_std, dias_desabasto, umbral_inv_min):
    """Renderiza la pestaña de resumen de rotación."""
    if df_raw.empty:
        st.info("📭 No hay datos. Ve a la pestaña **📤 Carga de Datos** para subir archivos Excel.")
        return

    df = preparar_df(df_raw)

    # ── Clasificar ──
    stats = clasificar_productos(df, umbral_cv, umbral_std, dias_desabasto, umbral_inv_min)

    if stats.empty:
        st.warning("⚠️ No se pudo clasificar. Verifica que existan las columnas 'item' e 'inventario_cd_en_unidades'.")
        return

    estrellas = stats[stats["clasificacion_rotacion"] == "🌟 Estrella"]
    desabastecidos = stats[stats["clasificacion_rotacion"] == "🚨 Desabastecido"]
    estancados = stats[stats["clasificacion_rotacion"] == "⚠️ Estancado"]

    # ── Métricas globales ──
    n_fechas = df["fecha"].nunique() if "fecha" in df.columns else 0
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Total Productos", f"{len(stats):,}")
    m2.metric("🌟 Estrella", f"{len(estrellas):,}")
    m3.metric("🚨 Desabastecidos", f"{len(desabastecidos):,}")
    m4.metric("⚠️ Estancados", f"{len(estancados):,}")
    m5.metric("📅 Días de datos", f"{n_fechas}")

    st.markdown("---")

    # ── Distribución por clasificación ──
    col_chart, col_summary = st.columns([1, 2])

    with col_chart:
        conteo = stats["clasificacion_rotacion"].value_counts().reset_index()
        conteo.columns = ["Clasificación", "Cantidad"]
        color_map = {
            "🌟 Estrella": GREEN,
            "🚨 Desabastecido": RED,
            "⚠️ Estancado": AMBER,
            "📦 Normal": "#636e72",
        }
        fig_pie = px.pie(
            conteo, names="Clasificación", values="Cantidad",
            color="Clasificación", color_discrete_map=color_map,
            hole=0.45,
        )
        fig_pie = plotly_layout(fig_pie, "Distribución de Productos")
        fig_pie.update_traces(
            textinfo="percent+value",
            textfont=dict(color=WHITE, size=13),
        )
        st.plotly_chart(fig_pie, use_container_width=True)

    with col_summary:
        st.markdown("#### 🌟 Top Productos Estrella")
        if not estrellas.empty:
            display_cols = ["item", "inv_promedio", "cv", "inv_ultimo"]
            if "clasificacion" in estrellas.columns:
                display_cols.insert(1, "clasificacion")
            top_estrellas = estrellas.head(10)[display_cols].copy()
            top_estrellas.columns = [c.replace("_", " ").title() for c in top_estrellas.columns]
            st.dataframe(top_estrellas, use_container_width=True, hide_index=True)
        else:
            st.caption("No hay productos estrella con los parámetros actuales.")

    # ── Tablas detalladas ──
    st.markdown("---")
    col_desab, col_estanc = st.columns(2)

    with col_desab:
        st.markdown(f"#### 🚨 Productos Desabastecidos ({len(desabastecidos)})")
        if not desabastecidos.empty:
            display_cols = ["item", "inv_promedio", "inv_ultimo", "registros"]
            if "clasificacion" in desabastecidos.columns:
                display_cols.insert(1, "clasificacion")
            st.dataframe(
                desabastecidos[display_cols].head(20),
                use_container_width=True, hide_index=True,
            )
        else:
            st.success("✅ No hay productos desabastecidos.")

    with col_estanc:
        st.markdown(f"#### ⚠️ Productos Estancados ({len(estancados)})")
        if not estancados.empty:
            display_cols = ["item", "inv_promedio", "inv_std", "inv_ultimo"]
            if "clasificacion" in estancados.columns:
                display_cols.insert(1, "clasificacion")
            st.dataframe(
                estancados[display_cols].head(20),
                use_container_width=True, hide_index=True,
            )
        else:
            st.success("✅ No hay productos estancados.")

    # ── Descarga de consumo mensual ──
    st.markdown("---")
    st.markdown("#### 📥 Descargar Consumo del Período")
    st.caption(
        "Genera un archivo Excel con las unidades y cajas consumidas de cada producto "
        "en el rango de fechas seleccionado."
    )

    df_consumo = calcular_consumo_mensual(df)

    if not df_consumo.empty:
        # Mostrar preview
        with st.expander("👀 Vista previa del reporte", expanded=False):
            st.dataframe(df_consumo.head(20), use_container_width=True, hide_index=True)
            st.caption(f"Mostrando 20 de {len(df_consumo)} productos.")

        # Generar Excel en memoria
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            df_consumo.to_excel(writer, index=False, sheet_name="Consumo Mensual")

            # Ajustar ancho de columnas
            ws = writer.sheets["Consumo Mensual"]
            for col_idx, col_name in enumerate(df_consumo.columns, 1):
                max_len = max(
                    len(str(col_name)),
                    df_consumo[col_name].astype(str).str.len().max() if len(df_consumo) > 0 else 0,
                )
                ws.column_dimensions[chr(64 + col_idx)].width = min(max_len + 4, 50)

        buffer.seek(0)

        st.download_button(
            label="⬇️ Descargar Excel de Consumo",
            data=buffer,
            file_name="consumo_mensual.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
        )
    else:
        st.info("No hay datos suficientes para calcular el consumo (se necesitan al menos 2 fechas).")
