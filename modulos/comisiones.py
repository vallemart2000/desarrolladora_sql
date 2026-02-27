import streamlit as st
import pandas as pd
from datetime import datetime

def render_comisiones(supabase):
    st.title("🎖️ Gestión de Comisiones")
    
    # --- CONFIGURACIÓN ---
    PORCENTAJE_COMISION = 0.03  # 3%
    
    # 1. CARGA DE DATOS
    # Traemos ventas para calcular lo devengado
    res_v = supabase.table("ventas").select("vendedor, precio_total, clientes(nombre), ubicaciones(ubicacion)").execute()
    df_v = pd.DataFrame(res_v.data)
    
    # Traemos pagos de comisiones realizados
    res_pc = supabase.table("pagos_comisiones").select("*").execute()
    df_pc = pd.DataFrame(res_pc.data)

    if df_v.empty:
        st.warning("No hay ventas registradas para calcular comisiones.")
        return

    # --- 2. PROCESAMIENTO ---
    # Calculamos comisión por venta
    df_v['comision_vta'] = df_v['precio_total'].astype(float) * PORCENTAJE_COMISION
    
    # Agrupamos lo devengado por vendedor
    devengado = df_v.groupby('vendedor')['comision_vta'].sum().reset_index()
    devengado.columns = ['Vendedor', 'Total Devengado']

    # Agrupamos lo pagado por vendedor
    if not df_pc.empty:
        pagado = df_pc.groupby('vendedor')['monto'].sum().reset_index()
        pagado.columns = ['Vendedor', 'Total Pagado']
        resumen = pd.merge(devengado, pagado, on='Vendedor', how='left').fillna(0)
    else:
        resumen = devengado.copy()
        resumen['Total Pagado'] = 0.0

    resumen['Saldo Pendiente'] = resumen['Total Devengado'] - resumen['Total Pagado']

    # --- 3. MÉTRICAS ---
    c1, c2, c3 = st.columns(3)
    c1.metric("💰 Comisiones Totales", f"$ {resumen['Total Devengado'].sum():,.2f}")
    c2.metric("💸 Total Pagado", f"$ {resumen['Total Pagado'].sum():,.2f}")
    c3.metric("⏳ Pendiente por Pagar", f"$ {resumen['Saldo Pendiente'].sum():,.2f}", delta_color="inverse")

    st.divider()

    # --- 4. FORMULARIO DE PAGO ---
    with st.expander("➕ Registrar Pago de Comisión"):
        with st.form("form_comision"):
            col_v, col_m, col_f = st.columns(3)
            v_sel = col_v.selectbox("Vendedor", resumen['Vendedor'].unique())
            m_pago = col_m.number_input("Monto ($)", min_value=0.0, step=100.0)
            f_pago = col_f.date_input("Fecha", datetime.now())
            nota = st.text_input("Nota (ej. Pago lote 05)")
            
            if st.form_submit_button("Confirmar Pago"):
                data_pago = {
                    "vendedor": v_sel,
                    "monto": m_pago,
                    "fecha": str(f_pago),
                    "nota": nota
                }
                supabase.table("pagos_comisiones").insert(data_pago).execute()
                st.success(f"Pago registrado para {v_sel}")
                st.rerun()

    # --- 5. VISUALIZACIÓN ---
    st.subheader("📊 Estado de Cuenta por Vendedor")
    st.dataframe(
        resumen,
        column_config={
            "Total Devengado": st.column_config.NumberColumn(format="$ %.2f"),
            "Total Pagado": st.column_config.NumberColumn(format="$ %.2f"),
            "Saldo Pendiente": st.column_config.NumberColumn(format="$ %.2f"),
        },
        use_container_width=True,
        hide_index=True
    )

    t1, t2 = st.tabs(["🏆 Ranking Detallado", "📜 Historial de Pagos"])
    
    with t1:
        # Detalle de ventas para ver de dónde viene la comisión
        df_rank = df_v.copy()
        df_rank['Cliente'] = df_rank['clientes'].apply(lambda x: x['nombre'])
        df_rank['Lote'] = df_rank['ubicaciones'].apply(lambda x: x['ubicacion'])
        
        st.dataframe(
            df_rank[['vendedor', 'Lote', 'Cliente', 'precio_total', 'comision_vta']],
            column_config={
                "precio_total": st.column_config.NumberColumn("Venta", format="$ %.2f"),
                "comision_vta": st.column_config.NumberColumn("Comisión", format="$ %.2f")
            },
            use_container_width=True,
            hide_index=True
        )

    with t2:
        if not df_pc.empty:
            st.dataframe(
                df_pc[['fecha', 'vendedor', 'monto', 'nota']].sort_values('fecha', ascending=False),
                column_config={"monto": st.column_config.NumberColumn(format="$ %.2f")},
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("No hay pagos registrados.")
