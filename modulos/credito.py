import streamlit as st
import pandas as pd
from datetime import datetime
from dateutil.relativedelta import relativedelta

def render_detalle_credito(supabase):
    st.title("📊 Detalle de Crédito y Estado de Cuenta")

    # --- 1. CARGA DE DATOS RELACIONADOS ---
    try:
        # Traemos ventas con relaciones correctas (directorio y ubicaciones)
        res_v = supabase.table("ventas").select("""
            *,
            cliente:directorio!cliente_id(nombre),
            ubicacion:ubicaciones(ubicacion_display, enganche_requerido, precio_lista)
        """).execute()
        df_v = pd.DataFrame(res_v.data)
    except Exception as e:
        st.error(f"Error cargando ventas: {e}")
        return

    if df_v.empty:
        st.warning("No hay ventas registradas en el sistema.")
        return

    # --- 2. SELECTOR DE CONTRATO ---
    # Creamos el nombre para mostrar igual que en Cobranza
    df_v['display_name'] = df_v.apply(
        lambda x: f"{x['ubicacion']['ubicacion_display']} | {x['cliente']['nombre']}", 
        axis=1
    )
    
    opciones_vta = df_v["display_name"].tolist()
    seleccion = st.selectbox("🔍 Seleccione un Contrato para ver detalles:", opciones_vta)

    # Extraer datos del contrato seleccionado
    v = df_v[df_v["display_name"] == seleccion].iloc[0]
    v_id = v['id']

    # Traer todos los pagos asociados a esta venta específica
    res_p = supabase.table("pagos").select("*").eq("venta_id", v_id).order("fecha").execute()
    df_p_vta = pd.DataFrame(res_p.data)

    # --- 3. LÓGICA FINANCIERA ---
    # Usamos los nombres de columnas reales de tu base de datos
    precio_total_vta = float(v['precio_venta'])
    eng_req = float(v['ubicacion']['enganche_requerido'])
    eng_pag = float(v.get('enganche_pagado') or 0.0)
    
    # Si aún no hay mensualidad definida en la venta, calculamos una sugerida o evitamos el error
    # Nota: Asegúrate de que 'plazo_meses' exista en tu tabla ventas
    plazo = int(v.get('plazo_meses', 12)) 
    mensualidad_pactada = float(v.get('mensualidad') or 0.0)
    
    # Si la mensualidad es 0, intentamos calcularla (Precio - Enganche) / Plazo
    if mensualidad_pactada == 0 and plazo > 0:
        mensualidad_pactada = (precio_total_vta - eng_req) / plazo

    # Suma total de dinero recibido
    total_pagado_real = df_p_vta["monto"].sum() if not df_p_vta.empty else 0.0
    
    # Dinero que sobra tras cubrir el enganche y se va a mensualidades
    dinero_para_mensualidades = max(0.0, total_pagado_real - eng_req)

    # --- 4. CÁLCULO DE ATRASOS ---
    saldo_vencido = 0.0
    num_atrasos = 0
    
    # Solo calculamos atrasos si ya hay una fecha de contrato (cuando se cubrió el enganche)
    if v['fecha_contrato']:
        f_ini = pd.to_datetime(v['fecha_contrato'])
        hoy = datetime.now()
        
        # Diferencia de meses desde el contrato
        meses_transcurridos = (hoy.year - f_ini.year) * 12 + (hoy.month - f_ini.month)
        meses_a_cobrar = max(0, meses_transcurridos) 
        
        deuda_esperada = meses_a_cobrar * mensualidad_pactada
        saldo_vencido = max(0.0, deuda_esperada - dinero_para_mensualidades)
        num_atrasos = saldo_vencido / mensualidad_pactada if mensualidad_pactada > 0 else 0

    # --- 5. INTERFAZ: RESUMEN ---
    porcentaje_total = min(1.0, total_pagado_real / precio_total_vta) if precio_total_vta > 0 else 0
    
    st.markdown("### 📋 Resumen del Crédito")
    st.write(f"**Avance de Pago Total: {int(porcentaje_total * 100)}%**")
    st.progress(porcentaje_total)

    c1, c2, c3 = st.columns(3)
    with c1:
        st.write(f"**📍 Lote:** {v['ubicacion']['ubicacion_display']}")
        st.write(f"**👤 Cliente:** {v['cliente']['nombre']}")
        st.write(f"**📅 Contrato:** {pd.to_datetime(v['fecha_contrato']).strftime('%d/%m/%Y') if v['fecha_contrato'] else 'PENDIENTE (Apartado)'}")
    with c2:
        st.metric("Total Recaudado", f"$ {total_pagado_real:,.2f}")
        st.caption(f"Precio Venta: $ {precio_total_vta:,.2f}")
        st.write(f"**Enganche:** $ {eng_pag:,.2f} / $ {eng_req:,.2f}")
    with c3:
        color_delta = "inverse" if saldo_vencido > 0 else "normal"
        st.metric("Saldo Vencido", f"$ {saldo_vencido:,.2f}", 
                  delta=f"{int(num_atrasos)} meses" if num_atrasos >= 1 else "Al día", 
                  delta_color=color_delta)
        st.write(f"**Saldo Pendiente:** $ {max(0.0, precio_total_vta - total_pagado_real):,.2f}")

    st.divider()

    # --- 6. TABLA DE AMORTIZACIÓN DINÁMICA ---
    st.subheader("📅 Plan de Pagos Detallado")
    
    if not v['fecha_contrato']:
        st.info("ℹ️ El plan de pagos mensual se generará automáticamente una vez que el cliente cubra el total del enganche.")
    else:
        datos_amort = []
        saldo_capital = precio_total_vta - eng_req
        bolsa_pago = dinero_para_mensualidades 
        fecha_base = pd.to_datetime(v['fecha_contrato'])

        for i in range(1, plazo + 1):
            # La primera mensualidad es un mes después del contrato
            fecha_cuota = fecha_base + relativedelta(months=i)
            
            if bolsa_pago >= mensualidad_pactada:
                estatus = "✅ Pagado"
                abonado = mensualidad_pactada
                bolsa_pago -= mensualidad_pactada
            elif bolsa_pago > 0:
                estatus = "⚠️ Parcial"
                abonado = bolsa_pago
                bolsa_pago = 0
            else:
                estatus = "⏳ Pendiente"
                abonado = 0.0
                
            saldo_capital = max(0.0, saldo_capital - abonado)
            
            datos_amort.append({
                "No.": i,
                "Fecha": fecha_cuota.strftime('%d/%m/%Y'),
                "Cuota Esperada": mensualidad_pactada,
                "Abonado": abonado,
                "Saldo Capital": saldo_capital,
                "Estatus": estatus
            })

        st.dataframe(
            pd.DataFrame(datos_amort),
            column_config={
                "Cuota Esperada": st.column_config.NumberColumn(format="$ %.2f"),
                "Abonado": st.column_config.NumberColumn(format="$ %.2f"),
                "Saldo Capital": st.column_config.NumberColumn(format="$ %.2f"),
            },
            use_container_width=True,
            hide_index=True
        )
