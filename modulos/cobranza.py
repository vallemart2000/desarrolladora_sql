import streamlit as st
import pandas as pd
from datetime import datetime

def render_cobranza(supabase):
    st.title("💰 Gestión de Cobranza")
    
    # --- 1. CARGA DE DATOS ---
    try:
        # Traemos ventas con sus relaciones (usando columnas reales)
        res_v = supabase.table("ventas").select("""
            id, ubicacion_id, cliente_id,
            cliente:directorio!cliente_id(nombre),
            ubicacion:ubicaciones(id, etapa, manzana, lote, precio, enganche_req)
        """).execute()
        df_v = pd.DataFrame(res_v.data)
        
        # Traemos pagos
        res_p = supabase.table("pagos").select("*").order("fecha", desc=True).execute()
        df_p = pd.DataFrame(res_p.data)

        if not df_v.empty:
            # Reconstruimos el nombre visualmente en Python para evitar errores de SQL
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
                # Obtenemos la fila seleccionada
                v = df_v[df_v['display_vta'] == seleccion].iloc[0]
                
                # --- CORRECCIÓN CRÍTICA AQUÍ ---
                # Consultamos la vista usando 'ubicacion_id' (columna real) en lugar de 'ubicacion_display'
                res_status = supabase.table("vista_estatus_lotes").select("total_pagado, enganche_req").eq("ubicacion_id", v['ubicacion_id']).execute()
                
                if res_status.data:
                    status = res_status.data[0]
                    total_pag = float(status.get('total_pagado') or 0)
                    eng_req = float(status.get('enganche_req') or 0)
                    faltante = max(0.0, eng_req - total_pag)
                    
                    # Diseño Dark Mode para el saldo
                    st.markdown(f"""
                    <div style="background-color: #1E1E1E; padding: 24px; border-radius: 12px; border-left: 6px solid #FF4B4B; margin: 10px 0px 25px 0px; border: 1px solid #333;">
                        <p style="color: #808495; margin: 0; font-size: 0.85rem; font-weight: 700; text-transform: uppercase; letter-spacing: 1px;">Faltante para Enganche</p>
                        <h2 style="color: #FFFFFF; margin: 5px 0 0 0; font-size: 2.2rem; font-family: sans-serif;">$ {faltante:,.2f}</h2>
                    </div>
                    """, unsafe_allow_html=True)

                    with st.form("form_pago_final"):
                        c1, c2 = st.columns(2)
                        f_fol = c1.text_input("Folio Físico / Recibo", placeholder="Ej: A-1234")
                        f_mon = c2.number_input("Monto a Recibir ($)", min_value=0.0, value=faltante if faltante > 0 else 5000.0, step=100.0)
                        f_com = st.text_area("Comentarios del pago")
                        
                        if st.form_submit_button("✅ Guardar Pago", type="primary", use_container_width=True):
                            pago_data = {
                                "venta_id": int(v['id']),
                                "monto": f_mon,
                                "fecha": str(datetime.now().date()),
                                "folio": f_fol,
                                "comentarios": f_com
                            }
                            try:
                                supabase.table("pagos").insert(pago_data).execute()
                                st.success("✅ ¡Pago registrado exitosamente!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error al insertar: {e}")

    # --- PESTAÑA 2: HISTORIAL ---
    with tab_historial:
        if not df_p.empty:
            df_show = df_p.merge(df_v[['id', 'display_vta']], left_on='venta_id', right_on='id', how='left')
            st.dataframe(
                df_show[['fecha', 'display_vta', 'monto', 'folio', 'comentarios']],
                column_config={
                    "display_vta": "Lote / Cliente",
                    "monto": st.column_config.NumberColumn("Importe", format="$%,.2f"),
                    "fecha": "Fecha de Pago",
                    "folio": "Referencia/Folio"
                },
                use_container_width=True, hide_index=True
            )
