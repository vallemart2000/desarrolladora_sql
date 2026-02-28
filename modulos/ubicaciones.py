import streamlit as st
import pandas as pd

def render_ubicaciones(supabase):
    st.title("📍 Control de Inventario de Lotes")

    # --- 1. OBTENER DATOS DE LA VISTA ---
    try:
        res_vista = supabase.table("vista_estatus_lotes").select("*").order("etapa").order("manzana").order("lote").execute()
        df = pd.DataFrame(res_vista.data)
        
        if not df.empty:
            df['Referencia'] = df.apply(lambda x: f"M{int(x['manzana']):02d}-L{int(x['lote']):02d}", axis=1)
            df['display_selector'] = df.apply(lambda x: f"E{x['etapa']}-M{x['manzana']}-L{x['lote']}", axis=1)
    except Exception as e:
        st.error(f"Error al cargar datos: {e}")
        return

    # --- 2. MÉTRICAS PERSONALIZADAS (DISEÑO LIMPIO) ---
    if not df.empty:
        total_lotes = len(df)
        disponibles = len(df[df['estatus_actual'] == 'DISPONIBLE'])
        valor_total = df['precio_lista'].sum()

        st.markdown(f"""
        <div style="
            display: grid; 
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); 
            gap: 20px; 
            margin-bottom: 25px;
        ">
            <div style="background-color: #1E1E1E; padding: 20px; border-radius: 12px; border: 1px solid #333; border-left: 5px solid #FF4B4B;">
                <p style="color: #808495; margin: 0; font-size: 0.8rem; font-weight: 700; text-transform: uppercase;">Total Lotes</p>
                <h2 style="color: #FFFFFF; margin: 5px 0 0 0;">{total_lotes}</h2>
            </div>
            <div style="background-color: #1E1E1E; padding: 20px; border-radius: 12px; border: 1px solid #333; border-left: 5px solid #00C853;">
                <p style="color: #808495; margin: 0; font-size: 0.8rem; font-weight: 700; text-transform: uppercase;">Disponibles</p>
                <h2 style="color: #FFFFFF; margin: 5px 0 0 0;">{disponibles}</h2>
            </div>
            <div style="background-color: #1E1E1E; padding: 20px; border-radius: 12px; border: 1px solid #333; border-left: 5px solid #29B6F6;">
                <p style="color: #808495; margin: 0; font-size: 0.8rem; font-weight: 700; text-transform: uppercase;">Valor Inventario</p>
                <h2 style="color: #FFFFFF; margin: 5px 0 0 0;">$ {valor_total:,.2f}</h2>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # --- 3. PESTAÑAS ---
    tab1, tab2, tab3 = st.tabs(["📋 Ver Inventario", "➕ Registrar Nuevo", "✏️ Editar / Borrar"])

    with tab1:
        if not df.empty:
            busqueda = st.text_input("🔍 Buscar por Referencia (ej: M01)", placeholder="Escriba para filtrar...")
            df_view = df[df['Referencia'].str.contains(busqueda, case=False, na=False)] if busqueda else df

            st.dataframe(
                df_view[["Referencia", "manzana", "lote", "etapa", "precio_lista", "enganche_req", "estatus_actual"]],
                column_config={
                    "Referencia": "Referencia",
                    "manzana": "Mz",
                    "lote": "Lt",
                    "etapa": "Etapa",
                    "precio_lista": st.column_config.NumberColumn("Precio Lista", format="$%,.2f"),
                    "enganche_req": st.column_config.NumberColumn("Enganche Req.", format="$%,.2f"),
                    "estatus_actual": st.column_config.TextColumn("Estatus")
                },
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("No hay lotes en el inventario.")

    with tab2:
        with st.form("form_nueva_ubicacion", clear_on_submit=True):
            st.subheader("Captura de nuevo lote")
            c1, c2, c3 = st.columns(3)
            etapa = c1.number_input("Etapa #", min_value=1, step=1)
            manzana = c2.number_input("Manzana #", min_value=1, step=1)
            lote = c3.number_input("Lote #", min_value=1, step=1)
            
            c4, c5 = st.columns(2)
            precio = c4.number_input("Precio de Lista ($)", min_value=0.0, step=1000.0)
            enganche = c5.number_input("Enganche Requerido ($)", min_value=0.0, step=1000.0)

            if st.form_submit_button("✅ Guardar Lote", type="primary", use_container_width=True):
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

    with tab3:
        if not df.empty:
            st.subheader("Modificar registro existente")
            lote_sel_ref = st.selectbox("Selecciona lote para editar", ["--"] + df['display_selector'].tolist())
            
            if lote_sel_ref != "--":
                datos_lote = df[df['display_selector'] == lote_sel_ref].iloc[0]

                with st.form("form_edicion"):
                    st.warning(f"Editando: **{datos_lote['Referencia']}**")
                    col_e1, col_e2 = st.columns(2)
                    nuevo_precio = col_e1.number_input("Precio ($)", value=float(datos_lote['precio_lista']), step=1000.0)
                    nuevo_enganche = col_e2.number_input("Enganche ($)", value=float(datos_lote['enganche_req']), step=1000.0)
                    
                    c_btn1, c_btn2 = st.columns(2)
                    if c_btn1.form_submit_button("💾 Guardar Cambios", use_container_width=True):
                        update_data = {"precio": nuevo_precio, "enganche_req": nuevo_enganche}
                        supabase.table("ubicaciones").update(update_data).eq("id", int(datos_lote['ubicacion_id'])).execute()
                        st.success("¡Actualizado!")
                        st.rerun()
                    
                    if c_btn2.form_submit_button("🗑️ Eliminar Lote", use_container_width=True):
                        try:
                            supabase.table("ubicaciones").delete().eq("id", int(datos_lote['ubicacion_id'])).execute()
                            st.rerun()
                        except:
                            st.error("No se puede eliminar un lote con historial de ventas.")
