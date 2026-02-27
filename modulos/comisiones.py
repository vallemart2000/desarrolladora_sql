import streamlit as st
import pandas as pd
from datetime import datetime

def render_comisiones(supabase):
    st.title("🎖️ Gestión de Comisiones")
    
    # --- CONFIGURACIÓN ---
    PORCENTAJE_COMISION = 0.03  # 3% (Puedes ajustarlo o traerlo de la DB)
    
    # --- 1. CARGA DE DATOS ---
    try:
        # Traemos ventas con el nombre del vendedor desde el directorio
        res_v = supabase.table("ventas").select("""
            precio_venta,
            vendedor:directorio!vendedor_id(id, nombre),
            cliente:directorio!cliente_id(nombre),
            ubicacion:ubicaciones(ubicacion_display)
        """).execute()
        df_v = pd.DataFrame(res_v.data)
        
        # Traemos pagos de comisiones realizados
        res_pc = supabase.table("pagos_comisiones").select("""
            *,
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
    # Aplanamos los nombres de los vendedores para facilitar el agrupamiento
    df_v['nombre_vendedor'] = df_v['vendedor'].apply(lambda x: x['nombre'])
    df_v['vendedor_id'] = df_v['vendedor'].apply(lambda x: x['id'])
    df_v['comision_vta'] = df_v['precio_venta'].astype(float) * PORCENTAJE_COMISION
    
    # Agrupamos lo devengado por ID y Nombre
    devengado = df_v.groupby(['vendedor_id', 'nombre_vendedor'])['comision_vta'].sum().reset_index()
    devengado.columns = ['ID', 'Vendedor', 'Total Devengado']

    # Agrupamos lo pagado
    if not df_pc.empty:
        df_pc['nombre_vendedor'] = df_pc['vendedor'].apply(lambda x: x['nombre'])
        pagado = df_pc.groupby('vendedor_id')['monto'].sum().reset_index()
        pagado.columns = ['ID', 'Total Pagado']
        resumen = pd.merge(devengado, pagado, on='ID', how='left').fillna(0)
    else:
        resumen = devengado.copy()
        resumen['Total Pagado'] = 0.0

    resumen['Saldo Pendiente'] = resumen['Total Devengado'] - resumen['Total Pagado']

    # --- 3. MÉTRICAS ---
    c1, c2, c3 = st.columns(3)
    c1.metric("💰 Comisiones Totales", f"$ {resumen['Total Devengado'].sum():,.2f}")
    c2.metric("💸 Total Pagado", f"$ {resumen['Total Pagado'].sum():,.2f}")
    c3.metric("⏳ Pendiente por Pagar", f"$ {resumen['Saldo Pendiente'].sum():,.2f}", 
              delta=f"{(resumen['Saldo Pendiente'].sum()/resumen['Total Devengado'].sum()*100):.1f}%" if resumen['Total Devengado'].sum() > 0 else None,
              delta_color="inverse")

    st.divider()

    # --- 4. FORMULARIO DE PAGO ---
    with st.expander("➕ Registrar Pago de Comisión"):
        with st.form("form_comision", clear_on_submit=True):
            col_v, col_m, col_f = st.columns(3)
            # El selector muestra nombres pero trabajamos con IDs
            v_dict = dict(zip(resumen['Vendedor'], resumen['ID']))
            v_sel_nombre = col_v.selectbox("Seleccionar Vendedor", list(v_dict.keys()))
            
            # Sugerir el saldo pendiente como monto de pago
            saldo_sugerido = resumen[resumen['Vendedor'] == v_sel_nombre]['Saldo Pendiente'].values[0]
            
            m_pago = col_m.number_input("Monto ($)", min_value=0.0, value=float(saldo_sugerido), step=100.0)
            f_pago = col_f.date_input("Fecha de Pago", datetime.now())
            nota = st.text_input("Nota / Referencia", placeholder="Ej. Pago parcial lote M01-L05")
            
            if st.form_submit_button("Confirmar Pago de Comisión", type="primary"):
                if m_pago <= 0:
                    st.error("El monto debe ser mayor a cero.")
                else:
                    try:
                        data_pago = {
                            "vendedor_id": int(v_dict[v_sel_nombre]),
                            "monto": m_pago,
                            "fecha": str(f_pago),
                            "nota": nota
                        }
                        supabase.table("pagos_comisiones").insert(data_pago).execute()
                        st.success(f"✅ Pago de $ {m_pago:,.2f} registrado para {v_sel_nombre}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al registrar pago: {e}")

    # --- 5. VISUALIZACIÓN ---
    t1, t2 = st.tabs(["📊 Resumen General", "📜 Detalle de Ventas e Historial"])
    
    with t1:
        st.dataframe(
            resumen[['Vendedor', 'Total Devengado', 'Total Pagado', 'Saldo Pendiente']],
            column_config={
                "Total Devengado": st.column_config.NumberColumn(format="$ %.2f"),
                "Total Pagado": st.column_config.NumberColumn(format="$ %.2f"),
                "Saldo Pendiente": st.column_config.NumberColumn(format="$ %.2f"),
            },
            use_container_width=True,
            hide_index=True
        )

    with t2:
        col_a, col_b = st.columns(2)
        with col_a:
            st.subheader("🏆 Ventas por Vendedor")
            df_rank = df_v.copy()
            df_rank['Lote'] = df_rank['ubicacion'].apply(lambda x: x['ubicacion_display'])
            df_rank['Cliente'] = df_rank['cliente'].apply(lambda x: x['nombre'])
            
            st.dataframe(
                df_rank[['nombre_vendedor', 'Lote', 'comision_vta']],
                column_config={
                    "nombre_vendedor": "Vendedor",
                    "comision_vta": st.column_config.NumberColumn("Comisión", format="$ %.2f")
                },
                use_container_width=True, hide_index=True
            )
        
        with col_b:
            st.subheader("📜 Últimos Pagos Realizados")
            if not df_pc.empty:
                df_hist = df_pc.copy()
                df_hist['Vendedor'] = df_hist['vendedor'].apply(lambda x: x['nombre'])
                st.dataframe(
                    df_hist[['fecha', 'Vendedor', 'monto', 'nota']].sort_values('fecha', ascending=False),
                    column_config={"monto": st.column_config.NumberColumn(format="$ %.2f")},
                    use_container_width=True, hide_index=True
                )
            else:
                st.info("No hay historial de pagos.")
