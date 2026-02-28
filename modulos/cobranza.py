import streamlit as st
import pandas as pd
from datetime import datetime
import time

def render_cobranza(supabase):
    st.title("💰 Gestión de Cobranza")
    
    # --- 1. CARGA DE DATOS ---
    try:
        # Traemos ventas con sus relaciones
        res_v = supabase.table("ventas").select("""
            id, ubicacion_id, cliente_id, plazo,
            cliente:directorio!cliente_id(nombre),
            ubicacion:ubicaciones(id, etapa, manzana, lote, precio, enganche_req)
        """).execute()
        df_v = pd.DataFrame(res_v.data)
        
        # Traemos pagos
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
            # Usamos un key para el selectbox para poder resetearlo indirectamente
            seleccion = st.selectbox(
                "🔍 Seleccione Lote / Cliente:", 
                ["--"] + df_v["display_vta"].tolist(),
                key="venta_selector"
            )
            
            if seleccion != "--":
                v = df_v[df_v['display_vta'] == seleccion].iloc[0]
                venta_id_real = int(v['id'])
                ubicacion_id_real = int(v['ubicacion_id'])
                
                # RE-CONSULTA CRÍTICA: Traemos el estatus más reciente para evitar datos viejos
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

                    # --- UI DE ESTADO MEJORADA ---
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

                    # Formulario con clear_on_submit=True para limpiar campos automáticamente
                    with st.form("form_pago_final", clear_on_submit=True):
                        st.write("📝 **Detalles del Cobro**")
                        c1, c2 = st.columns(2)
                        f_fol = c1.text_input("Folio Recibo / Referencia", placeholder="Ej: REC-1024")
                        f_mon = c2.number_input("Monto a Recibir ($)", min_value=0.0, value=float(pago_sugerido), step=100.0)
                        f_com = st.text_area("Comentarios", placeholder="Abono correspondiente a...")
                        
                        btn_confirmar = st.form_submit_button("✅ REGISTRAR PAGO AHORA", type="primary", use_container_width=True)
                        
                        if btn_confirmar:
                            if f_mon <= 0:
                                st.error("❌ El monto debe ser mayor a 0")
                            else:
                                try:
                                    # 1. Insertar pago
                                    supabase.table("pagos").insert({
                                        "venta_id": venta_id_real,
                                        "monto": f_mon,
                                        "fecha": str(datetime.now().date()),
                                        "folio": f_fol,
                                        "comentarios": f_com
                                    }).execute()
                                    
                                    # 2. Notificación Visual Impactante
                                    st.toast(f"✅ ¡Pago de ${f_mon:,.2f} registrado con éxito!", icon="💰")
                                    st.success(f"🎊 EXCELENTE: Se registró el pago con folio {f_fol}. Los datos se han actualizado.")
                                    
                                    # 3. Pequeña pausa para que el usuario vea el éxito antes del rerun
                                    time.sleep(1.5)
                                    st.rerun()
                                    
                                except Exception as e:
                                    st.error(f"❌ Error al registrar: {e}")

    # --- PESTAÑA 2: HISTORIAL ---
    with tab_historial:
        if not df_p.empty:
            df_show = df_p.merge(df_v[['id', 'display_vta']], left_on='venta_id', right_on='id', how='left')
            st.dataframe(
                df_show[['fecha', 'display_vta', 'monto', 'folio', 'comentarios']],
                column_config={
                    "display_vta": "Lote / Cliente",
                    "monto": st.column_config.NumberColumn("Importe", format="$%,.2f"),
                    "fecha": "Fecha de Cobro",
                    "folio": "Recibo/Ref"
                },
                use_container_width=True, 
                hide_index=True
            )
