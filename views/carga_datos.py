"""
Pestaña 3: Carga de archivos Excel de existencias diarias.
"""

import streamlit as st
import pandas as pd

from backend.constantes import GREEN_LIGHT, NOMBRE_TABLA
from backend.database import insertar_datos, obtener_fechas_cargadas, cargar_tabla
from backend.limpieza import limpiar_dataframe
from backend.analisis import preparar_df


def render(df_raw):
    """Renderiza la pestaña de carga de datos."""
    st.markdown("#### 📤 Cargar archivos de existencias diarias")
    st.caption("Sube archivos Excel (.xlsx) con el formato estándar de inventarios. "
               "Las primeras 4 filas del archivo se ignoran automáticamente.")

    # Mostrar fechas ya cargadas en formato heatmap estilo GitHub
    fechas_existentes = obtener_fechas_cargadas()
    if fechas_existentes:
        import datetime
        fecha_inicio = st.session_state.get("fecha_inicio", datetime.date.today().replace(day=1))
        fecha_fin = st.session_state.get("fecha_fin", datetime.date.today())
        
        hoy = datetime.date.today()
        current_month_start = fecha_inicio.replace(day=1)
        end_month_start = fecha_fin.replace(day=1)

        months_blocks = []
        
        while current_month_start <= end_month_start:
            meses = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
            nombre_mes = meses[current_month_start.month - 1]
            year = current_month_start.year
            
            # Encontrar fin del mes actual
            next_month_start = current_month_start.replace(day=28) + datetime.timedelta(days=4)
            next_month_start = next_month_start.replace(day=1)
            this_month_end = next_month_start - datetime.timedelta(days=1)
            
            cal_start = current_month_start - datetime.timedelta(days=current_month_start.weekday())
            cal_end = this_month_end + datetime.timedelta(days=6 - this_month_end.weekday())
            
            weeks_html = []
            current = cal_start
            while current <= cal_end:
                current_week = []
                for _ in range(7):
                    if current.month != current_month_start.month:
                        color_class = "day-empty"
                        title = ""
                    else:
                        date_str = current.strftime("%Y-%m-%d")
                        if current > hoy:
                            color_class = "day-future"
                            title = f"{date_str} (Futuro)"
                        elif date_str in fechas_existentes:
                            color_class = "day-loaded"
                            title = f"{date_str} (Cargado)"
                        elif current == hoy:
                            color_class = "day-process"
                            title = f"{date_str} (En proceso)"
                        else:
                            color_class = "day-missed"
                            title = f"{date_str} (Falta)"
                    current_week.append(f'<div class="github-day {color_class}" title="{title}"></div>')
                    current += datetime.timedelta(days=1)
                weeks_html.append(f'<div class="github-week">{"".join(current_week)}</div>')
            
            month_html = f"""
<div class="month-block">
    <div class="month-label">{nombre_mes} {year}</div>
    <div class="month-grid">
        {"".join(weeks_html)}
    </div>
</div>
"""
            months_blocks.append(month_html)
            
            current_month_start = next_month_start

        html = f"""
<style>
.github-calendar-wrapper {{
display: flex;
flex-direction: column;
gap: 12px;
background: #1b1b1e;
padding: 20px;
border-radius: 8px;
border: 1px solid #3a3a3e;
margin-bottom: 16px;
box-shadow: 0 4px 15px rgba(0,0,0,0.3);
}}
.github-calendar-inner {{
display: flex;
flex-direction: row;
gap: 28px;
flex-wrap: wrap;
}}
.month-block {{
display: flex;
flex-direction: column;
gap: 8px;
}}
.month-label {{
font-size: 13px;
color: #8b949e;
font-weight: 500;
}}
.month-grid {{
display: flex;
flex-direction: row;
gap: 6px;
}}
.github-week {{
display: flex;
flex-direction: column;
gap: 6px;
}}
.github-day {{
width: 18px;
height: 18px;
border-radius: 4px;
}}
.day-loaded {{ background-color: #39d353; }}
.day-process {{ background-color: #f39c12; }}
.day-missed {{ background-color: #f85149; }}
.day-future {{ background-color: #2a2a2e; }}
.day-empty {{ background-color: transparent; }}
.calendar-legend {{
display: flex;
gap: 16px;
font-size: 13px;
color: #8b949e;
align-items: center;
margin-top: 8px;
padding-top: 14px;
border-top: 1px solid #2a2a2e;
}}
.legend-item {{
display: flex;
align-items: center;
gap: 6px;
}}
</style>
<div class="github-calendar-wrapper">
<div style="font-size: 16px; color: #f0f0f0; font-weight: 600; margin-bottom: 2px;">
🗓️ Calendario de Cargas
</div>
<div style="font-size: 13px; color: #8b949e; margin-bottom: 8px;">
Mostrando el estado de subida de los meses en el rango seleccionado. Pasa el cursor sobre un día para ver su estado.
</div>
<div class="github-calendar-inner">
{"".join(months_blocks)}
</div>
<div class="calendar-legend">
<div class="legend-item"><div class="github-day day-loaded"></div> Cargado</div>
<div class="legend-item"><div class="github-day day-process"></div> En proceso</div>
<div class="legend-item"><div class="github-day day-missed"></div> Falta</div>
<div class="legend-item"><div class="github-day day-future"></div> Futuro</div>
</div>
</div>
"""
        st.markdown(html, unsafe_allow_html=True)

    st.markdown("---")

    # Uploader
    col_upload, col_preview = st.columns([1, 1])

    with col_upload:
        archivos = st.file_uploader(
            "Selecciona archivos Excel",
            type=["xlsx", "xls"],
            accept_multiple_files=True,
            key="uploader_tab3",
        )

        if archivos:
            st.markdown(f"**{len(archivos)} archivo(s) seleccionado(s)**")
            for a in archivos:
                st.caption(f"📄 {a.name}")

            if st.button("🚀 Procesar y subir a Supabase", type="primary", key="btn_subir"):
                # Obtener fechas ya cargadas para evitar duplicados
                fechas_existentes = obtener_fechas_cargadas()
                total_insertados = 0
                archivos_duplicados = []
                progress = st.progress(0)
                for idx, archivo in enumerate(archivos):
                    with st.spinner(f"Procesando {archivo.name}…"):
                        df_raw_upload = pd.read_excel(archivo, skiprows=4, dtype=str)
                        st.caption(f"📄 {archivo.name}: {len(df_raw_upload):,} filas leídas")

                        df_limpio = limpiar_dataframe(df_raw_upload)
                        st.caption(f"🧹 Limpieza: {len(df_limpio):,} filas válidas")

                        if df_limpio.empty:
                            st.warning(f"⚠️ {archivo.name} vacío tras limpieza.")
                            continue

                        # Verificar duplicados por fecha
                        if "fecha" in df_limpio.columns:
                            fecha_archivo = df_limpio["fecha"].iloc[0]
                            if fecha_archivo in fechas_existentes:
                                archivos_duplicados.append(
                                    f"⚠️ **{archivo.name}** — fecha {fecha_archivo} ya está en la base. Omitido."
                                )
                                continue

                        n = insertar_datos(df_limpio)
                        total_insertados += n
                    progress.progress((idx + 1) / len(archivos))

                # Mostrar resultados
                if archivos_duplicados:
                    for msg in archivos_duplicados:
                        st.warning(msg)

                if total_insertados > 0:
                    st.success(f"✅ {total_insertados:,} registros insertados. Recarga la página para ver los datos actualizados.")
                    cargar_tabla.clear()
                else:
                    if not archivos_duplicados:
                        st.warning("No se insertaron registros.")

    with col_preview:
        st.markdown("#### Vista previa")
        if archivos:
            preview_file = archivos[0]
            try:
                df_preview = pd.read_excel(preview_file, skiprows=4, nrows=10, dtype=str)
                df_preview.columns = (
                    df_preview.columns.str.strip().str.lower()
                    .str.replace(r"\s+", "_", regex=True)
                    .str.replace(r"[^\w]", "", regex=True)
                )
                st.dataframe(df_preview, use_container_width=True, hide_index=True)
                st.caption(f"Mostrando primeras 10 filas de {preview_file.name}")
            except Exception as e:
                st.error(f"Error al leer preview: {e}")
        else:
            st.caption("Sube un archivo para ver la vista previa.")

    # Tabla actualizada de la base
    if not df_raw.empty:
        st.markdown("---")
        st.markdown("#### 📊 Datos actuales en la base")
        mc1, mc2, mc3 = st.columns(3)
        mc1.metric("Registros totales", f"{len(df_raw):,}")
        mc2.metric("Productos únicos",
                   f"{df_raw['item'].nunique():,}" if "item" in df_raw.columns else "–")
        mc3.metric("Fechas cargadas",
                   f"{df_raw['fecha'].nunique()}" if "fecha" in df_raw.columns else "–")

        with st.expander("📋 Ver últimos registros", expanded=False):
            # Mostrar solo columnas solicitadas + fecha de carga
            cols_mostrar = ["fecha", "item", "tamanio", "inventario_cd_en_unidades", "inventario_cd_en_cajas"]
            cols_disponibles = [c for c in cols_mostrar if c in df_raw.columns]
            
            df_mostrar = df_raw[cols_disponibles].tail(50)
            st.dataframe(
                df_mostrar,
                use_container_width=True, hide_index=True,
            )
            
            # Botón de descarga
            csv = df_mostrar.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="⬇️ Descargar tabla (CSV)",
                data=csv,
                file_name="ultimos_registros.csv",
                mime="text/csv",
            )
