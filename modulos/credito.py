import streamlit as st
import pandas as pd
from datetime import datetime
from dateutil.relativedelta import relativedelta

def render_detalle_credito(supabase):
    st.title("📊 Detalle de Crédito y Estado de Cuenta")

    # --- 1. CARGA DE DATOS (Ajustado a SQL Real) ---
    try:
        # Traemos ventas con los nombres de columna exactos de tus tablas
        res_v = supabase.table("ventas").select("""
            *,
            cliente:directorio!cliente_id(nombre),
            ubicacion:ubicaciones(id, manzana, lote, etapa, precio, enganche_req)
        """).execute()
        df_v = pd.DataFrame(res_v.data)
        
        # Traer la vista de estatus para saldos pagados acumulados
        res_status = supabase.table("vista_estatus_lotes").select("*").execute()
        df_status = pd.DataFrame(res_status.data)
        
    except Exception as e:
        st.error(f"Error cargando datos: {e}")
        return

    if df_v.empty:
        st.warning("No hay ventas registradas.")
        return

    # --- 2. SELECTOR DE CONTRATO ---
    st.subheader("1. Seleccione un Contrato")
    
    # Formateo de identificación del lote (MXX-LXX)
    df_v['Lote_Ref'] = df_v['ubicacion'].apply(lambda x: f"M{int(x['manzana']):02d}-L{int(x['lote']):02d} (E{x['etapa']})")
    df_v['Cliente_Nom'] = df_v['cliente'].apply(lambda x: x['nombre'])
    
    search_cred = st.text_input("🔍 Filtrar por nombre o lote:", placeholder="Ej: Manzana 05...")
    
    df_sel = df_v.copy()
    if search_cred:
        df_sel = df_sel[
            df_sel['Cliente_Nom'].str.contains(search_cred, case=False) | 
            df_sel['Lote_Ref'].str.contains(search_cred, case=False)
        ]

    # Tabla interactiva para seleccionar
    event = st.dataframe(
        df_sel[['Lote_Ref', 'Cliente_Nom']],
        column_config={"Lote_Ref": "Ubicación", "Cliente_Nom": "Cliente"},
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        key="credito_selector_table"
    )

    # --- 3. CÁLCULOS Y VISUALIZACIÓN ---
    if len(event.selection.rows) > 0:
        idx = event.selection.rows[0]
        v_selected = df_sel.iloc[idx]
        v_id = v_selected['id']
        u_id = v_selected['ubicacion_id']

        # Extraer valores monetarios del SQL de ubicaciones
        precio_vta = float(v_selected['ubicacion']['precio'])
        e_requerido = float(v_selected['ubicacion']['enganche_req'])
        plazo_meses = int(v_selected.get('plazo') or 12)
        
        # Obtener lo pagado hasta hoy desde la vista
        v_status = df_status[df_status['ubicacion_id'] == u_id]
        total_pagado_hoy = float(v_status['total_pagado'].iloc[0] if not v_status.empty else 0)

        st.divider()
        st.markdown(f"### 📋 Estado de Cuenta: {v_selected['Lote_Ref']}")
        
        # Dashboard de métricas rápidas
        m1, m2, m3 = st.columns(3)
        m1.metric("Valor del Lote", f"${precio_vta:,.2f}")
        m2.metric("Total Recaudado", f"${total_pagado_hoy:,.2f}")
        m3.metric("Saldo Restante", f"${max(0.0, precio_vta - total_pagado_hoy):,.2f}")

        # --- 4. TABLA DE AMORTIZACIÓN DINÁMICA ---
        st.subheader("📅 Plan de Pagos Mensual")
        
        # La mensualidad se calcula sobre el saldo insoluto (Precio - Enganche)
        mensualidad_base = (precio_vta - e_requerido) / plazo_meses if plazo_meses > 0 else 0
        
        # El dinero se aplica primero al enganche, el resto a mensualidades
        bolsa_para_mensualidades = max(0.0, total_pagado_hoy - e_requerido)
        
        datos_amort = []
        saldo_insoluto = precio_vta - e_requerido
        fecha_inicio = pd.to_datetime(v_selected['fecha_venta'])

        for i in range(1, plazo_meses + 1):
            fecha_pago = fecha_inicio + relativedelta(months=i)
            
            # Lógica de semáforo para el estatus de la mensualidad
            if bolsa_para_mensualidades >= (mensualidad_base - 0.05): # Margen para redondeo
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
                "Mes": i,
                "Fecha Venc.": fecha_pago.strftime('%d/%m/%Y'),
                "Cuota Sugerida": mensualidad_base,
                "Abonado": abono,
                "Saldo de Crédito": saldo_insoluto,
                "Estatus": status_pago
            })

        st.dataframe(
            pd.DataFrame(datos_amort),
            column_config={
                "Cuota Sugerida": st.column_config.NumberColumn(format="$ %.2f"),
                "Abonado": st.column_config.NumberColumn(format="$ %.2f"),
                "Saldo de Crédito": st.column_config.NumberColumn(format="$ %.2f"),
            },
            use_container_width=True,
            hide_index=True
        )

        # Sección de Recibos
        with st.expander("🧾 Historial de Folios Registrados"):
            res_p = supabase.table("pagos").select("*").eq("venta_id", v_id).order("fecha").execute()
            df_recibos = pd.DataFrame(res_p.data)
            if not df_recibos.empty:
                st.dataframe(df_recibos[['fecha', 'folio', 'monto']], use_container_width=True)
            else:
                st.info("No hay recibos individuales para este contrato.")
    else:
        st.info("💡 Haz clic en una fila de la tabla superior para generar el estado de cuenta.")
