import streamlit as st
import pandas as pd
from datetime import datetime
import time

def render_cobranza(supabase):
    st.title("💰 Gestión de Cobranza")
    
    # --- 1. CARGA DE DATOS ---
    try:
        # Cargamos ventas
        res_v = supabase.table("ventas").select("""
            id, ubicacion_id, cliente_id, plazo,
            cliente:directorio!cliente_id(nombre),
            ubicacion:ubicaciones(id, etapa, manzana, lote, precio, enganche_req)
        """).execute()
        df_v = pd.DataFrame(res_v.data)
        
        # Cargamos pagos (renombramos el ID de entrada para evitar conflictos)
        res_p = supabase.table("pagos").select("*").order("fecha", desc=True).execute()
        df_p = pd.DataFrame(res_p.data)
        if not df_p.empty:
            df_p = df_p.rename(columns={'id': 'pago_id'}) # Claridad absoluta

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

    # --- PESTAÑA 2: HISTORIAL Y EDICIÓN ---
    with tab_historial:
        if df_p.empty:
            st.info("No hay historial de pagos.")
        else:
            # Join con los IDs ya renombrados (pago_id vs id de venta)
            df_historial = df_p.merge(df_v[['id', 'display_vta']], left_on='venta_id', right_on='id', how='left')
            
            st.subheader("📋 Registro de Movimientos")
            search = st.text_input("🔍 Buscar por folio o cliente:", key="hist_search")
            if search:
                df_historial = df_historial[
                    df_historial['display_vta'].str.contains(search, case=False) | 
                    df_historial['folio'].str.contains(search, case=False)
                ]

            st.dataframe(
                df_historial[['fecha', 'display_vta', 'monto', 'folio', 'comentarios']],
                use_container_width=True, hide_index=True
            )

            st.markdown("---")
            st.subheader("✏️ Gestión de Registro Específico")
            
            # Label descriptivo para el selector
            df_historial['select_label'] = df_historial.apply(
                lambda x: f"Folio: {x['folio']} | {x['display_vta']} | ${x['monto']:,.2f}", axis=1
            )
            
            pago_a_editar = st.selectbox(
                "Seleccione el pago para modificar/eliminar:", 
                ["--"] + df_historial['select_label'].tolist(),
                key="pago_editor_selector"
            )

            if pago_a_editar != "--":
                pago_data = df_historial[df_historial['select_label'] == pago_a_editar].iloc[0]
                p_id = pago_data['pago_id'] # Usamos el nombre nuevo

                c_ed, c_de = st.columns([2, 1])
                
                with c_ed:
                    with st.expander("📝 Editar Datos", expanded=True):
                        with st.form("form_edit_pago_real"):
                            e_fol = st.text_input("Folio", value=pago_data['folio'])
                            e_mon = st.number_input("Monto ($)", value=float(pago_data['monto']))
                            e_fec = st.date_input("Fecha", value=datetime.strptime(pago_data['fecha'], '%Y-%m-%d'))
                            e_com = st.text_area("Comentarios", value=pago_data['comentarios'])
                            
                            if st.form_submit_button("💾 Guardar Cambios"):
                                supabase.table("pagos").update({
                                    "folio": e_fol, "monto": e_mon,
                                    "fecha": str(e_fec), "comentarios": e_com
                                }).eq("id", p_id).execute()
                                st.success("¡Registro actualizado!")
                                time.sleep(1)
                                st.rerun()

                with c_de:
                    with st.expander("🚨 Eliminar", expanded=True):
                        st.write("¿Borrar este pago?")
                        if st.button("🗑️ ELIMINAR", type="primary", use_container_width=True):
                            try:
                                supabase.table("pagos").delete().eq("id", p_id).execute()
                                st.toast("Registro eliminado")
                                time.sleep(1)
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error al borrar: {e}")
