import streamlit as st
import pandas as pd
from datetime import datetime
import time

def render_cobranza(supabase):
    st.title("💰 Gestión de Cobranza")
    
    # --- 1. CARGA DE DATOS ---
    try:
        res_v = supabase.table("ventas").select("""
            id, ubicacion_id, cliente_id, plazo,
            cliente:directorio!cliente_id(nombre),
            ubicacion:ubicaciones(id, etapa, manzana, lote, precio, enganche_req)
        """).execute()
        df_v = pd.DataFrame(res_v.data)
        
        res_p = supabase.table("pagos").select("*").order("fecha", desc=True).execute()
        df_p = pd.DataFrame(res_p.data)

        if not df_v.empty:
            df_v['display_vta'] = df_v.apply(
                lambda x: f"M{int(x['ubicacion']['manzana']):02d}-L{int(x['ubicacion']['lote']):02d} | {x['cliente']['nombre']}", 
                axis=1
            )
        
    except Exception as e:
        st.error(f"⚠️ Error cargando datos: {e}")
        return

    tab_pago, tab_historial = st.tabs(["💵 Registrar Pago", "📋 Historial y Edición"])

    # --- PESTAÑA 1: REGISTRAR PAGO ---
    with tab_pago:
        if df_v.empty:
            st.warning("No hay ventas registradas.")
        else:
            seleccion = st.selectbox(
                "🔍 Seleccione Lote / Cliente:", 
                ["--"] + df_v["display_vta"].tolist(),
                key="venta_selector"
            )
            
            if seleccion != "--":
                v = df_v[df_v['display_vta'] == seleccion].iloc[0]
                venta_id_real = int(v['id'])
                ubicacion_id_real = int(v['ubicacion_id'])
                
                res_status = supabase.table("vista_estatus_lotes").select("*").eq("ubicacion_id", ubicacion_id_real).execute()
                
                if res_status.data:
                    status = res_status.data[0]
                    precio_total = float(v['ubicacion']['precio'] or 0)
                    eng_req = float(v['ubicacion']['enganche_req'] or 0)
                    total_pagado = float(status.get('total_pagado') or 0)
                    plazo_real = int(v.get('plazo') or 1)
                    
                    faltante_eng = max(0.0, eng_req - total_pagado)
                    saldo_total = max(0.0, precio_total - total_pagado)
                    monto_a_financiar = precio_total - eng_req
                    mensualidad = monto_a_financiar / plazo_real if plazo_real > 0 else 0
                    pago_sugerido = faltante_eng if faltante_eng > 0 else mensualidad

                    st.markdown(f"""
                    <div style="background-color: #1E1E1E; padding: 20px; border-radius: 12px; border: 1px solid #333; margin-bottom: 20px;">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <span style="color: #808495; font-size: 0.8rem;">CONTRATO ID: <b>{venta_id_real}</b></span>
                            <span style="background-color: {'#FF4B4B22' if faltante_eng > 0 else '#00C85322'}; color: {'#FF4B4B' if faltante_eng > 0 else '#00C853'}; padding: 2px 10px; border-radius: 15px; font-size: 0.7rem; font-weight: bold;">
                                {'DEBE ENGANCHE' if faltante_eng > 0 else 'ENGANCHE CUBIERTO'}
                            </span>
                        </div>
                        <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 15px; margin-top: 15px;">
                            <div style="text-align: center; border-right: 1px solid #333;">
                                <p style="color: #808495; font-size: 0.7rem; margin:0;">PENDIENTE ENGANCHE</p>
                                <h3 style="color: {'#FF4B4B' if faltante_eng > 0 else '#00C853'}; margin:0;">${faltante_eng:,.2f}</h3>
                            </div>
                            <div style="text-align: center; border-right: 1px solid #333;">
                                <p style="color: #808495; font-size: 0.7rem; margin:0;">SALDO RESTANTE</p>
                                <h3 style="color: white; margin:0;">${saldo_total:,.2f}</h3>
                            </div>
                            <div style="text-align: center;">
                                <p style="color: #808495; font-size: 0.7rem; margin:0;">MENSUALIDAD</p>
                                <h3 style="color: white; margin:0;">${mensualidad:,.2f}</h3>
                            </div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                    with st.form("form_pago_final", clear_on_submit=True):
                        st.write("📝 **Detalles del Cobro**")
                        c1, c2 = st.columns(2)
                        f_fol = c1.text_input("Folio Recibo / Referencia")
                        f_mon = c2.number_input("Monto a Recibir ($)", min_value=0.0, value=float(pago_sugerido))
                        f_com = st.text_area("Comentarios")
                        
                        if st.form_submit_button("✅ REGISTRAR PAGO AHORA", type="primary", use_container_width=True):
                            try:
                                supabase.table("pagos").insert({
                                    "venta_id": venta_id_real, "monto": f_mon,
                                    "fecha": str(datetime.now().date()), "folio": f_fol, "comentarios": f_com
                                }).execute()
                                st.toast("💰 Pago registrado!")
                                time.sleep(1)
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error: {e}")

    # --- PESTAÑA 2: HISTORIAL, MODIFICAR Y ELIMINAR ---
    with tab_historial:
        if df_p.empty:
            st.info("No hay historial de pagos.")
        else:
            # Preparamos los datos para la tabla y el buscador
            df_historial = df_p.merge(df_v[['id', 'display_vta']], left_on='venta_id', right_on='id', how='left')
            
            st.subheader("📋 Registro de Movimientos")
            
            # Buscador rápido
            search = st.text_input("🔍 Buscar por folio o cliente:", placeholder="Escriba para filtrar...")
            if search:
                df_historial = df_historial[
                    df_historial['display_vta'].str.contains(search, case=False) | 
                    df_historial['folio'].str.contains(search, case=False)
                ]

            # Mostramos la tabla principal
            st.dataframe(
                df_historial[['fecha', 'display_vta', 'monto', 'folio', 'comentarios']],
                use_container_width=True, hide_index=True
            )

            st.markdown("---")
            st.subheader("✏️ Modificar o Eliminar un Pago")
            
            # Selector para elegir qué pago editar
            df_historial['select_label'] = df_historial.apply(lambda x: f"Folio: {x['folio']} | {x['display_vta']} | ${x['monto']:,.2f} ({x['fecha']})", axis=1)
            pago_a_editar = st.selectbox("Seleccione el pago que desea corregir:", ["--"] + df_historial['select_label'].tolist())

            if pago_a_editar != "--":
                # Extraer datos del pago seleccionado
                pago_data = df_historial[df_historial['select_label'] == pago_a_editar].iloc[0]
                
                col_edit, col_del = st.columns([2, 1])
                
                with col_edit:
                    with st.expander("📝 Editar Información", expanded=True):
                        with st.form("form_edit_pago"):
                            e_fol = st.text_input("Editar Folio", value=pago_data['folio'])
                            e_mon = st.number_input("Editar Monto ($)", value=float(pago_data['monto']))
                            e_fec = st.date_input("Editar Fecha", value=datetime.strptime(pago_data['fecha'], '%Y-%m-%d'))
                            e_com = st.text_area("Editar Comentarios", value=pago_data['comentarios'])
                            
                            if st.form_submit_button("💾 Guardar Cambios", use_container_width=True):
                                try:
                                    supabase.table("pagos").update({
                                        "folio": e_fol, "monto": e_mon,
                                        "fecha": str(e_fec), "comentarios": e_com
                                    }).eq("id", pago_data['id']).execute()
                                    st.success("Actualizado con éxito")
                                    time.sleep(1)
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Error: {e}")

                with col_del:
                    with st.expander("🚨 Zona de Peligro", expanded=True):
                        st.write("Esta acción no se puede deshacer.")
                        if st.button("🗑️ ELIMINAR PAGO", type="secondary", use_container_width=True):
                            # Usamos un modal de confirmación nativo de Streamlit si está disponible, 
                            # si no, una doble verificación simple
                            st.session_state.confirm_delete = True
                        
                        if st.session_state.get('confirm_delete'):
                            st.warning("¿Está seguro de borrar este registro?")
                            if st.button("SÍ, BORRAR DEFINITIVAMENTE", type="primary", use_container_width=True):
                                try:
                                    supabase.table("pagos").delete().eq("id", pago_data['id']).execute()
                                    st.toast("Pago eliminado correctamente")
                                    st.session_state.confirm_delete = False
                                    time.sleep(1)
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Error: {e}")
