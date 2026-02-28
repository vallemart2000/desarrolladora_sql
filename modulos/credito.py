import streamlit as st
import pandas as pd
from datetime import datetime
from dateutil.relativedelta import relativedelta

def render_detalle_credito(supabase):
    # Estilo CSS para mejorar el Dark Mode
    st.markdown("""
        <style>
        .main { background-color: #0E1117; }
        .stMetric {
            background-color: #1E2129;
            padding: 15px;
            border-radius: 10px;
            border: 1px solid #31333F;
        }
        [data-testid="stExpander"] {
            border: 1px solid #31333F;
            border-radius: 10px;
        }
        .status-card {
            background-color: #1E2129;
            padding: 20px;
            border-radius: 12px;
            border-left: 5px solid #4CAF50;
            margin-bottom: 20px;
        }
        </style>
    """, unsafe_allow_html=True)

    st.title("📊 Detalle de Crédito")

    # --- 1. CARGA DE DATOS ---
    try:
        res_v = supabase.table("ventas").select("""
            *,
            cliente:directorio!cliente_id(nombre),
            ubicacion:ubicaciones(id, manzana, lote, etapa, precio, enganche_req)
        """).execute()
        df_v = pd.DataFrame(res_v.data)
        
        res_status = supabase.table("vista_estatus_lotes").select("*").execute()
        df_status = pd.DataFrame(res_status.data)
    except Exception as e:
        st.error(f"Error cargando datos: {e}")
        return

    if df_v.empty:
        st.warning("No hay ventas registradas.")
        return

    # --- 2. SELECTOR VISUAL ---
    df_v['Lote_Ref'] = df_v['ubicacion'].apply(lambda x: f"M{int(x['manzana']):02d}-L{int(x['lote']):02d} (Etapa {x['etapa']})")
    df_v['Cliente_Nom'] = df_v['cliente'].apply(lambda x: x['nombre'])
    
    col_search, col_spacer = st.columns([2, 1])
    search_cred = col_search.text_input("🔍 Buscar cliente o lote:", placeholder="Nombre o Manzana...")
    
    df_sel = df_v.copy()
    if search_cred:
        df_sel = df_sel[df_sel['Cliente_Nom'].str.contains(search_cred, case=False) | 
                        df_sel['Lote_Ref'].str.contains(search_cred, case=False)]

    event = st.dataframe(
        df_sel[['Lote_Ref', 'Cliente_Nom']],
        column_config={"Lote_Ref": "Ubicación", "Cliente_Nom": "Cliente"},
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        key="credito_selector_table"
    )

    # --- 3. DASHBOARD DE ESTADO DE CUENTA ---
    if len(event.selection.rows) > 0:
        idx = event.selection.rows[0]
        v_selected = df_sel.iloc[idx]
        u_id = v_selected['ubicacion_id']

        precio_vta = float(v_selected['ubicacion']['precio'])
        e_requerido = float(v_selected['ubicacion']['enganche_req'])
        plazo_meses = int(v_selected.get('plazo') or 12)
        
        v_status = df_status[df_status['ubicacion_id'] == u_id]
        total_pagado_hoy = float(v_status['total_pagado'].iloc[0] if not v_status.empty else 0)
        saldo_restante = max(0.0, precio_vta - total_pagado_hoy)

        st.markdown(f"""
            <div class="status-card">
                <p style="margin:0; color: #808495; font-size: 0.9rem;">CONTRATO ACTIVO</p>
                <h2 style="margin:0; color: white;">{v_selected['Lote_Ref']}</h2>
                <p style="margin:0; color: #4CAF50;">{v_selected['Cliente_Nom']}</p>
            </div>
        """, unsafe_allow_html=True)
        
        m1, m2, m3 = st.columns(3)
        m1.metric("Valor Total", f"${precio_vta:,.2f}")
        m2.metric("Total Pagado", f"${total_pagado_hoy:,.2f}", f"{int((total_pagado_hoy/precio_vta)*100)}%")
        m3.metric("Saldo Restante", f"${saldo_restante:,.2f}", f"-${total_pagado_hoy:,.2f}", delta_color="inverse")

        # --- 4. TABLA DE AMORTIZACIÓN ---
        st.markdown("### 📅 Plan de Pagos")
        
        mensualidad_base = (precio_vta - e_requerido) / plazo_meses if plazo_meses > 0 else 0
        bolsa_para_mensualidades = max(0.0, total_pagado_hoy - e_requerido)
        
        datos_amort = []
        saldo_insoluto = precio_vta - e_requerido
        fecha_inicio = pd.to_datetime(v_selected['fecha_venta'])

        for i in range(1, plazo_meses + 1):
            fecha_pago = fecha_inicio + relativedelta(months=i)
            
            if bolsa_para_mensualidades >= (mensualidad_base - 0.05):
                status_pago = "✅ Cubierto"
                abono = mensualidad_base
                bolsa_para_mensualidades -= mensualidad_base
            elif bolsa_para_mensualidades > 0:
                status_pago = "⚠️ Parcial"
                abono = bolsa_para_mensualidades
                bolsa_para_mensualidades = 0
            else:
                status_pago = "⏳ Pendiente"
                abono = 0.0
                
            saldo_insoluto = max(0.0, saldo_insoluto - abono)
            
            datos_amort.append({
                "Mes": f"Mes {i:02d}",
                "Vencimiento": fecha_pago.strftime('%d/%m/%Y'),
                "Cuota": mensualidad_base,
                "Abonado": abono,
                "Saldo": saldo_insoluto,
                "Estatus": status_pago
            })

        st.dataframe(
            pd.DataFrame(datos_amort),
            column_config={
                "Cuota": st.column_config.NumberColumn(format="$,.2f"),
                "Abonado": st.column_config.NumberColumn(format="dollar"),
                "Saldo": st.column_config.NumberColumn(format="dollar"),
                "Estatus": st.column_config.TextColumn("Estatus")
            },
            use_container_width=True,
            hide_index=True
        )

        with st.expander("🧾 Historial de Pagos (Folios)"):
            res_p = supabase.table("pagos").select("*").eq("venta_id", v_selected['id']).order("fecha").execute()
            df_recibos = pd.DataFrame(res_p.data)
            if not df_recibos.empty:
                st.dataframe(df_recibos[['fecha', 'folio', 'monto']], use_container_width=True, hide_index=True)
            else:
                st.info("No hay recibos registrados.")
    else:
        st.info("💡 Selecciona un contrato de la lista superior para visualizar el estado de cuenta detallado.")
