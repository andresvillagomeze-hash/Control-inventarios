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

    # Mostrar fechas ya cargadas
    if not df_raw.empty:
        df_temp = preparar_df(df_raw)
        if "fecha" in df_temp.columns:
            fechas_cargadas = sorted(df_temp["fecha"].dropna().unique())
            fechas_str = [str(f)[:10] for f in fechas_cargadas]
            with st.expander(f"📅 Fechas ya cargadas ({len(fechas_str)})", expanded=False):
                chips = " · ".join(fechas_str[-30:])
                st.markdown(f"<p style='color:{GREEN_LIGHT}'>{chips}</p>", unsafe_allow_html=True)
                if len(fechas_str) > 30:
                    st.caption(f"… y {len(fechas_str) - 30} más")

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
