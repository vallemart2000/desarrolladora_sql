import streamlit as st
import pandas as pd

def render_ubicaciones(supabase):
    st.header("📍 Control de Inventario de Lotes")

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
            st.metric("Disponibles", disponibles, delta=f"{disponibles/len(df):.0%}")
        with col_m3:
            valor_total = df['precio_lista'].sum()
            st.metric("Valor Inventario", f"${valor_total:,.2f}")
        st.markdown("---")

    # --- 3. FORMULARIO DE CAPTURA ---
    with st.expander("➕ Registrar Nuevo Lote"):
        with st.form("form_nueva_ubicacion", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            etapa = c1.selectbox("Etapa", ["Etapa 1", "Etapa 2", "Etapa 3", "Etapa 4"])
            manzana = c2.text_input("Manzana")
            lote = c3.text_input("Lote")
            
            c4, c5 = st.columns(2)
            precio = c4.number_input("Precio de Lista", min_value=0.0, step=5000.0, format="%.2f")
            enganche = c5.number_input("Enganche Requerido", min_value=0.0, step=1000.0, format="%.2f")

            if st.form_submit_button("Guardar en Base de Datos"):
                if manzana and lote:
                    # El campo 'ubicacion_display' se genera solo en SQL, no lo mandamos
                    nuevo_lote = {
                        "manzana": manzana, "lote": lote, "etapa": etapa,
                        "precio_lista": precio, "enganche_requerido": enganche,
                        "estatus": "Disponible"
                    }
                    supabase.table("ubicaciones").insert(nuevo_lote).execute()
                    st.success("¡Lote guardado correctamente!")
                    st.rerun()
                else:
                    st.warning("Manzana y Lote son obligatorios.")

    # --- 4. TABLA DE GESTIÓN ---
    if not df.empty:
        st.subheader("📋 Inventario Detallado")
        
        # Filtro rápido
        busqueda = st.text_input("🔍 Buscar por Manzana o Lote (ej: M05 o L12)")
        df_filtered = df.copy()
        if busqueda:
            df_filtered = df[df['ubicacion_display'].str.contains(busqueda, case=False)]

        # Preparar visualización
        df_filtered = df_filtered.rename(columns={
            "ubicacion_display": "Ubicación",
            "etapa": "Etapa",
            "precio_lista": "Precio",
            "enganche_requerido": "Enganche",
            "estatus": "Estado"
        })

        # Mostrar tabla interactiva
        st.dataframe(
            df_filtered[["Ubicación", "Etapa", "Precio", "Enganche", "Estado"]],
            column_config={
                "Precio": st.column_config.NumberColumn(format="$%.2f"),
                "Enganche": st.column_config.NumberColumn(format="$%.2f"),
                "Estado": st.column_config.SelectboxColumn(options=["Disponible", "Vendido", "Apartado"])
            },
            use_container_width=True,
            hide_index=True
        )

        # --- 5. SECCIÓN DE ACCIONES (EDICIÓN/BORRADO) ---
        st.markdown("---")
        with st.expander("🛠️ Acciones Avanzadas"):
            col_sel, col_btn = st.columns([3, 1])
            lote_a_borrar = col_sel.selectbox("Seleccionar lote para eliminar", df['ubicacion_display'].tolist())
            if col_btn.button("🗑️ Eliminar Lote", type="primary"):
                try:
                    supabase.table("ubicaciones").delete().eq("ubicacion_display", lote_a_borrar).execute()
                    st.warning(f"Lote {lote_a_borrar} eliminado.")
                    st.rerun()
                except Exception:
                    st.error("No se puede eliminar un lote que ya tiene una venta asociada.")

    else:
        st.info("Aún no hay lotes. Usa el formulario de arriba para empezar.")
