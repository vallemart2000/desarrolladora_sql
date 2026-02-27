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
        col_m1.metric("Total Lotes", len(df))
        col_m2.metric("Disponibles", len(df[df['estatus'] == 'Disponible']))
        # Sumamos el valor del inventario total
        valor_total = df['precio_lista'].sum()
        col_m3.metric("Valor Inventario", f"${valor_total:,.2f}")
        st.markdown("---")

    # --- 3. PESTAÑAS: REGISTRO VS EDICIÓN ---
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
                    "precio_lista": precio, 
                    "enganche_requerido": enganche, 
                    "estatus": "Disponible"
                }
                supabase.table("ubicaciones").insert(data).execute()
                st.success("✅ ¡Lote registrado con éxito!")
                st.rerun()

    with tab2:
        if not df.empty:
            st.subheader("Modificar registro existente")
            # Selector para buscar el lote a editar
            lote_sel_ref = st.selectbox("Selecciona un lote para modificar", df['ubicacion_display'].tolist())
            datos_lote = df[df['ubicacion_display'] == lote_sel_ref].iloc[0]

            with st.form("form_edicion"):
                st.info(f"Editando valores para: **{lote_sel_ref}**")
                col_e1, col_e2 = st.columns(2)
                # Cargamos los valores actuales por defecto
                nuevo_precio = col_e1.number_input("Ajustar Precio ($)", value=float(datos_lote['precio_lista']), step=1000.0)
                nuevo_enganche = col_e2.number_input("Ajustar Enganche ($)", value=float(datos_lote['enganche_requerido']), step=1000.0)
                
                # Permite cambiar el estatus manualmente si hubo error
                nuevo_estatus = st.selectbox("Cambiar Estatus", ["Disponible", "Apartado", "Vendido"], 
                                           index=["Disponible", "Apartado", "Vendido"].index(datos_lote['estatus']))

                col_btn1, col_btn2 = st.columns([1, 1])
                
                if col_btn1.form_submit_button("💾 Guardar Cambios"):
                    update_data = {
                        "precio_lista": nuevo_precio,
                        "enganche_requerido": nuevo_enganche,
                        "estatus": nuevo_estatus
                    }
                    supabase.table("ubicaciones").update(update_data).eq("id", int(datos_lote['id'])).execute()
                    st.success("¡Datos actualizados correctamente!")
                    st.rerun()
                
                if col_btn2.form_submit_button("🗑️ Eliminar Lote"):
                    try:
                        supabase.table("ubicaciones").delete().eq("id", int(datos_lote['id'])).execute()
                        st.warning("El registro ha sido eliminado.")
                        st.rerun()
                    except:
                        st.error("No se puede borrar un lote que ya tiene una venta vinculada.")
        else:
            st.info("No hay lotes registrados para editar.")

    # --- 4. TABLA DE GESTIÓN CON FORMATO PROFESIONAL ---
    if not df.empty:
        st.subheader("📋 Inventario Actual")
        
        busqueda = st.text_input("🔍 Filtrar tabla por referencia (ej: M01)")
        df_view = df[df['ubicacion_display'].str.contains(busqueda, case=False, na=False)] if busqueda else df

        # Aplicamos el formato de moneda con separador de miles y $
        st.dataframe(
            df_view[["ubicacion_display", "etapa", "precio_lista", "enganche_requerido", "estatus"]],
            column_config={
                "ubicacion_display": "Ref. Lote",
                "etapa": "Etapa",
                "precio_lista": st.column_config.NumberColumn("Precio Lista", format="$%,.2f"),
                "enganche_requerido": st.column_config.NumberColumn("Enganche Requerido", format="$%,.2f"),
                "estatus": "Estado Actual"
            },
            use_container_width=True,
            hide_index=True
        )
