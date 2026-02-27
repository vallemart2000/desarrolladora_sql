import streamlit as st
import pandas as pd

def render_ubicaciones(supabase):
    st.header("📍 Control de Inventario de Lotes (Numérico)")

    # --- 1. OBTENER DATOS ---
    try:
        response = supabase.table("ubicaciones").select("*").order("etapa").order("manzana").order("lote").execute()
        df = pd.DataFrame(response.data)
    except Exception as e:
        st.error(f"Error de conexión: {e}")
        return

    # --- 2. MÉTRICAS RÁPIDAS ---
    if not df.empty:
        col_m1, col_m2, col_m3 = st.columns(3)
        with col_m1:
            st.metric("Total Lotes", len(df))
        with col_m2:
            disponibles = len(df[df['estatus'] == 'Disponible'])
            st.metric("Disponibles", disponibles)
        with col_m3:
            valor_total = df['precio_lista'].sum()
            st.metric("Valor Inventario", f"${valor_total:,.2f}")
        st.markdown("---")

    # --- 3. FORMULARIO DE CAPTURA ESTRICTAMENTE NUMÉRICO ---
    with st.expander("➕ Registrar Nuevo Lote"):
        with st.form("form_nueva_ubicacion", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            etapa = c1.number_input("Etapa #", min_value=1, step=1, value=1)
            manzana = c2.number_input("Manzana #", min_value=1, step=1, value=1)
            lote = c3.number_input("Lote #", min_value=1, step=1, value=1)
            
            c4, c5 = st.columns(2)
            precio = c4.number_input("Precio de Lista ($)", min_value=0.0, step=1000.0, format="%.2f")
            enganche = c5.number_input("Enganche Requerido ($)", min_value=0.0, step=1000.0, format="%.2f")

            if st.form_submit_button("Guardar en Base de Datos"):
                nuevo_lote = {
                    "manzana": int(manzana), 
                    "lote": int(lote), 
                    "etapa": int(etapa),
                    "precio_lista": precio, 
                    "enganche_requerido": enganche,
                    "estatus": "Disponible"
                }
                try:
                    supabase.table("ubicaciones").insert(nuevo_lote).execute()
                    st.success(f"✅ Lote registrado con éxito!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al insertar: {e}")

    # --- 4. TABLA DE GESTIÓN ---
    if not df.empty:
        st.subheader("📋 Inventario Detallado")
        
        busqueda = st.text_input("🔍 Buscar por Referencia (ej: M01 o L15)")
        df_filtered = df.copy()
        
        if busqueda:
            df_filtered = df[df['ubicacion_display'].str.contains(busqueda, case=False, na=False)]

        df_display = df_filtered.rename(columns={
            "ubicacion_display": "Ref.",
            "etapa": "Etapa",
            "precio_lista": "Precio Lista",
            "enganche_requerido": "Enganche",
            "estatus": "Estado"
        })

        # --- CORRECCIÓN AQUÍ: Quitamos StatusColumn y usamos SelectboxColumn ---
        st.dataframe(
            df_display[["Ref.", "Etapa", "Precio Lista", "Enganche", "Estado"]],
            column_config={
                "Precio Lista": st.column_config.NumberColumn(format="$%.2f"),
                "Enganche": st.column_config.NumberColumn(format="$%.2f"),
                "Estado": st.column_config.SelectboxColumn(
                    options=["Disponible", "Vendido", "Apartado"]
                )
            },
            use_container_width=True,
            hide_index=True
        )

        # --- 5. SECCIÓN DE ACCIONES ---
        st.markdown("---")
        with st.expander("🛠️ Acciones Avanzadas"):
            col_sel, col_btn = st.columns([3, 1])
            lote_a_borrar = col_sel.selectbox(
                "Seleccionar lote para eliminar", 
                df['ubicacion_display'].unique().tolist()
            )
            
            if col_btn.button("🗑️ Eliminar Lote", type="primary"):
                try:
                    supabase.table("ubicaciones").delete().eq("ubicacion_display", lote_a_borrar).execute()
                    st.warning(f"Lote {lote_a_borrar} eliminado.")
                    st.rerun()
                except Exception:
                    st.error("Protección: No puedes borrar un lote con ventas asociadas.")
    else:
        st.info("No hay lotes en el inventario.")
