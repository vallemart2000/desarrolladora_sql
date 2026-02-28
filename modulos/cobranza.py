import streamlit as st
import pandas as pd
from datetime import datetime

def render_cobranza(supabase):
    st.title("💰 Gestión de Cobranza")
    
    # --- 1. CARGA DE DATOS ---
    try:
        # Ahora incluimos 'plazo' en la consulta de ventas
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

    # --- PESTAÑA 1: REGISTRAR PAGO ---
    with tab_pago:
        if df_v.empty:
            st.warning("No hay ventas registradas.")
        else:
            seleccion = st.selectbox("🔍 Seleccione Lote / Cliente:", ["--"] + df_v["display_vta"].tolist())
            
            if seleccion != "--":
                v = df_v[df_v['display_vta'] == seleccion].iloc[0]
                
                # Consultamos la vista de estatus para ver pagos acumulados
                res_status = supabase.table("vista_estatus_lotes").select("*").eq("ubicacion_id", v['ubicacion_id']).execute()
                
                if res_status.data:
                    status = res_status.data[0]
                    
                    # --- CÁLCULOS FINANCIEROS REALES ---
                    precio_total = float(v['ubicacion']['precio'] or 0)
                    eng_req = float(v['ubicacion']['enganche_req'] or 0)
                    total_pagado = float(status.get('total_pagado') or 0)
                    plazo_real = int(v.get('plazo') or 1) # Usamos el plazo de la BD
                    
                    # 1. Saldo de Enganche
                    faltante_eng = max(0.0, eng_req - total_pagado)
                    
                    # 2. Saldo Total del Contrato
                    saldo_total = max(0.0, precio_total - total_pagado)
                    
                    # 3. Mensualidad Real (Saldo después de enganche / Plazo)
                    monto_a_financiar = precio_total - eng_req
                    mensualidad = monto_a_financiar / plazo_real if plazo_real > 0 else 0
                    
                    # 4. Sugerencia de Pago Inteligente
                    pago_sugerido = faltante_eng if faltante_eng > 0 else mensualidad

                    # --- DISEÑO DE TARJETA PROFESIONAL ---
                    st.markdown(f"""
                    <div style="
                        background-color: #1E1E1E; 
                        padding: 24px; 
                        border-radius: 12px; 
                        border: 1px solid #333; 
                        margin-bottom: 25px;
                    ">
                        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 20px;">
                            <div>
                                <p style="color: #808495; margin: 0; font-size: 0.75rem; font-weight: 700; text-transform: uppercase;">Pendiente Enganche</p>
                                <h3 style="color: {'#FF4B4B' if faltante_eng > 0 else '#00C853'}; margin: 5px 0 0 0; font-size: 1.5rem;">$ {faltante_eng:,.2f}</h3>
                            </div>
                            <div>
                                <p style="color: #808495; margin: 0; font-size: 0.75rem; font-weight: 700; text-transform: uppercase;">Saldo Pendiente Total</p>
                                <h3 style="color: #FFFFFF; margin: 5px 0 0 0; font-size: 1.5rem;">$ {saldo_total:,.2f}</h3>
                            </div>
                            <div>
                                <p style="color: #808495; margin: 0; font-size: 0.75rem; font-weight: 700; text-transform: uppercase;">Mensualidad ({plazo_real} m)</p>
                                <h3 style="color: #FFFFFF; margin: 5px 0 0 0; font-size: 1.5rem;">$ {mensualidad:,.2f}</h3>
                            </div>
                        </div>
                        <div style="margin-top: 15px; padding-top: 15px; border-top: 1px solid #333; display: flex; align-items: center;">
                            <span style="background-color: #2E7D32; color: white; padding: 4px 12px; border-radius: 20px; font-size: 0.7rem; font-weight: bold; margin-right: 10px;">SUGERENCIA</span>
                            <p style="color: #00C853; margin: 0; font-size: 0.9rem;">
                                {'🎯 Cobrar saldo de enganche' if faltante_eng > 0 else '📅 Cobrar mensualidad corriente'}: <b>$ {pago_sugerido:,.2f}</b>
                            </p>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                    with st.form("form_pago_final"):
                        c1, c2 = st.columns(2)
                        f_fol = c1.text_input("Folio Físico / Recibo", placeholder="Ej: REC-001")
                        f_mon = c2.number_input("Monto a Recibir ($)", min_value=0.0, value=float(pago_sugerido), step=100.0)
                        f_com = st.text_area("Comentarios del pago", placeholder="Ej: Abono a mensualidad 1 de 36...")
                        
                        if st.form_submit_button("✅ Registrar Pago", type="primary", use_container_width=True):
                            try:
                                supabase.table("pagos").insert({
                                    "venta_id": int(v['id']),
                                    "monto": f_mon,
                                    "fecha": str(datetime.now().date()),
                                    "folio": f_fol,
                                    "comentarios": f_com
                                }).execute()
                                st.success(f"✅ Pago de ${f_mon:,.2f} registrado con éxito.")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error al registrar: {e}")

    # --- PESTAÑA 2: HISTORIAL ---
    with tab_historial:
        if not df_p.empty:
            df_show = df_p.merge(df_v[['id', 'display_vta']], left_on='venta_id', right_on='id', how='left')
            st.dataframe(
                df_show[['fecha', 'display_vta', 'monto', 'folio', 'comentarios']],
                column_config={
                    "display_vta": "Lote / Cliente",
                    "monto": st.column_config.NumberColumn("Importe", format="$%,.2f"),
                    "fecha": "Fecha de Cobro"
                },
                use_container_width=True, hide_index=True
            )
