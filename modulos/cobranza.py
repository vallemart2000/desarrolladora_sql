import streamlit as st
import pandas as pd
from datetime import datetime
import time

def render_cobranza(supabase):
    st.title("💰 Gestión de Cobranza")
    
    # --- 1. CARGA DE DATOS ---
    try:
        # Cargamos ventas con datos de cliente y ubicación
        res_v = supabase.table("ventas").select("""
            id, ubicacion_id, cliente_id, plazo,
            cliente:directorio!cliente_id(nombre),
            ubicacion:ubicaciones(id, etapa, manzana, lote, precio, enganche_req)
        """).execute()
        df_v = pd.DataFrame(res_v.data)
        
        # Cargamos pagos
        res_p = supabase.table("pagos").select("*").order("fecha", desc=True).execute()
        df_p = pd.DataFrame(res_p.data)
        if not df_p.empty:
            df_p = df_p.rename(columns={'id': 'pago_id'})

        if not df_v.empty:
            # Preparar datos para la tabla de selección
            df_v['Lote'] = df_v['ubicacion'].apply(lambda x: f"M{int(x['manzana']):02d}-L{int(x['lote']):02d}")
            df_v['Cliente'] = df_v['cliente'].apply(lambda x: x['nombre'])
            df_v['Precio'] = df_v['ubicacion'].apply(lambda x: float(x['precio'] or 0))
            # Para el selector interno
            df_v['display_vta'] = df_v['Lote'] + " | " + df_v['Cliente']
        
    except Exception as e:
        st.error(f"⚠️ Error cargando datos: {e}")
        return

    tab_pago, tab_historial = st.tabs(["💵 Registrar Pago", "📋 Historial y Edición"])

    # --- PESTAÑA 1: REGISTRAR PAGO (Estrategia de Selección) ---
    with tab_pago:
        if df_v.empty:
            st.warning("No hay ventas registradas.")
        else:
            st.subheader("1. Seleccione una Venta")
            
            # FILTRO DE BÚSQUEDA
            search_name = st.text_input("🔍 Filtrar por nombre de cliente o lote:", placeholder="Ej: Juan Perez o M01")
            
            df_filtrado = df_v.copy()
            if search_name:
                df_filtrado = df_filtrado[
                    df_filtrado['Cliente'].str.contains(search_name, case=False) | 
                    df_filtrado['Lote'].str.contains(search_name, case=False)
                ]

            # TABLA DE SELECCIÓN
            event = st.dataframe(
                df_filtrado[['Lote', 'Cliente', 'Precio']],
                column_config={
                    "Precio": st.column_config.NumberColumn("Precio Total", format="dollar"),
                },
                use_container_width=True,
                hide_index=True,
                on_select="rerun",
                selection_mode="single-row",
                key="venta_selector_table"
            )

            # LÓGICA DE FORMULARIO SI HAY SELECCIÓN
            if len(event.selection.rows) > 0:
                idx = event.selection.rows[0]
                v = df_filtrado.iloc[idx]
                venta_id_real = int(v['id'])
                ubicacion_id_real = int(v['ubicacion_id'])
                
                # Consultar estatus financiero actual del lote seleccionado
                res_status = supabase.table("vista_estatus_lotes").select("*").eq("ubicacion_id", ubicacion_id_real).execute()
                
                if res_status.data:
                    status = res_status.data[0]
                    precio_total = float(v['Precio'])
                    eng_req = float(v['ubicacion']['enganche_req'] or 0)
                    total_pagado = float(status.get('total_pagado') or 0)
                    plazo_real = int(v.get('plazo') or 48)
                    
                    faltante_eng = max(0.0, eng_req - total_pagado)
                    saldo_total = max(0.0, precio_total - total_pagado)
                    monto_a_financiar = precio_total - eng_req
                    mensualidad = monto_a_financiar / plazo_real if plazo_real > 0 else 0
                    pago_sugerido = faltante_eng if faltante_eng > 0 else mensualidad

                    st.markdown("---")
                    st.subheader(f"2. Detalles de Cobro: {v['Lote']}")
                    
                    # Dashboard Resumen
                    st.markdown(f"""
                    <div style="background-color: #1E1E1E; padding: 20px; border-radius: 12px; border: 1px solid #333; margin-bottom: 20px;">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <span style="color: #808495; font-size: 0.8rem;">CLIENTE: <b>{v['Cliente']}</b></span>
                            <span style="background-color: {'#FF4B4B22' if faltante_eng > 0 else '#00C85322'}; color: {'#FF4B4B' if faltante_eng > 0 else '#00C853'}; padding: 2px 10px; border-radius: 15px; font-size: 0.7rem; font-weight: bold;">
                                {'DEBE ENGANCHE' if faltante_eng > 0 else 'ENGANCHE CUBIERTO'}
                            </span>
                        </div>
                        <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 15px; margin-top: 15px;">
                            <div style="text-align: center; border-right: 1px solid #333;">
                                <p style="color: #808495; font-size: 0.7rem; margin:0;">POR PAGAR ENGANCHE</p>
                                <h3 style="color: {'#FF4B4B' if faltante_eng > 0 else '#00C853'}; margin:0;">${faltante_eng:,.2f}</h3>
                            </div>
                            <div style="text-align: center; border-right: 1px solid #333;">
                                <p style="color: #808495; font-size: 0.7rem; margin:0;">SALDO TOTAL</p>
                                <h3 style="color: white; margin:0;">${saldo_total:,.2f}</h3>
                            </div>
                            <div style="text-align: center;">
                                <p style="color: #808495; font-size: 0.7rem; margin:0;">MENSUALIDAD BASE</p>
                                <h3 style="color: white; margin:0;">${mensualidad:,.2f}</h3>
                            </div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                    with st.form("form_pago_nuevo", clear_on_submit=True):
                        c1, c2 = st.columns(2)
                        f_fol = c1.text_input("Folio Recibo / Referencia")
                        f_mon = c2.number_input("Monto a Recibir ($)", min_value=0.0, value=float(pago_sugerido), format="%.2f")
                        f_com = st.text_area("Comentarios o Concepto de Pago")
                        
                        if st.form_submit_button("✅ CONFIRMAR Y REGISTRAR PAGO", type="primary", use_container_width=True):
                            if f_mon <= 0:
                                st.error("El monto debe ser mayor a 0.")
                            else:
                                try:
                                    supabase.table("pagos").insert({
                                        "venta_id": venta_id_real, 
                                        "monto": f_mon,
                                        "fecha": str(datetime.now().date()), 
                                        "folio": f_fol, 
                                        "comentarios": f_com
                                    }).execute()
                                    st.balloons()
                                    st.success("💰 Pago registrado exitosamente")
                                    time.sleep(1.5)
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Error: {e}")
            else:
                st.info("👆 Seleccione un cliente de la tabla para ver su estado de cuenta y registrar pagos.")

    # --- PESTAÑA 2: HISTORIAL Y EDICIÓN (Se mantiene funcional) ---
    with tab_historial:
        if df_p.empty:
            st.info("No hay historial de pagos.")
        else:
            df_historial = df_p.merge(df_v[['id', 'display_vta']], left_on='venta_id', right_on='id', how='left')
            
            st.subheader("📋 Registro Global de Movimientos")
            search_hist = st.text_input("🔍 Buscar en historial (Folio o Cliente):")
            
            if search_hist:
                df_historial = df_historial[
                    df_historial['display_vta'].str.contains(search_hist, case=False) | 
                    df_historial['folio'].str.contains(search_hist, case=False)
                ]

            st.dataframe(
                df_historial[['fecha', 'display_vta', 'monto', 'folio', 'comentarios']],
                column_config={"monto": st.column_config.NumberColumn("Monto", format="dollar")},
                use_container_width=True, hide_index=True
            )

            st.markdown("---")
            # Selector de edición simplificado
            df_historial['select_label'] = df_historial.apply(
                lambda x: f"Folio: {x['folio']} | {x['display_vta']} | ${x['monto']:,.2f}", axis=1
            )
            
            pago_a_editar = st.selectbox("✏️ Seleccione un pago para modificar/eliminar:", ["--"] + df_historial['select_label'].tolist())

            if pago_a_editar != "--":
                pago_data = df_historial[df_historial['select_label'] == pago_a_editar].iloc[0]
                p_id = pago_data['pago_id']

                col1, col2 = st.columns([2, 1])
                with col1:
                    with st.expander("Modificar Datos", expanded=True):
                        with st.form("edit_pago"):
                            new_fol = st.text_input("Folio", value=pago_data['folio'])
                            new_mon = st.number_input("Monto", value=float(pago_data['monto']))
                            if st.form_submit_button("Actualizar"):
                                supabase.table("pagos").update({"folio": new_fol, "monto": new_mon}).eq("id", p_id).execute()
                                st.rerun()
                with col2:
                    with st.expander("Eliminar"):
                        if st.button("BORRAR PAGO", type="primary"):
                            supabase.table("pagos").delete().eq("id", p_id).execute()
                            st.rerun()
