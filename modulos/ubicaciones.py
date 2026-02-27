import streamlit as st
import pandas as pd

def render_ubicaciones(supabase):
    st.header("📍 Control de Inventario de Lotes")

    # --- 1. OBTENER DATOS (De la VISTA para el estatus y de la TABLA para edición) ---
    try:
        # Usamos la VISTA para mostrar la información con estatus calculado
        res_vista = supabase.table("vista_estatus_lotes").select("*").order("etapa").order("manzana").order("lote").execute()
        df = pd.DataFrame(res_vista.data)
        
        # Creamos una columna visual para el selector y la tabla
        if not df.empty:
            df['display'] = df.apply(lambda x: f"E{x['etapa']}-M{x['manzana']}-L{x['lote']}", axis=1)
    except Exception as e:
        st.error(f"Error al cargar datos: {e}")
        return

    # --- 2. MÉTRICAS RÁPIDAS ---
    if not df.empty:
        col_m1, col_m2, col_m3 = st.columns(3)
        col_m1.metric("Total Lotes", len(df))
        # El estatus ahora viene de la lógica de la Vista
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
                # Insertamos solo en la tabla física 'ubicaciones'
                data = {
                    "manzana": int(manzana), 
                    "lote": int(lote), 
                    "etapa": int(etapa),
                    "precio": precio, # Nombre corregido
                    "enganche_req": enganche # Nombre corregido
                    # Nota: Ya no enviamos 'estatus'
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
            lote_sel_ref = st.selectbox("Selecciona un lote para modificar", df['display'].tolist())
            datos_lote = df[df['display'] == lote_sel_ref].iloc[0]

            with st.form("form_edicion"):
                st.info(f"Editando valores para: **{lote_sel_ref}**")
                st.write(f"Estatus actual: `{datos_lote['estatus_actual']}`")
                
                col_e1, col_e2 = st.columns(2)
                nuevo_precio = col_e1.number_input("Ajustar Precio ($)", value=float(datos_lote['precio_lista']), step=1000.0)
                nuevo_enganche = col_e2.number_input("Ajustar Enganche ($)", value=float(datos_lote['enganche_req']), step=1000.0)
                
                st.caption("Nota: El estatus se actualiza automáticamente basado en los pagos registrados.")

                col_btn1, col_btn2 = st.columns([1, 1])
                
                if col_btn1.form_submit_button("💾 Guardar Cambios"):
                    update_data = {
                        "precio": nuevo_precio,
                        "enganche_req": nuevo_enganche
                    }
                    supabase.table("ubicaciones").update(update_data).eq("id", int(datos_lote['ubicacion_id'])).execute()
                    st.success("¡Datos actualizados correctamente!")
                    st.rerun()
                
                if col_btn2.form_submit_button("🗑️ Eliminar Lote"):
                    try:
                        # Intentamos borrar de la tabla física
                        supabase.table("ubicaciones").delete().eq("id", int(datos_lote['ubicacion_id'])).execute()
                        st.warning("El registro ha sido eliminado.")
                        st.rerun()
                    except:
                        st.error("No se puede borrar: asegúrate de que no existan ventas o pagos ligados.")
        else:
            st.info("No hay lotes registrados para editar.")

    # --- 4. TABLA DE GESTIÓN ---
    if not df.empty:
        st.subheader("📋 Inventario Actual (Vista Dinámica)")
        
        busqueda = st.text_input("🔍 Filtrar por referencia (ej: E1-M2)")
        df_view = df[df['display'].str.contains(busqueda, case=False, na=False)] if busqueda else df

        st.dataframe(
            df_view[["display", "etapa", "precio_lista", "enganche_req", "estatus_actual"]],
            column_config={
                "display": "Ref. Lote",
                "etapa": "Etapa",
                "precio_lista": st.column_config.NumberColumn("Precio Lista", format="$%,.2f"),
                "enganche_req": st.column_config.NumberColumn("Enganche Req.", format="$%,.2f"),
                "estatus_actual": "Estado (Calculado)"
            },
            use_container_width=True,
            hide_index=True
        )
