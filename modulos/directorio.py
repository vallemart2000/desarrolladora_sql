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
            tipo = c2.selectbox("Tipo de Contacto", ["Cliente", "Vendedor", "Prospecto", "Socio"])
            
            c3, c4 = st.columns(2)
            # Ayuda visual para el usuario
            telefono_input = c3.text_input("Teléfono (10 dígitos)", help="Solo números enteros.")
            correo = c4.text_input("Correo Electrónico")
            
            notas = st.text_area("Notas o Referencias")

            if st.form_submit_button("Guardar en Directorio"):
                # --- VALIDACIÓN DE TELÉFONO ---
                # Filtramos para dejar solo números por si el usuario pone espacios o guiones
                tel_clean = "".join(filter(str.isdigit, telefono_input))
                
                if not nombre:
                    st.warning("El nombre es obligatorio.")
                elif len(tel_clean) != 10:
                    st.error("🚨 El teléfono debe tener exactamente 10 dígitos numéricos.")
                else:
                    nuevo_registro = {
                        "nombre": nombre.strip(),
                        "tipo": tipo,
                        "telefono": tel_clean,
                        "correo": correo.strip().lower(),
                        "notas": notas
                    }
                    try:
                        supabase.table("directorio").insert(nuevo_registro).execute()
                        st.success(f"✅ {nombre} guardado como {tipo}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error en base de datos: {e}")

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
                    "tipo": "Categoría",
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
                sel = st.selectbox("Selecciona persona para editar", df['nombre'].tolist())
                d = df[df['nombre'] == sel].iloc[0]
                
                with st.form("edit_dir"):
                    st.write(f"Editando a: **{sel}**")
                    enombre = st.text_input("Nombre", value=d['nombre'])
                    etipo = st.selectbox("Tipo", ["Cliente", "Vendedor", "Prospecto", "Socio"], 
                                       index=["Cliente", "Vendedor", "Prospecto", "Socio"].index(d['tipo']))
                    etel_input = st.text_input("Teléfono (10 dígitos)", value=d['telefono'])
                    email = st.text_input("Correo", value=d['correo'])
                    
                    c_btn1, c_btn2 = st.columns(2)
                    
                    if c_btn1.form_submit_button("💾 Actualizar"):
                        # Misma validación al editar
                        etel_clean = "".join(filter(str.isdigit, etel_input))
                        
                        if len(etel_clean) == 10:
                            upd = {
                                "nombre": enombre.strip(), 
                                "tipo": etipo, 
                                "telefono": etel_clean, 
                                "correo": email.strip().lower()
                            }
                            supabase.table("directorio").update(upd).eq("id", d['id']).execute()
                            st.success("¡Actualizado!")
                            st.rerun()
                        else:
                            st.error("🚨 El teléfono debe tener 10 dígitos.")
                    
                    if c_btn2.form_submit_button("🗑️ Eliminar"):
                        supabase.table("directorio").delete().eq("id", d['id']).execute()
                        st.warning("Registro eliminado.")
                        st.rerun()
        else:
            st.info("El directorio está vacío.")
