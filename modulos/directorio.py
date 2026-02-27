import streamlit as st
import pandas as pd

def render_directorio(supabase):
    st.header("👤 Directorio General")

    # --- 1. OBTENER DATOS ---
    try:
        response = supabase.table("directorio").select("*").order("nombre").execute()
        df = pd.DataFrame(response.data)
    except Exception as e:
        st.error(f"Error al conectar con el directorio: {e}")
        return

    # --- 2. PESTAÑAS ---
    tab1, tab2 = st.tabs(["➕ Nuevo Registro", "📋 Ver Directorio"])

    with tab1:
        with st.form("form_nuevo_registro", clear_on_submit=True):
            c1, c2 = st.columns(2)
            nombre = c1.text_input("Nombre Completo")
            # Agregamos Categoría para que sepas quién es quién en el mismo lugar
            tipo = c2.selectbox("Tipo de Contacto", ["Cliente", "Vendedor", "Prospecto", "Socio"])
            
            c3, c4 = st.columns(2)
            telefono = c3.text_input("Teléfono")
            correo = c4.text_input("Correo Electrónico")
            
            notas = st.text_area("Notas o Referencias")

            if st.form_submit_button("Guardar en Directorio"):
                if nombre:
                    nuevo_registro = {
                        "nombre": nombre.strip(),
                        "tipo": tipo,
                        "telefono": telefono.strip(),
                        "correo": correo.strip().lower(),
                        "notas": notas
                    }
                    supabase.table("directorio").insert(nuevo_registro).execute()
                    st.success(f"✅ {nombre} guardado como {tipo}")
                    st.rerun()
                else:
                    st.warning("El nombre es obligatorio.")

    with tab2:
        if not df.empty:
            # Filtros rápidos
            c_f1, c_f2 = st.columns([2, 1])
            busqueda = c_f1.text_input("🔍 Buscar por nombre...")
            filtro_tipo = c_f2.multiselect("Filtrar por tipo", df['tipo'].unique())

            df_view = df.copy()
            if busqueda:
                df_view = df_view[df_view['nombre'].str.contains(busqueda, case=False, na=False)]
            if filtro_tipo:
                df_view = df_view[df_view['tipo'].isin(filtro_tipo)]

            # Tabla profesional
            st.dataframe(
                df_view[["nombre", "tipo", "telefono", "correo", "notas"]],
                column_config={
                    "nombre": "Nombre",
                    "tipo": st.column_config.SelectboxColumn("Categoría", options=["Cliente", "Vendedor", "Prospecto"]),
                    "telefono": "Teléfono",
                    "correo": "Email",
                    "notas": "Observaciones"
                },
                use_container_width=True,
                hide_index=True
            )

            # --- EDICIÓN Y BORRADO ---
            st.markdown("---")
            with st.expander("✏️ Editar o Eliminar del Directorio"):
                sel = st.selectbox("Selecciona persona", df['nombre'].tolist())
                d = df[df['nombre'] == sel].iloc[0]
                
                with st.form("edit_dir"):
                    enombre = st.text_input("Nombre", value=d['nombre'])
                    etipo = st.selectbox("Tipo", ["Cliente", "Vendedor", "Prospecto"], 
                                       index=["Cliente", "Vendedor", "Prospecto"].index(d['tipo']))
                    etel = st.text_input("Teléfono", value=d['telefono'])
                    email = st.text_input("Correo", value=d['correo'])
                    
                    c_btn1, c_btn2 = st.columns(2)
                    if c_btn1.form_submit_button("💾 Actualizar"):
                        upd = {"nombre": enombre, "tipo": etipo, "telefono": etel, "correo": email}
                        supabase.table("directorio").update(upd).eq("id", d['id']).execute()
                        st.success("¡Actualizado!")
                        st.rerun()
                    
                    if c_btn2.form_submit_button("🗑️ Eliminar"):
                        supabase.table("directorio").delete().eq("id", d['id']).execute()
                        st.rerun()
        else:
            st.info("El directorio está vacío.")
