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

    # --- 2. PESTAÑAS PRINCIPALES ---
    tab_nuevo, tab_ver = st.tabs(["➕ Nuevo Registro", "📋 Ver Directorio"])

    with tab_nuevo:
        with st.form("form_nuevo_registro", clear_on_submit=True):
            c1, c2 = st.columns(2)
            nombre = c1.text_input("Nombre Completo *")
            tipo = c2.selectbox("Tipo de Contacto", ["Cliente", "Vendedor"])
            
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
                        st.success(f"✅ {nombre_limpio} guardado.")
                        st.rerun()
                    except Exception as e: st.error(f"Error: {e}")

    with tab_ver:
        if df.empty:
            st.info("El directorio está vacío.")
        else:
            # --- SUB-PESTAÑAS PARA SEPARAR CLIENTES Y VENDEDORES ---
            st.write("### Filtrar por categoría")
            sub_tab_c, sub_tab_v = st.tabs(["👥 Clientes", "💼 Vendedores"])

            # Buscador general (fuera de las sub-pestañas para que afecte a ambas)
            busqueda = st.text_input("🔍 Buscar por nombre en la lista seleccionada...", key="search_dir")

            def mostrar_tabla(tipo_filtro):
                df_filtro = df[df['tipo'] == tipo_filtro].copy()
                if busqueda:
                    df_filtro = df_filtro[df_filtro['nombre'].str.contains(busqueda, case=False, na=False)]
                
                if df_filtro.empty:
                    st.warning(f"No se encontraron {tipo_filtro.lower()}s.")
                else:
                    st.dataframe(
                        df_filtro[["nombre", "telefono", "correo"]],
                        column_config={
                            "nombre": "Nombre Completo",
                            "telefono": "Teléfono",
                            "correo": "Email"
                        },
                        use_container_width=True, hide_index=True
                    )
                return df_filtro

            with sub_tab_c:
                df_clientes = mostrar_tabla("Cliente")

            with sub_tab_v:
                df_vendedores = mostrar_tabla("Vendedor")

            st.markdown("---")
            
            # --- SECCIÓN DE EDICIÓN (Se adapta a lo que el usuario ve) ---
            with st.expander("✏️ Editar o Eliminar del Directorio"):
                # Unificamos los nombres según lo que se esté buscando para facilitar la selección
                opciones_edit = df['nombre'].tolist()
                sel = st.selectbox("Selecciona un registro para modificar:", ["--"] + opciones_edit)
                
                if sel != "--":
                    d = df[df['nombre'] == sel].iloc[0]
                    
                    with st.form("edit_dir_secure"):
                        st.subheader(f"Modificando: {d['nombre']}")
                        col_e1, col_e2 = st.columns(2)
                        enombre = col_e1.text_input("Nombre", value=d['nombre'])
                        etipo = col_e2.selectbox("Categoría", ["Cliente", "Vendedor"], 
                                               index=0 if d['tipo'] == "Cliente" else 1)
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
                    st.subheader("🗑️ Zona de Peligro")
                    confirmar_check = st.checkbox(f"Confirmo que deseo borrar a **{d['nombre']}** permanentemente.")
                    
                    if confirmar_check:
                        if st.button(f"ELIMINAR REGISTRO", type="primary", use_container_width=True):
                            try:
                                supabase.table("directorio").delete().eq("id", d['id']).execute()
                                st.warning("Registro eliminado."); st.rerun()
                            except Exception as e:
                                st.error("❌ No se puede eliminar: El contacto tiene ventas o pagos asociados.")
