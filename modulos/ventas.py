import streamlit as st
import pandas as pd
from datetime import datetime

def render_ventas(supabase):
    st.title("📝 Gestión de Ventas (SQL)")

    # --- 1. CARGA DE DATOS DESDE SUPABASE ---
    # Traemos clientes, vendedores y lotes para los selectores
    res_cl = supabase.table("clientes").select("id, nombre").order("nombre").execute()
    res_vd = supabase.table("vendedores").select("id, nombre").order("nombre").execute()
    res_ub = supabase.table("ubicaciones").select("*").order("ubicacion").execute()
    
    # Traemos las ventas haciendo un "JOIN" para ver nombres en lugar de IDs
    res_v = supabase.table("ventas").select("""
        *,
        clientes (nombre),
        vendedores (nombre),
        ubicaciones (ubicacion)
    """).execute()

    df_cl = pd.DataFrame(res_cl.data)
    df_vd = pd.DataFrame(res_vd.data)
    df_u = pd.DataFrame(res_ub.data)
    df_v = pd.DataFrame(res_v.data)

    tab_nueva, tab_editar, tab_lista = st.tabs(["✨ Nueva Venta/Apartado", "✏️ Editor y Archivo", "📋 Historial"])

    # --- PESTAÑA 1: NUEVA VENTA ---
    with tab_nueva:
        st.subheader("Registrar Nuevo Contrato")
        lotes_libres = df_u[df_u["estatus"] == "Disponible"]
        
        if lotes_libres.empty:
            st.warning("No hay lotes disponibles.")
        else:
            f_lote_txt = st.selectbox("📍 Seleccione Lote", ["--"] + lotes_libres["ubicacion"].tolist())
            
            if f_lote_txt != "--":
                row_u = lotes_libres[lotes_libres["ubicacion"] == f_lote_txt].iloc[0]
                id_lote = int(row_u['id'])
                costo_base = float(row_u['precio_lista'])
                eng_minimo = float(row_u['enganche_req'])
                
                st.info(f"💰 **Condiciones:** Precio Lista: $ {costo_base:,.2f} | Enganche Mín: $ {eng_minimo:,.2f}")

                with st.form("form_nueva_venta"):
                    c1, c2 = st.columns(2)
                    f_fec = c1.date_input("📅 Fecha de Contrato", value=datetime.now())
                    
                    # Selectores vinculados a IDs
                    vendedores_list = ["-- SELECCIONAR --"] + df_vd["nombre"].tolist()
                    f_vende_sel = c1.selectbox("👔 Vendedor", vendedores_list)
                    
                    clientes_list = ["-- SELECCIONAR --"] + df_cl["nombre"].tolist()
                    f_cli_sel = st.selectbox("👤 Cliente", clientes_list)
                    
                    st.markdown("---")
                    cf1, cf2, cf3 = st.columns(3)
                    f_tot = cf1.number_input("Precio Final ($)", min_value=0.0, value=costo_base)
                    f_pla = cf2.selectbox("🕒 Plazo (Meses)", [12, 24, 36, 48, 72], index=0)
                    f_comision = cf3.number_input("Comisión Pactada ($)", min_value=0.0, value=5000.0)
                    
                    f_coment = st.text_area("📝 Notas Adicionales")
                    m_calc = (f_tot - eng_minimo) / f_pla if f_pla > 0 else 0
                    st.write(f"📊 **Mensualidad Resultante:** $ {m_calc:,.2f}")

                    if st.form_submit_button("💾 GENERAR CONTRATO", type="primary"):
                        if f_cli_sel == "-- SELECCIONAR --" or f_vende_sel == "-- SELECCIONAR --":
                            st.error("❌ Seleccione cliente y vendedor.")
                        else:
                            # Obtener IDs reales
                            id_cliente = int(df_cl[df_cl["nombre"] == f_cli_sel]["id"].iloc[0])
                            id_vendedor = int(df_vd[df_vd["nombre"] == f_vende_sel]["id"].iloc[0])

                            nueva_v_data = {
                                "fecha_contrato": str(f_fec),
                                "lote_id": id_lote,
                                "cliente_id": id_cliente,
                                "vendedor_id": id_vendedor,
                                "precio_total": f_tot,
                                "enganche_pagado": 0.0,
                                "enganche_requerido": eng_minimo,
                                "comision_venta": f_comision,
                                "plazo_meses": f_pla,
                                "mensualidad": m_calc,
                                "estatus_pago": "Pendiente",
                                "notas": f_coment
                            }
                            
                            # 1. Insertar Venta
                            supabase.table("ventas").insert(nueva_v_data).execute()
                            # 2. Actualizar Lote
                            supabase.table("ubicaciones").update({"estatus": "Apartado"}).eq("id", id_lote).execute()
                            
                            st.success(f"✅ Contrato registrado con éxito.")
                            st.rerun()

    # --- PESTAÑA 2: EDITOR Y ARCHIVO ---
    with tab_editar:
        st.subheader("Modificar Contratos Existentes")
        if df_v.empty:
            st.info("No hay registros.")
        else:
            # Mostramos info amigable: Ubicación | Cliente
            df_v['display_name'] = df_v['ubicaciones'].apply(lambda x: x['ubicacion']) + " | " + df_v['clientes'].apply(lambda x: x['nombre'])
            edit_sel = st.selectbox("Seleccione Contrato", ["--"] + df_v["display_name"].tolist())
            
            if edit_sel != "--":
                datos_v = df_v[df_v["display_name"] == edit_sel].iloc[0]
                v_id = datos_v['id']
                l_id = datos_v['lote_id']

                with st.form("form_edit_vta_sql"):
                    e_tot = st.number_input("Precio Final ($)", value=float(datos_v["precio_total"]))
                    e_pla = st.selectbox("Plazo (Meses)", [12, 24, 36, 48, 72], index=[12, 24, 36, 48, 72].index(int(datos_v["plazo_meses"])))
                    e_com = st.number_input("Comisión ($)", value=float(datos_v.get("comision_venta", 0)))
                    f_motivo = st.text_input("Motivo (solo para cancelación)")
                    
                    c_save, c_cancel = st.columns(2)
                    
                    if c_save.form_submit_button("💾 GUARDAR CAMBIOS"):
                        eng_req = float(datos_v["enganche_requerido"])
                        nueva_mens = (e_tot - eng_req) / e_pla
                        
                        supabase.table("ventas").update({
                            "precio_total": e_tot,
                            "plazo_meses": e_pla,
                            "comision_venta": e_com,
                            "mensualidad": nueva_mens
                        }).eq("id", v_id).execute()
                        
                        st.success("Cambios aplicados en SQL."); st.rerun()

                    if c_cancel.form_submit_button("❌ CANCELAR CONTRATO"):
                        if not f_motivo: 
                            st.error("Indique motivo de cancelación.")
                        else:
                            # 1. Lote disponible
                            supabase.table("ubicaciones").update({"estatus": "Disponible"}).eq("id", l_id).execute()
                            # 2. Borrar venta
                            supabase.table("ventas").delete().eq("id", v_id).execute()
                            st.warning("Venta eliminada."); st.rerun()

    # --- PESTAÑA 3: HISTORIAL ---
    with tab_lista:
        if not df_v.empty:
            st.subheader("📋 Resumen de Contratos")
            # Aplanamos los datos de las relaciones para el dataframe
            df_m = df_v.copy()
            df_m['Ubicación'] = df_m['ubicaciones'].apply(lambda x: x['ubicacion'])
            df_m['Cliente'] = df_m['clientes'].apply(lambda x: x['nombre'])
            
            df_final = df_m[["id", "fecha_contrato", "Ubicación", "Cliente", "precio_total", "mensualidad", "estatus_pago"]]
            
            st.dataframe(
                df_final.style.format({"precio_total": "$ {:,.2f}", "mensualidad": "$ {:,.2f}"}),
                use_container_width=True,
                hide_index=True
            )
