import streamlit as st
import pandas as pd
from datetime import datetime

def render_cobranza(supabase):
    st.title("💰 Gestión de Cobranza")
    
    # --- 1. CARGA DE DATOS ---
    try:
        # Traemos ventas con sus relaciones
        res_v = supabase.table("ventas").select("""
            id, ubicacion_id, cliente_id,
            cliente:directorio!cliente_id(nombre),
            ubicacion:ubicaciones(id, etapa, manzana, lote, precio, enganche_req)
        """).execute()
        df_v = pd.DataFrame(res_v.data)
        
        # Traemos pagos (Nota: usamos 'venta_id' si ya renombraste la columna)
        res_p = supabase.table("pagos").select("*").order("fecha", desc=True).execute()
        df_p = pd.DataFrame(res_p.data)

        if not df_v.empty:
            df_v['display_vta'] = df_v.apply(
                lambda x: f"M{int(x['ubicacion']['manzana']):02d}-L{int(x['ubicacion']['lote']):02d} | {x['cliente']['nombre']}", 
                axis=1
            )
        
    except Exception as e:
        st.error(f"⚠️ Error de datos: {e}")
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
                
                # Consultamos la vista para ver el saldo
                res_status = supabase.table("vista_estatus_lotes").select("total_pagado, enganche_req").eq("ubicacion_id", v['ubicacion_id']).execute()
                
                if res_status.data:
                    status = res_status.data[0]
                    faltante = max(0.0, float(status['enganche_req']) - float(status['total_pagado'] or 0))
                    
                    st.metric("Faltante para Enganche", f"$ {faltante:,.2f}")

                    with st.form("form_pago_final"):
                        c1, c2 = st.columns(2)
                        f_fol = c1.text_input("Folio Físico / Recibo")
                        f_mon = c2.number_input("Monto a Recibir ($)", min_value=0.0, value=faltante if faltante > 0 else 5000.0)
                        f_com = st.text_area("Comentarios del pago")
                        
                        if st.form_submit_button("✅ Guardar Pago", type="primary"):
                            pago_data = {
                                "venta_id": int(v['id']), # Asegúrate de que se llame venta_id en SQL
                                "monto": f_mon,
                                "fecha": str(datetime.now().date()),
                                "folio": f_fol,
                                "comentarios": f_com
                            }
                            try:
                                supabase.table("pagos").insert(pago_data).execute()
                                st.success("✅ ¡Pago registrado y saldo actualizado!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error al insertar: {e}")

    # --- PESTAÑA 2: HISTORIAL ---
    with tab_historial:
        if not df_p.empty:
            # Unión en Python para mostrar nombres en lugar de IDs
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
