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
            telefono_input = c3.text_input("Teléfono (Opcional - 10 dígitos)")
            correo = c4.text_input("Correo Electrónico (Opcional)")

            if st.form_submit_button("Guardar en Directorio"):
                tel_clean = "".join(filter(str.isdigit, telefono_input))
                errores = []

                if not nombre.strip():
                    errores.append("El nombre es obligatorio.")
                if tel_clean and len(tel_clean) != 10:
                    errores.append("El teléfono debe tener 10 dígitos.")
                if correo.strip() and "@" not in correo:
                    errores.append("El correo no es válido.")

                if errores:
                    for err in errores: st.error(f"🚨 {err}")
                else:
                    nombre_limpio = nombre.strip()
                    if not df.empty:
                        existe = df[(df['nombre'].str.lower() == nombre_limpio.lower()) & (df['tipo'] == tipo)]
                        if not existe.empty:
                            st.warning(f"⚠️ El {tipo} '{nombre_limpio}' ya existe.")
                            return

                    try:
                        supabase.table("directorio").insert({
                            "nombre": nombre_limpio, "tipo": tipo,
                            "telefono": tel_clean if tel_clean else None,
                            "correo": correo.strip().lower() if correo.strip() else None
                        }).execute()
                        st.success(f"✅ {nombre_limpio} guardado."); st.rerun()
                    except Exception as e: st.error(f"Error: {e}")

    with tab2:
        if not df.empty:
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
                column_config={"nombre": "Nombre", "tipo": "Categoría", "telefono": "Teléfono", "correo": "Email"},
                use_container_width=True, hide_index=True
            )

            st.markdown("---")
            # --- SECCIÓN DE EDICIÓN SEGURA ---
            with st.expander("✏️ Editar o Eliminar del Directorio"):
                nombres_lista = df_view['nombre'].tolist() if not df_view.empty else df['nombre'].tolist()
                sel = st.selectbox("Selecciona persona para modificar", ["--"] + nombres_lista)
                
                if sel != "--":
                    d = df[df['nombre'] == sel].iloc[0]
                    
                    # FORMULARIO DE EDICIÓN
                    with st.form("edit_dir_secure"):
                        st.subheader("Modificar Datos")
                        col_e1, col_e2 = st.columns(2)
                        enombre = col_e1.text_input("Nombre", value=d['nombre'])
                        etipo = col_e2.selectbox("Tipo", ["Cliente", "Vendedor", "Prospecto", "Socio"], 
                                               index=["Cliente", "Vendedor", "Prospecto", "Socio"].index(d['tipo']))
                        etel_input = col_e1.text_input("Teléfono", value=d['telefono'] if d['telefono'] else "")
                        email = col_e2.text_input("Correo", value=d['correo'] if d['correo'] else "")
                        
                        if st.form_submit_button("💾 GUARDAR CAMBIOS"):
                            etel_clean = "".join(filter(str.isdigit, etel_input))
                            try:
                                supabase.table("directorio").update({
                                    "nombre": enombre.strip(), "tipo": etipo,
                                    "telefono": etel_clean if etel_clean else None,
                                    "correo": email.strip().lower() if email.strip() else None
                                }).eq("id", d['id']).execute()
                                st.success("¡Actualizado!"); st.rerun()
                            except Exception as e: st.error(f"Error: {e}")

                    st.markdown("---")
                    # ZONA DE ELIMINACIÓN CON DOBLE PASO
                    st.subheader("🗑️ Zona de Peligro")
                    st.write(f"¿Estás seguro de que deseas eliminar a **{d['nombre']}**?")
                    
                    confirmar_check = st.checkbox(f"Confirmo que deseo borrar a {d['nombre']} permanentemente.")
                    
                    if confirmar_check:
                        if st.button(f"🗑️ ELIMINAR A {d['nombre'].upper()}", type="primary"):
                            try:
                                supabase.table("directorio").delete().eq("id", d['id']).execute()
                                st.warning("Registro eliminado definitivamente."); st.rerun()
                            except Exception as e:
                                st.error("❌ No se puede eliminar: Este contacto está vinculado a ventas o pagos existentes.")
                    else:
                        st.info("Para eliminar, marca la casilla de confirmación arriba.")
