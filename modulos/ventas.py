import streamlit as st
import pandas as pd
from datetime import datetime

def render_ventas(supabase):
    st.title("📝 Gestión de Ventas")

    # --- 1. CARGA DE DATOS DESDE SUPABASE ---
    try:
        # Traemos TODO el directorio (para filtrar clientes y vendedores después)
        res_dir = supabase.table("directorio").select("id, nombre, tipo").order("nombre").execute()
        # Traemos todas las ubicaciones
        res_ub = supabase.table("ubicaciones").select("*").order("manzana").order("lote").execute()
        
        # Traemos las ventas haciendo JOIN con 'directorio' dos veces (cliente y vendedor)
        # Nota: En Supabase, para unir la misma tabla dos veces usamos el nombre de la columna
        res_v = supabase.table("ventas").select("""
            *,
            cliente:directorio!cliente_id(nombre),
            vendedor:directorio!vendedor_id(nombre),
            ubicacion:ubicaciones(ubicacion_display)
        """).execute()

        df_dir = pd.DataFrame(res_dir.data)
        df_u = pd.DataFrame(res_ub.data)
        df_v = pd.DataFrame(res_v.data)
    except Exception as e:
        st.error(f"Error al cargar datos: {e}")
        return

    tab_nueva, tab_editar, tab_lista = st.tabs(["✨ Nueva Venta/Apartado", "✏️ Editor y Archivo", "📋 Historial"])

    # --- PESTAÑA 1: NUEVA VENTA ---
    with tab_nueva:
        st.subheader("Registrar Nuevo Contrato")
        lotes_libres = df_u[df_u["estatus"] == "Disponible"]
        
        if lotes_libres.empty:
            st.warning("No hay lotes disponibles para nueva venta.")
        else:
            # Usamos 'ubicacion_display' que es el nombre bonito (M01-L01)
            f_lote_txt = st.selectbox("📍 Seleccione Lote", ["--"] + lotes_libres["ubicacion_display"].tolist())
            
            if f_lote_txt != "--":
                row_u = lotes_libres[lotes_libres["ubicacion_display"] == f_lote_txt].iloc[0]
                id_lote = int(row_u['id'])
                costo_base = float(row_u['precio_lista'])
                eng_minimo = float(row_u['enganche_requerido'])
                
                st.info(f"💰 **Condiciones Sugeridas:** Precio: ${costo_base:,.2f} | Enganche: ${eng_minimo:,.2f}")

                with st.form("form_nueva_venta"):
                    c1, c2 = st.columns(2)
                    f_fec = c1.date_input("📅 Fecha de Contrato", value=datetime.now())
                    
                    # Filtramos el directorio para Vendedores
                    vendedores_df = df_dir[df_dir["tipo"] == "Vendedor"]
                    f_vende_sel = c1.selectbox("👔 Vendedor", ["-- SELECCIONAR --"] + vendedores_df["nombre"].tolist())
                    
                    # Filtramos el directorio para Clientes/Prospectos
                    clientes_df = df_dir[df_dir["tipo"] != "Vendedor"]
                    f_cli_sel = c2.selectbox("👤 Cliente", ["-- SELECCIONAR --"] + clientes_df["nombre"].tolist())
                    
                    st.markdown("---")
                    cf1, cf2, cf3 = st.columns(3)
                    f_tot = cf1.number_input("Precio Final ($)", min_value=0.0, value=costo_base)
                    f_pla = cf2.selectbox("🕒 Plazo (Meses)", [1, 12, 24, 36, 48, 60, 72], index=2)
                    f_eng_pag = cf3.number_input("Enganche Pagado ($)", min_value=0.0, value=eng_minimo)
                    
                    # Cálculo de mensualidad
                    m_calc = (f_tot - f_eng_pag) / f_pla if f_pla > 0 else 0
                    st.write(f"📊 **Mensualidad Resultante:** $ {m_calc:,.2f}")

                    if st.form_submit_button("💾 GENERAR CONTRATO", type="primary"):
                        if f_cli_sel == "-- SELECCIONAR --" or f_vende_sel == "-- SELECCIONAR --":
                            st.error("❌ Debe seleccionar un cliente y un vendedor del directorio.")
                        else:
                            id_cliente = int(df_dir[df_dir["nombre"] == f_cli_sel]["id"].iloc[0])
                            id_vendedor = int(df_dir[df_dir["nombre"] == f_vende_sel]["id"].iloc[0])

                            nueva_v_data = {
                                "lote_id": id_lote,
                                "cliente_id": id_cliente,
                                "vendedor_id": id_vendedor,
                                "precio_venta": f_tot,
                                "enganche_pagado": f_eng_pag,
                                "fecha_venta": str(f_fec),
                                "estatus_venta": "Activa"
                            }
                            
                            try:
                                # 1. Insertar Venta
                                supabase.table("ventas").insert(nueva_v_data).execute()
                                # 2. Actualizar Lote a Vendido
                                supabase.table("ubicaciones").update({"estatus": "Vendido"}).eq("id", id_lote).execute()
                                
                                st.success(f"✅ Venta registrada y lote {f_lote_txt} actualizado.")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error al guardar: {e}")

    # --- PESTAÑA 2: EDITOR Y ARCHIVO ---
    with tab_editar:
        st.subheader("Modificar / Cancelar Ventas")
        if df_v.empty:
            st.info("No hay ventas registradas.")
        else:
            # Formateamos nombre para el selector: Lote | Cliente
            df_v['display_name'] = df_v['ubicacion'].apply(lambda x: x['ubicacion_display']) + " - " + df_v['cliente'].apply(lambda x: x['nombre'])
            edit_sel = st.selectbox("Seleccione Venta", ["--"] + df_v["display_name"].tolist())
            
            if edit_sel != "--":
                datos_v = df_v[df_v["display_name"] == edit_sel].iloc[0]
                
                with st.form("form_edit_vta"):
                    st.warning(f"Editando contrato de: {datos_v['cliente']['nombre']}")
                    e_tot = st.number_input("Precio Final ($)", value=float(datos_v["precio_venta"]))
                    e_eng = st.number_input("Enganche Pagado ($)", value=float(datos_v["enganche_pagado"]))
                    e_est = st.selectbox("Estatus de Venta", ["Activa", "Cancelada"], 
                                       index=0 if datos_v['estatus_venta'] == "Activa" else 1)
                    
                    c_save, c_cancel = st.columns(2)
                    
                    if c_save.form_submit_button("💾 ACTUALIZAR DATOS"):
                        supabase.table("ventas").update({
                            "precio_venta": e_tot,
                            "enganche_pagado": e_eng,
                            "estatus_venta": e_est
                        }).eq("id", datos_v['id']).execute()
                        st.success("Cambios guardados."); st.rerun()

                    if c_cancel.form_submit_button("🗑️ ELIMINAR REGISTRO"):
                        # Al eliminar, liberamos el lote
                        supabase.table("ubicaciones").update({"estatus": "Disponible"}).eq("id", datos_v['lote_id']).execute()
                        supabase.table("ventas").delete().eq("id", datos_v['id']).execute()
                        st.warning("Venta eliminada y lote liberado."); st.rerun()

    # --- PESTAÑA 3: HISTORIAL ---
    with tab_lista:
        if not df_v.empty:
            st.subheader("📋 Historial de Ventas")
            df_m = df_v.copy()
            # Aplanamos para la tabla
            df_m['Lote'] = df_m['ubicacion'].apply(lambda x: x['ubicacion_display'])
            df_m['Cliente'] = df_m['cliente'].apply(lambda x: x['nombre'])
            df_m['Vendedor'] = df_m['vendedor'].apply(lambda x: x['nombre'])
            
            df_final = df_m[["fecha_venta", "Lote", "Cliente", "Vendedor", "precio_venta", "enganche_pagado", "estatus_venta"]]
            
            st.dataframe(
                df_final.style.format({"precio_venta": "$ {:,.2f}", "enganche_pagado": "$ {:,.2f}"}),
                use_container_width=True,
                hide_index=True
            )
