import streamlit as st
import pandas as pd
from datetime import datetime

def render_comisiones(supabase):
    st.title("🎖️ Control de Comisiones")

    # --- 1. CARGA DE DATOS ---
    try:
        # Saldos generales desde la vista mágica
        res_saldos = supabase.table("vista_saldos_comisiones").select("*").execute()
        df_saldos = pd.DataFrame(res_saldos.data)

        # Historial de pagos realizados
        res_pagos = supabase.table("comisiones_pagadas").select("""
            *,
            vendedor:directorio!vendedor_id(nombre)
        """).order("fecha_pago", desc=True).execute()
        df_historial = pd.DataFrame(res_pagos.data)
        
    except Exception as e:
        st.error(f"Error: {e}")
        return

    tab_saldos, tab_pagar, tab_historial = st.tabs(["📊 Saldos", "💸 Registrar Pago", "📜 Historial"])

    with tab_saldos:
        st.subheader("Resumen de Deudas a Vendedores")
        if not df_saldos.empty:
            st.dataframe(
                df_saldos,
                column_config={
                    "vendedor_nombre": "Vendedor",
                    "comision_total": st.column_config.NumberColumn("Total Generado", format="$%,.2f"),
                    "comision_pagada": st.column_config.NumberColumn("Total Pagado", format="$%,.2f"),
                    "saldo_pendiente": st.column_config.NumberColumn("Saldo Pendiente", format="$%,.2f"),
                },
                use_container_width=True, hide_index=True
            )

    with tab_pagar:
        st.subheader("Registrar Salida de Efectivo")
        vendedores_con_saldo = df_saldos[df_saldos["saldo_pendiente"] > 0]
        
        if vendedores_con_saldo.empty:
            st.success("✅ No hay comisiones pendientes de pago.")
        else:
            v_sel = st.selectbox("Seleccione Vendedor:", vendedores_con_saldo["vendedor_nombre"].tolist())
            datos_v = vendedores_con_saldo[vendedores_con_saldo["vendedor_nombre"] == v_sel].iloc[0]
            
            # Tarjeta de diseño Dark Mode
            st.markdown(f"""
            <div style="background-color: #1E1E1E; padding: 20px; border-radius: 10px; border-left: 5px solid #00C853; border: 1px solid #333;">
                <p style="color: #808495; margin:0;">SALDO PENDIENTE</p>
                <h2 style="color: #FFFFFF; margin:0;">$ {datos_v['saldo_pendiente']:,.2f}</h2>
            </div>
            """, unsafe_allow_html=True)

            with st.form("form_pago_comision"):
                c1, c2 = st.columns(2)
                f_monto = c1.number_input("Monto a Pagar ($)", min_value=0.0, value=float(datos_v['saldo_pendiente']))
                f_ref = c2.text_input("Referencia (Ej: Transferencia SPEI)")
                f_com = st.text_area("Notas adicionales")
                
                if st.form_submit_button("✅ Registrar Pago de Comisión", type="primary"):
                    pago_data = {
                        "vendedor_id": int(datos_v['vendedor_id']),
                        "monto_pagado": f_monto,
                        "referencia": f_ref,
                        "fecha_pago": str(datetime.now().date())
                    }
                    supabase.table("comisiones_pagadas").insert(pago_data).execute()
                    st.success("Pago registrado exitosamente.")
                    st.rerun()

    with tab_historial:
        if not df_historial.empty:
            df_historial['vendedor_nom'] = df_historial['vendedor'].apply(lambda x: x['nombre'])
            st.dataframe(
                df_historial[["fecha_pago", "vendedor_nom", "monto_pagado", "referencia"]],
                use_container_width=True, hide_index=True
            )
