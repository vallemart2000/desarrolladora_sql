import streamlit as st
import pandas as pd
from datetime import datetime
import urllib.parse
import re

def render_inicio(supabase):
    st.title("🏠 Panel de Control y Cartera")

    # --- 1. CARGA DE DATOS (Columnas Explícitas) ---
    try:
        # Agregamos 'enganche_pagado', 'precio_venta' y 'mensualidad' al select
        res_v = supabase.table("ventas").select("""
            id,
            fecha_venta,
            precio_venta,
            enganche_pagado,
            mensualidad,
            cliente_id,
            estatus_venta,
            ubicacion_id,
            cliente:directorio!cliente_id(nombre, telefono, correo),
            ubicacion:ubicaciones(id, manzana, lote, etapa)
        """).execute()
        
        res_p = supabase.table("pagos").select("monto").execute()
        
        df_v = pd.DataFrame(res_v.data)
        df_p = pd.DataFrame(res_p.data)
    except Exception as e:
        st.error(f"🚨 Error en la carga de datos: {e}")
        return

    if df_v.empty:
        st.info("👋 ¡Bienvenido! Aún no hay ventas registradas.")
        return

    # --- 2. PREPARACIÓN DE DATOS ---
    # Formateo de Lote y Cliente
    df_v['Lote_Ref'] = df_v['ubicacion'].apply(lambda x: f"M{int(x['manzana']):02d}-L{int(x['lote']):02d} (E{x['etapa']})")
    df_v['Cliente_Nom'] = df_v['cliente'].apply(lambda x: x['nombre'] if x else "Sin Nombre")

    # --- 3. MÉTRICAS PRINCIPALES ---
    # Ingresos = Enganches + Abonos mensuales
    total_recaudado = df_v["enganche_pagado"].fillna(0).sum() + (df_p["monto"].sum() if not df_p.empty else 0)
    
    # Solo ventas que no estén canceladas
    df_activos = df_v[df_v['estatus_venta'] != 'Cancelado']
    valor_cartera = df_activos['precio_venta'].sum()
    clientes_activos = df_activos['cliente_id'].nunique()
    
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("💰 Ingresos Totales", f"$ {total_recaudado:,.2f}")
    m2.metric("👥 Clientes Activos", clientes_activos)
    m3.metric("📈 Valor Cartera", f"$ {valor_cartera:,.2f}")
    m4.metric("🏗️ Lotes Vendidos", len(df_activos))

    st.divider()

    # --- 4. LÓGICA DE COBRANZA (MORA) ---
    res_p_vta = supabase.table("pagos").select("venta_id, monto").execute()
    df_p_vta = pd.DataFrame(res_p_vta.data)
    
    # Sumar pagos por cada venta
    if not df_p_vta.empty:
        pagos_sum = df_p_vta.groupby('venta_id')['monto'].sum().reset_index()
    else:
        pagos_sum = pd.DataFrame(columns=['venta_id', 'monto'])

    df_cartera = df_v.copy()
    df_cartera = df_cartera.merge(pagos_sum, left_on='id', right_on='venta_id', how='left').fillna({'monto': 0})
    
    hoy = datetime.now()

    def calc_mora(row):
        try:
            if not row['fecha_venta'] or row['estatus_venta'] == 'Cancelado': 
                return pd.Series([0, 0.0])
            
            f_ini = pd.to_datetime(row['fecha_venta'])
            # Diferencia de meses (simplificada)
            diff_meses = (hoy.year - f_ini.year) * 12 + (hoy.month - f_ini.month)
            mensualidad = float(row.get('mensualidad') or 0)
            
            if mensualidad <= 0: return pd.Series([0, 0.0])

            # Lo que debería llevar pagado en mensualidades
            deuda_esperada = max(0, diff_meses) * mensualidad
            pagado_mensualidades = float(row['monto']) 
            
            saldo_vencido = max(0.0, deuda_esperada - pagado_mensualidades)
            
            dias = 0
            if saldo_vencido > 1.0: # Tolerancia de $1
                # Estimación de días basado en la proporción de la mensualidad
                meses_pagados = pagado_mensualidades / mensualidad
                ultimo_vencimiento_cubierto = f_ini + pd.DateOffset(months=int(meses_pagados))
                dias = (hoy - ultimo_vencimiento_cubierto).days
            
            return pd.Series([max(0, dias), saldo_vencido])
        except:
            return pd.Series([0, 0.0])

    df_cartera[['atraso', 'monto_vencido']] = df_cartera.apply(calc_mora, axis=1)

    # --- 5. TABLA DE SEGUIMIENTO ---
    st.subheader("📋 Seguimiento de Cartera Vencida")
    
    c_f1, c_f2 = st.columns([1, 1])
    solo_mora = c_f1.toggle("⚠️ Filtrar solo clientes con adeudo", value=True)
    busqueda = c_f2.text_input("🔍 Buscar por nombre o lote:")

    df_viz = df_cartera.copy()
    if solo_mora: 
        df_viz = df_viz[df_viz['monto_vencido'] > 1.0]
    
    if busqueda:
        df_viz = df_viz[df_viz['Cliente_Nom'].str.contains(busqueda, case=False) | 
                        df_viz['Lote_Ref'].str.contains(busqueda, case=False)]

    if not df_viz.empty:
        df_viz = df_viz.sort_values("atraso", ascending=False)
        
        # Etiquetado de estatus
        def get_status_label(dias):
            if dias > 60: return "🔴 Crítico (+60)"
            if dias > 0: return "🟡 Mora"
            return "🟢 Al día"
            
        df_viz['Estatus'] = df_viz['atraso'].apply(get_status_label)

        # Generar links de WhatsApp
        def get_wa_link(row):
            try:
                tel = re.sub(r'\D', '', str(row['cliente']['telefono']))
                tel_final = tel if tel.startswith("52") else "52" + tel
                msg = f"Hola {row['Cliente_Nom']}, te saludamos de Valle Mart. 📲 Notamos un saldo pendiente en tu lote {row['Lote_Ref']} por ${row['monto_vencido']:,.2f}. ¿Podrías apoyarnos con tu comprobante?"
                return f"https://wa.me/{tel_final}?text={urllib.parse.quote(msg)}"
            except: return None

        df_viz['WhatsApp'] = df_viz.apply(get_wa_link, axis=1)

        st.dataframe(
            df_viz[["Estatus", "Lote_Ref", "Cliente_Nom", "atraso", "monto_vencido", "WhatsApp"]],
            column_config={
                "Lote_Ref": "Lote",
                "Cliente_Nom": "Cliente",
                "atraso": st.column_config.NumberColumn("Días Atraso"),
                "monto_vencido": st.column_config.NumberColumn("Monto Vencido", format="$%,.2f"),
                "WhatsApp": st.column_config.LinkColumn("📲 Enviar Recordatorio", display_text="WhatsApp")
            },
            use_container_width=True, 
            hide_index=True
        )
    else:
        st.success("🎉 No hay deudas pendientes por mostrar.")
