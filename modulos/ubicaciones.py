import streamlit as st
import pandas as pd

def render_ubicaciones(supabase):
    st.header("📍 Control de Inventario de Lotes")

    # --- 1. OBTENER DATOS DE LA VISTA ---
    try:
        res_vista = supabase.table("vista_estatus_lotes").select("*").order("etapa").order("manzana").order("lote").execute()
        df = pd.DataFrame(res_vista.data)
        
        if not df.empty:
            # Nueva lógica de referencia: Manzana y Lote con ceros a la izquierda (opcional)
            # Ejemplo: M01-L05
            df['Referencia'] = df.apply(lambda x: f"M{int(x['manzana']):02d}-L{int(x['lote']):02d}", axis=1)
            
            # Para el selector de edición seguimos usando Etapa para evitar confusiones si hay M01-L01 en varias etapas
            df['display_selector'] = df.apply(lambda x: f"E{x['etapa']}-M{x['manzana']}-L{x['lote']}", axis=1)
    except Exception as e:
        st.error(f"Error al cargar datos: {e}")
        return

    # --- 2. MÉTRICAS RÁPIDAS ---
    if not df.empty:
        col_m1, col_m2, col_m3 = st.columns(3)
        col_m1.metric("Total Lotes", len(df))
        disponibles = len(df[df['estatus_actual'] == 'DISPONIBLE'])
        col_m2.metric("Disponibles", disponibles)
        valor_total = df['precio_lista'].sum()
        col_m3.metric("Valor Inventario", f"${valor_total:,.2f}")
        st.markdown("---")

    # --- 3. PESTAÑAS ---
    tab1, tab2 = st.tabs(["➕ Registrar Nuevo", "✏️ Editar / Borrar"])

    with tab1:
        with st.form("form_nueva_ubicacion", clear_on_submit=True):
            st.subheader("Captura de nuevo lote")
            c1, c2, c3 = st.columns(3)
            etapa = c1.number_input("Etapa #", min_value=1, step=1)
            manzana = c2.number_input("Manzana #", min_value=1, step=1)
            lote = c3.number_input("Lote #", min_value=1, step=1)
            
            c4, c5 = st.columns(2)
            precio = c4.number_input("Precio de Lista ($)", min_value=0.0, step=1000.0)
            enganche = c5.number_input("Enganche Requerido ($)", min_value=0.0, step=1000.0)

            if st.form_submit_button("Guardar Lote"):
                data = {
                    "manzana": int(manzana), 
                    "lote": int(lote), 
                    "etapa": int(etapa),
                    "precio": precio,
                    "enganche_req": enganche
                }
                try:
                    supabase.table("ubicaciones").insert(data).execute()
                    st.success("✅ ¡Lote registrado con éxito!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al guardar: {e}")

    with tab2:
        if not df.empty:
            st.subheader("Modificar registro existente")
            # Usamos el display con Etapa solo aquí para asegurar que editas el correcto
            lote_sel_ref = st.selectbox("Selecciona lote para editar (Ref. completa)", df['display_selector'].tolist())
            datos_lote = df[df['display_selector'] == lote_sel_ref].iloc[0]

            with st.form("form_edicion"):
                st.info(f"Editando: **{datos_lote['Referencia']}** (Etapa {datos_lote['etapa']})")
                
                col_e1, col_e2 = st.columns(2)
                nuevo_precio = col_e1.number_input("Precio ($)", value=float(datos_lote['precio_lista']), step=1000.0)
                nuevo_enganche = col_e2.number_input("Enganche ($)", value=float(datos_lote['enganche_req']), step=1000.0)
                
                if st.form_submit_button("💾 Guardar Cambios"):
                    update_data = {"precio": nuevo_precio, "enganche_req": nuevo_enganche}
                    supabase.table("ubicaciones").update(update_data).eq("id", int(datos_lote['ubicacion_id'])).execute()
                    st.success("¡Actualizado!")
                    st.rerun()
                
                if st.form_submit_button("🗑️ Eliminar Lote"):
                    try:
                        supabase.table("ubicaciones").delete().eq("id", int(datos_lote['ubicacion_id'])).execute()
                        st.rerun()
                    except:
                        st.error("No se puede eliminar un lote con historial.")
        else:
            st.info("No hay lotes registrados.")

    # --- 4. TABLA DE GESTIÓN (VISTA DINÁMICA ORDENADA) ---
    if not df.empty:
        st.subheader("📋 Inventario Actual")
        
        busqueda = st.text_input("🔍 Buscar por Referencia (ej: M01)")
        df_view = df[df['Referencia'].str.contains(busqueda, case=False, na=False)] if busqueda else df

        # Seleccionamos y renombramos columnas para cumplir tu requerimiento
        # Orden: Referencia, Mz, Lt, Etapa, Precio de Lista, Enganche Requerido, Estatus
        df_final = df_view[[
            "Referencia", "manzana", "lote", "etapa", "precio_lista", "enganche_req", "estatus_actual"
        ]]

        st.dataframe(
            df_final,
            column_config={
                "Referencia": "Referencia",
                "manzana": "Mz",
                "lote": "Lt",
                "etapa": "Etapa",
                "precio_lista": st.column_config.NumberColumn("Precio de Lista", format="$%,.2f"),
                "enganche_req": st.column_config.NumberColumn("Enganche Requerido", format="$%,.2f"),
                "estatus_actual": "Estatus"
            },
            use_container_width=True,
            hide_index=True
        )
