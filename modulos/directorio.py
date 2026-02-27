import streamlit as st
import pandas as pd

def render_directorio(supabase):
    st.title("📇 Directorio General (SQL)")

    # --- CARGA DE DATOS ---
    res_cl = supabase.table("clientes").select("*").order("nombre").execute()
    df_cl = pd.DataFrame(res_cl.data)
    
    res_vd = supabase.table("vendedores").select("*").order("nombre").execute()
    df_vd = pd.DataFrame(res_vd.data)

    tab_clientes, tab_vendedores = st.tabs(["👥 Directorio de Clientes", "👔 Equipo de Vendedores"])

    # --- TABLA CLIENTES ---
    with tab_clientes:
        st.subheader("Gestión de Clientes")
        
        c1, c2 = st.columns(2)
        with c1.expander("➕ Registrar Nuevo Cliente"):
            with st.form("form_nuevo_cl"):
                f_nom = st.text_input("Nombre Completo *")
                f_tel = st.text_input("Teléfono")
                f_eml = st.text_input("Correo")
                if st.form_submit_button("💾 Guardar Cliente", type="primary"):
                    if not f_nom:
                        st.error("Nombre obligatorio.")
                    else:
                        nuevo = {
                            "nombre": f_nom.strip(), 
                            "telefono": f_tel.strip(), 
                            "correo": f_eml.strip()
                        }
                        supabase.table("clientes").insert(nuevo).execute()
                        st.success("✅ Cliente registrado en SQL.")
                        st.rerun()

        with c2.expander("✏️ Editar Cliente Existente"):
            if df_cl.empty:
                st.info("No hay clientes para editar.")
            else:
                cliente_sel = st.selectbox("Seleccione cliente", df_cl["nombre"].tolist(), key="edit_cl_select")
                datos_cl = df_cl[df_cl["nombre"] == cliente_sel].iloc[0]
                
                with st.form("form_edit_cl"):
                    e_nom = st.text_input("Nombre", value=datos_cl["nombre"])
                    e_tel = st.text_input("Teléfono", value=str(datos_cl["telefono"]))
                    e_eml = st.text_input("Correo", value=str(datos_cl["correo"]))
                    
                    if st.form_submit_button("💾 Actualizar Datos"):
                        update_cl = {
                            "nombre": e_nom.strip(),
                            "telefono": e_tel.strip(),
                            "correo": e_eml.strip()
                        }
                        supabase.table("clientes").update(update_cl).eq("id", datos_cl["id"]).execute()
                        st.success("✅ Datos actualizados."); st.rerun()

        st.divider()
        busqueda_cl = st.text_input("🔍 Buscar cliente", "", key="search_cl")
        df_m_cl = df_cl[df_cl['nombre'].str.contains(busqueda_cl, case=False, na=False)] if busqueda_cl else df_cl
        st.dataframe(df_m_cl, use_container_width=True, hide_index=True)

    # --- TABLA VENDEDORES ---
    with tab_vendedores:
        st.subheader("Equipo de Ventas")

        cv1, cv2 = st.columns(2)
        with cv1.expander("➕ Registrar Nuevo Vendedor"):
            with st.form("form_nuevo_vd"):
                f_nom_v = st.text_input("Nombre Vendedor *")
                f_tel_v = st.text_input("Teléfono")
                # Agregamos comisión base que definimos en el esquema
                f_com = st.number_input("Comisión Base (%)", min_value=0.0, max_value=100.0, value=3.0)
                
                if st.form_submit_button("💾 Registrar Vendedor", type="primary"):
                    if not f_nom_v:
                        st.error("Nombre obligatorio.")
                    else:
                        nuevo_v = {
                            "nombre": f_nom_v.strip(), 
                            "telefono": f_tel_v.strip(),
                            "comision_base": f_com
                        }
                        supabase.table("vendedores").insert(nuevo_v).execute()
                        st.success("✅ Vendedor registrado."); st.rerun()

        with cv2.expander("✏️ Editar Vendedor"):
            if df_vd.empty:
                st.info("No hay vendedores.")
            else:
                vd_sel = st.selectbox("Seleccione vendedor", df_vd["nombre"].tolist())
                datos_vd = df_vd[df_vd["nombre"] == vd_sel].iloc[0]
                
                with st.form("form_edit_vd"):
                    e_nom_v = st.text_input("Nombre", value=datos_vd["nombre"])
                    e_tel_v = st.text_input("Teléfono", value=str(datos_vd["telefono"]))
                    e_com_v = st.number_input("Comisión Base (%)", value=float(datos_vd.get("comision_base", 0)))
                    
                    if st.form_submit_button("💾 Actualizar Vendedor"):
                        supabase.table("vendedores").update({
                            "nombre": e_nom_v.strip(),
                            "telefono": e_tel_v.strip(),
                            "comision_base": e_com_v
                        }).eq("id", datos_vd["id"]).execute()
                        st.success("✅ Vendedor actualizado."); st.rerun()

        st.divider()
        busqueda_vd = st.text_input("🔍 Buscar vendedor", "", key="search_vd")
        df_m_vd = df_vd[df_vd['nombre'].str.contains(busqueda_vd, case=False, na=False)] if busqueda_vd else df_vd
        st.dataframe(df_m_vd, use_container_width=True, hide_index=True)
