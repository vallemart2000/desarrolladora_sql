import streamlit as st
import pandas as pd
from datetime import datetime

def render_comisiones(supabase):
    st.title("🎖️ Gestión de Comisiones")
    
    # --- 1. CARGA DE DATOS ---
    try:
        # Traemos ventas: Ahora incluimos explícitamente 'comision_monto'
        res_v = supabase.table("ventas").select("""
            id,
            comision_monto,
            vendedor:directorio!vendedor_id(id, nombre),
            cliente:directorio!cliente_id(nombre),
            ubicacion:ubicaciones(ubicacion_display)
        """).execute()
        df_v = pd.DataFrame(res_v.data)
        
        # Traemos pagos de comisiones realizados
        res_pc = supabase.table("pagos_comisiones").select("""
            id,
            vendedor_id,
            monto,
            fecha,
            nota,
            vendedor:directorio!vendedor_id(nombre)
        """).execute()
        df_pc = pd.DataFrame(res_pc.data)
        
    except Exception as e:
        st.error(f"Error en la base de datos: {e}")
        return

    if df_v.empty:
        st.warning("No hay ventas registradas para calcular comisiones.")
        return

    # --- 2. PROCESAMIENTO ---
    # Extraemos datos de los objetos anidados
    df_v['nombre_vendedor'] = df_v['vendedor'].apply(lambda x: x['nombre'])
    df_v['vendedor_id'] = df_v['vendedor'].apply(lambda x: x['id'])
    
    # IMPORTANTE: Ahora usamos el valor real guardado en la DB
    df_v['comision_vta'] = df_v['comision_monto'].astype(float)
    
    # Agrupamos lo devengado por Vendedor
    devengado = df_v.groupby(['vendedor_id', 'nombre_vendedor'])['comision_vta'].sum().reset_index()
    devengado.columns = ['ID', 'Vendedor', 'Total Devengado']

    # Agrupamos lo pagado
    if not df_pc.empty:
        pagado = df_pc.groupby('vendedor_id')['monto'].sum().reset_index()
        pagado.columns = ['ID', 'Total Pagado']
        resumen = pd.merge(devengado, pagado, on='ID', how='left').fillna(0)
    else:
        resumen = devengado.copy()
        resumen['Total Pagado'] = 0.0

    resumen['Saldo Pendiente'] = resumen['Total Devengado'] - resumen['Total Pagado']

    # --- 3. MÉTRICAS ---
    c1, c2, c3 = st.columns(3)
    total_dev = resumen['Total Devengado'].sum()
    total_pag = resumen['Total Pagado'].sum()
    
    c1.metric("💰 Comisiones Totales", f"$ {total_dev:,.2f}")
    c2.metric("💸 Total Pagado", f"$ {total_pag:,.2f}")
    c3.metric("⏳ Pendiente por Pagar", f"$ {resumen['Saldo Pendiente'].sum():,.2f}", 
              delta=f"{(resumen['Saldo Pendiente'].sum()/total_dev*100):.1f}%" if total_dev > 0 else None,
              delta_color="inverse")

    st.divider()

    # --- 4. FORMULARIO DE PAGO ---
    with st.expander("➕ Registrar Pago de Comisión"):
        with st.form("form_comision", clear_on_submit=True):
            col_v, col_m, col_f = st.columns(3)
            v_dict = dict(zip(resumen['Vendedor'], resumen['ID']))
            v_sel_nombre = col_v.selectbox("Seleccionar Vendedor", list(v_dict.keys()))
            
            row_v = resumen[resumen['Vendedor'] == v_sel_nombre]
            saldo_sugerido = float(row_v['Saldo Pendiente'].values[0]) if not row_v.empty else 0.0
            
            m_pago = col_m.number_input("Monto ($)", min_value=0.0, value=saldo_sugerido, step=100.0)
            f_pago = col_f.date_input("Fecha de Pago", datetime.now())
            nota = st.text_input("Nota / Referencia")
            
            if st.form_submit_button("Confirmar Pago", type="primary"):
                try:
                    supabase.table("pagos_comisiones").insert({
                        "vendedor_id": int(v_dict[v_sel_nombre]),
                        "monto": m_pago,
                        "fecha": str(f_pago),
                        "nota": nota
                    }).execute()
                    st.success("✅ Pago registrado correctamente.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")

    # --- 5. VISUALIZACIÓN ---
    t1, t2 = st.tabs(["📊 Resumen General", "📜 Detalle por Venta"])
    
    with t1:
        st.dataframe(resumen[['Vendedor', 'Total Devengado', 'Total Pagado', 'Saldo Pendiente']], 
                     use_container_width=True, hide_index=True)

    with t2:
        df_rank = df_v.copy()
        df_rank['Lote'] = df_rank['ubicacion'].apply(lambda x: x['ubicacion_display'])
        df_rank['Cliente'] = df_rank['cliente'].apply(lambda x: x['nombre'])
        st.dataframe(df_rank[['nombre_vendedor', 'Lote', 'Cliente', 'comision_vta']], 
                     column_config={"comision_vta": st.column_config.NumberColumn("Comisión ($)", format="$ %.2f")},
                     use_container_width=True, hide_index=True)
