import streamlit as st
import pandas as pd
from datetime import datetime

def render_cobranza(supabase):
    st.title("💰 Gestión de Cobranza")
    
    # --- 1. CARGA DE DATOS ---
    try:
        # Traemos la información de ventas vinculada a ubicaciones y clientes
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

    tab_pago, tab_historial = st.tabs(["💵 Registrar Pago", "📋 Historial"])

    with tab_pago:
        if df_v.empty:
            st.warning("No hay ventas registradas.")
        else:
            seleccion = st.selectbox("🔍 Seleccione Lote / Cliente:", ["--"] + df_v["display_vta"].tolist())
            
            if seleccion != "--":
                # Extraemos la fila de la venta seleccionada
                v = df_v[df_v['display_vta'] == seleccion].iloc[0]
                venta_id_real = int(v['id'])
                ubicacion_id_real = int(v['ubicacion_id'])
                
                # Consultamos la vista de estatus usando el ubicacion_id
                res_status = supabase.table("vista_estatus_lotes").select("*").eq("ubicacion_id", ubicacion_id_real).execute()
                
                if res_status.data:
                    status = res_status.data[0]
                    
                    # --- CÁLCULOS ---
                    precio_total = float(v['ubicacion']['precio'] or 0)
                    eng_req = float(v['ubicacion']['enganche_req'] or 0)
                    total_pagado = float(status.get('total_pagado') or 0)
                    plazo_real = int(v.get('plazo') or 1)
                    
                    faltante_eng = max(0.0, eng_req - total_pagado)
                    saldo_total = max(0.0, precio_total - total_pagado)
                    monto_a_financiar = precio_total - eng_req
                    mensualidad = monto_a_financiar / plazo_real if plazo_real > 0 else 0
                    pago_sugerido = faltante_eng if faltante_eng > 0 else mensualidad

                    # --- UI DE ESTADO ---
                    st.markdown(f"""
                    <div style="background-color: #1E1E1E; padding: 20px; border-radius: 12px; border: 1px solid #333;">
                        <small style="color: #808495;">ID VENTA: {venta_id_real}</small>
                        <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px; margin-top: 10px;">
                            <div style="text-align: center;">
                                <p style="color: #808495; font-size: 0.7rem; margin:0;">PENDIENTE ENGANCHE</p>
                                <h4 style="color: {'#FF4B4B' if faltante_eng > 0 else '#00C853'}; margin:0;">${faltante_eng:,.2f}</h4>
                            </div>
                            <div style="text-align: center;">
                                <p style="color: #808495; font-size: 0.7rem; margin:0;">SALDO TOTAL</p>
                                <h4 style="color: white; margin:0;">${saldo_total:,.2f}</h4>
                            </div>
                            <div style="text-align: center;">
                                <p style="color: #808495; font-size: 0.7rem; margin:0;">MENSUALIDAD</p>
                                <h4 style="color: white; margin:0;">${mensualidad:,.2f}</h4>
                            </div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                    with st.form("form_pago_final", clear_on_submit=True):
                        c1, c2 = st.columns(2)
                        f_fol = c1.text_input("Folio Recibo")
                        f_mon = c2.number_input("Monto ($)", min_value=0.0, value=float(pago_sugerido))
                        f_com = st.text_area("Notas")
                        
                        if st.form_submit_button("✅ CONFIRMAR PAGO", type="primary", use_container_width=True):
                            try:
                                # INSERTAMOS USANDO EL ID DE LA VENTA
                                supabase.table("pagos").insert({
                                    "venta_id": venta_id_real,
                                    "monto": f_mon,
                                    "fecha": str(datetime.now().date()),
                                    "folio": f_fol,
                                    "comentarios": f_com
                                }).execute()
                                st.success("Pago guardado correctamente.")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error técnico al insertar: {e}")

    with tab_historial:
        if not df_p.empty:
            # Join local para mostrar nombres en lugar de IDs
            df_show = df_p.merge(df_v[['id', 'display_vta']], left_on='venta_id', right_on='id', how='left')
            st.dataframe(df_show[['fecha', 'display_vta', 'monto', 'folio']], use_container_width=True, hide_index=True)
