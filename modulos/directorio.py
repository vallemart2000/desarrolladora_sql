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
            nombre = c1.text_input("Nombre Completo *")
            tipo = c2.selectbox("Tipo de Contacto", ["Cliente", "Vendedor", "Prospecto", "Socio"])
            
            c3, c4 = st.columns(2)
            # Quitamos el 'value' por defecto para que sea opcional
            telefono_input = c3.text_input("Teléfono (Opcional - 10 dígitos)")
            correo = c4.text_input("Correo Electrónico (Opcional)")

            if st.form_submit_button("Guardar en Directorio"):
                # --- LÓGICA DE VALIDACIÓN FLEXIBLE ---
                tel_clean = "".join(filter(str.isdigit, telefono_input))
                errores = []

                # 1. Validar Nombre (Obligatorio)
                if not nombre.strip():
                    errores.append("El nombre es obligatorio.")

                # 2. Validar Teléfono (Solo si el usuario escribió algo)
                if tel_clean and len(tel_clean) != 10:
                    errores.append("Si ingresas un teléfono, debe tener exactamente 10 dígitos.")

                # 3. Validar Correo (Solo si el usuario escribió algo)
                if correo.strip() and "@" not in correo:
                    errores.append("El correo ingresado no es válido (falta el '@').")

                if errores:
                    for err in errores:
                        st.error(f"🚨 {err}")
                else:
                    nuevo_registro = {
                        "nombre": nombre.strip(),
                        "tipo": tipo,
                        "telefono": tel_clean if tel_clean else None, # Guardamos NULL si está vacío
                        "correo": correo.strip().lower() if correo.strip() else None
                    }
                    try:
                        supabase.table("directorio").insert(nuevo_registro).execute()
                        st.success(f"✅ {nombre} guardado correctamente.")
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

            st.dataframe(
                df_view[["nombre", "tipo", "telefono", "correo"]],
                column_config={
                    "nombre": "Nombre",
                    "tipo": "Categoría",
                    "telefono": "Teléfono",
                    "correo": "Email"
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
                    enombre = st.text_input("Nombre", value=d['nombre'])
                    etipo = st.selectbox("Tipo", ["Cliente", "Vendedor", "Prospecto", "Socio"], 
                                       index=["Cliente", "Vendedor", "Prospecto", "Socio"].index(d['tipo']))
                    etel_input = st.text_input("Teléfono", value=d['telefono'] if d['telefono'] else "")
                    email = st.text_input("Correo", value=d['correo'] if d['correo'] else "")
                    
                    if st.form_submit_button("💾 Guardar Cambios"):
                        etel_clean = "".join(filter(str.isdigit, etel_input))
                        
                        # Validaciones en edición (mismas reglas)
                        valido = True
                        if etel_clean and len(etel_clean) != 10:
                            st.error("Teléfono inválido (debe ser de 10 dígitos).")
                            valido = False
                        if email.strip() and "@" not in email:
                            st.error("Correo inválido.")
                            valido = False
                            
                        if valido:
                            upd = {
                                "nombre": enombre.strip(), 
                                "tipo": etipo, 
                                "telefono": etel_clean if etel_clean else None, 
                                "correo": email.strip().lower() if email.strip() else None
                            }
                            supabase.table("directorio").update(upd).eq("id", d['id']).execute()
                            st.success("¡Actualizado!"); st.rerun()
