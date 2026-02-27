import streamlit as st
import pandas as pd

def render_ubicaciones(supabase):
    st.title("📍 Gestión de Inventario (Ubicaciones)")

    # --- CARGA DE DATOS DESDE SQL ---
    res = supabase.table("ubicaciones").select("*").order("id").execute()
    df_u = pd.DataFrame(res.data)

    tab_lista, tab_nuevo, tab_editar = st.tabs(["📋 Inventario Actual", "➕ Agregar Lote", "✏️ Editar Ubicación"])

    # --- PESTAÑA 1: LISTA ---
    with tab_lista:
        st.subheader("Control de Lotes y Disponibilidad")
        if df_u.empty:
            st.info("No hay lotes registrados.")
        else:
            ocultar_vendidos = st.toggle("Ocultar ubicaciones vendidas", value=True)
            
            df_mostrar = df_u.copy()
            if ocultar_vendidos:
                df_mostrar = df_mostrar[df_mostrar["estatus"] != "Vendido"]

            st.dataframe(
                df_mostrar,
                column_config={
                    "id": st.column_config.NumberColumn("ID", format="%d"),
                    "manzana": "Mz",
                    "lote": "Lt",
                    "ubicacion": "Ubicación",
                    "precio_lista": st.column_config.NumberColumn("Precio Lista", format="$ %.2f"),
                    "enganche_req": st.column_config.NumberColumn("Enganche Req.", format="$ %.2f"),
                    "estatus": st.column_config.SelectboxColumn("Estatus", options=["Disponible", "Vendido", "Apartado", "Bloqueado"])
                },
                use_container_width=True,
                hide_index=True
            )

    # --- PESTAÑA 2: NUEVO LOTE ---
    with tab_nuevo:
        st.subheader("Registrar Nueva Ubicación en SQL")
        with st.form("form_nueva_ub"):
            c_top1, c_top2 = st.columns(2)
            f_mz = c_top1.number_input("Número de Manzana", min_value=1, step=1, value=1)
            f_lt = c_top2.number_input("Número de Lote", min_value=1, step=1, value=1)
            f_fase = c_top1.selectbox("Fase/Etapa", ["Etapa 1", "Etapa 2", "Etapa 3", "Club"])
            
            c_bot1, c_bot2 = st.columns(2)
            f_pre = c_bot1.number_input("Precio de Lista ($)", min_value=0.0, step=1000.0)
            f_eng = c_bot2.number_input("Enganche Requerido para Contrato ($)", min_value=0.0, step=500.0)
            
            nombre_generado = f"M{int(f_mz):02d}-L{int(f_lt):02d}"
            
            st.markdown("---")
            if st.form_submit_button("💾 Guardar en Supabase", type="primary"):
                # Verificamos si ya existe el nombre en la base de datos
                check = supabase.table("ubicaciones").select("id").eq("ubicacion", nombre_generado).execute()
                
                if check.data:
                    st.error(f"❌ La ubicación {nombre_generado} ya existe.")
                else:
                    nueva_ub = {
                        "manzana": int(f_mz),
                        "lote": int(f_lt),
                        "ubicacion": nombre_generado,
                        "fase": f_fase,
                        "precio_lista": f_pre,
                        "enganche_req": f_eng,
                        "estatus": "Disponible"
                    }
                    supabase.table("ubicaciones").insert(nueva_ub).execute()
                    st.success(f"✅ {nombre_generado} registrado con éxito.")
                    st.rerun()

    # --- PESTAÑA 3: EDITAR REGISTRO ---
    with tab_editar:
        st.subheader("Modificar o Eliminar Ubicación")
        if df_u.empty:
            st.info("No hay ubicaciones para editar.")
        else:
            opciones_ubi = df_u["ubicacion"].tolist()
            ubi_sel = st.selectbox("Seleccione la ubicación a gestionar", ["--"] + opciones_ubi)

            if ubi_sel != "--":
                datos_actuales = df_u[df_u["ubicacion"] == ubi_sel].iloc[0]
                row_id = datos_actuales['id']

                with st.form("form_edit_ub"):
                    st.write(f"🔢 ID Base de Datos: **{row_id}** | Ubicación: **{ubi_sel}**")
                    ce1, ce2 = st.columns(2)
                    
                    opciones_fase = ["Etapa 1", "Etapa 2", "Etapa 3", "Club"]
                    e_fase = ce1.selectbox("Fase/Etapa", opciones_fase, 
                                         index=opciones_fase.index(datos_actuales["fase"]) if datos_actuales["fase"] in opciones_fase else 0)
                    
                    opciones_estatus = ["Disponible", "Vendido", "Apartado", "Bloqueado"]
                    e_estatus = ce2.selectbox("Estatus", opciones_estatus,
                                            index=opciones_estatus.index(datos_actuales["estatus"]))
                    
                    e_pre = ce1.number_input("Precio de Lista ($)", min_value=0.0, value=float(datos_actuales["precio_lista"]))
                    e_eng = ce2.number_input("Enganche Requerido ($)", min_value=0.0, value=float(datos_actuales["enganche_req"]))

                    st.markdown("---")
                    st.warning("⚠️ **Zona de Peligro**")
                    confirmar_borrado = st.checkbox(f"Confirmar eliminación definitiva de {ubi_sel}")
                    
                    c_save, c_del = st.columns(2)
                    
                    if c_save.form_submit_button("💾 Actualizar SQL", type="primary"):
                        update_data = {
                            "fase": e_fase,
                            "estatus": e_estatus,
                            "precio_lista": e_pre,
                            "enganche_req": e_eng
                        }
                        supabase.table("ubicaciones").update(update_data).eq("id", row_id).execute()
                        st.success(f"✅ {ubi_sel} actualizada en la nube.")
                        st.rerun()
                    
                    if c_del.form_submit_button("🗑️ Eliminar de la Base de Datos"):
                        if confirmar_borrado:
                            supabase.table("ubicaciones").delete().eq("id", row_id).execute()
                            st.error(f"🗑️ {ubi_sel} eliminada permanentemente.")
                            st.rerun()
                        else:
                            st.warning("❌ Debes marcar la casilla de confirmación.")
