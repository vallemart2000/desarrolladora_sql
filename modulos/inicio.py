import streamlit as st
import pandas as pd
from datetime import datetime
import urllib.parse
import re

def render_inicio(supabase):
    # Estilo CSS para tarjetas Dark Mode
    st.markdown("""
        <style>
        [data-testid="stMetricValue"] { font-size: 1.8rem; color: #ffffff; }
        [data-testid="stMetricLabel"] { color: #808495; }
        .metric-card {
            background-color: #1E2129;
            padding: 15px;
            border-radius: 10px;
            border: 1px solid #31333F;
        }
        </style>
    """, unsafe_allow_html=True)

    st.title("🏠 Panel de Control y Cartera")

    # --- 1. CARGA DE DATOS ---
    try:
        res_v = supabase.table("ventas").select("""
            id, fecha_venta, plazo, cliente_id, ubicacion_id,
            cliente:directorio!cliente_id(nombre, telefono, correo),
            ubicacion:ubicaciones(id, manzana, lote, etapa, precio, enganche_req)
        """).execute()
        
        res_p = supabase.table("pagos").select("venta_id, monto").execute()
        
        df_v = pd.DataFrame(res_v.data)
        df_p = pd.DataFrame(res_p.data)
    except Exception as e:
        st.error(f"🚨 Error de conexión: {e}")
        return

    if df_v.empty:
        st.info("👋 El sistema está listo. Comienza registrando una venta.")
        return

    # --- 2. CÁLCULOS Y MÉTRICAS ---
    total_recaudado = df_p["monto"].sum() if not df_p.empty else 0.0
    df_v['valor_lote'] = df_v['ubicacion'].apply(lambda x: float(x['precio']) if x else 0.0)
    total_cartera = df_v['valor_lote'].sum()
    
    # Renderizado de Métricas en Tarjetas
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.metric("💰 Recaudación", f"$ {total_recaudado:,.2f}")
    with m2:
        st.metric("👥 Clientes", df_v['cliente_id'].nunique())
    with m3:
        st.metric("📈 Valor Cartera", f"$ {total_cartera:,.2f}")
    with m4:
        st.metric("🏗️ Lotes Vendidos", len(df_v))

    st.markdown("---")

    # --- 3. ANÁLISIS DE MORA ---
    pagos_agrupados = df_p.groupby('venta_id')['monto'].sum().reset_index() if not df_p.empty else pd.DataFrame(columns=['venta_id', 'monto'])
    df_cartera = df_v.merge(pagos_agrupados, left_on='id', right_on='venta_id', how='left').fillna({'monto': 0})
    
    hoy = datetime.now()

    def calcular_estado_cuenta(row):
        try:
            u = row['ubicacion']
            precio, enganche_req, plazo = float(u['precio']), float(u['enganche_req']), int(row['plazo'] or 12)
            mensualidad = (precio - enganche_req) / plazo if plazo > 0 else 0
            f_vta = pd.to_datetime(row['fecha_venta'])
            meses_transcurridos = (hoy.year - f_vta.year) * 12 + (hoy.month - f_vta.month)
            
            deuda_teorica = enganche_req + (max(0, meses_transcurridos) * mensualidad)
            pagado_real = float(row['monto'])
            saldo_vencido = max(0.0, deuda_teorica - pagado_real)
            
            dias_atraso = 0
            if saldo_vencido > 100:
                meses_cubiertos = (pagado_real - enganche_req) / mensualidad if mensualidad > 0 else 0
                vence = f_vta + pd.DateOffset(months=int(max(0, meses_cubiertos)) + 1)
                dias_atraso = (hoy - vence).days
            return pd.Series([max(0, dias_atraso), saldo_vencido])
        except: return pd.Series([0, 0.0])

    df_cartera[['atraso', 'monto_vencido']] = df_cartera.apply(calcular_estado_cuenta, axis=1)

    # --- 4. INTERFAZ DE COBRANZA ---
    st.subheader("📋 Gestión de Cobranza")
    
    col_f1, col_f2 = st.columns([1, 1])
    solo_mora = col_f1.toggle("⚠️ Filtrar deudores", value=True)
    busqueda = col_f2.text_input("🔍 Buscar cliente o lote:", placeholder="Ej. Manzana 2")

    df_cartera['Lote'] = df_cartera['ubicacion'].apply(lambda x: f"M{int(x['manzana']):02d}-L{int(x['lote']):02d} (E{x['etapa']})")
    df_cartera['Cliente'] = df_cartera['cliente'].apply(lambda x: x['nombre'] if x else "N/A")
    
    df_viz = df_cartera.copy()
    if solo_mora: df_viz = df_viz[df_viz['monto_vencido'] > 100]
    if busqueda:
        df_viz = df_viz[df_viz['Cliente'].str.contains(busqueda, case=False) | df_viz['Lote'].str.contains(busqueda, case=False)]

    if not df_viz.empty:
        df_viz = df_viz.sort_values("atraso", ascending=False)
        
        # Formateo de Estatus con colores para Dark Mode
        def style_status(atraso):
            if atraso > 60: return "🔴 Crítico (+60)"
            if atraso > 0: return "🟡 Mora"
            return "🟢 Al día"
        
        df_viz['Estatus'] = df_viz['atraso'].apply(style_status)

        def generar_wa(row):
            try:
                tel = re.sub(r'\D', '', str(row['cliente']['telefono']))
                tel_f = tel if tel.startswith("52") else "52" + tel
                msg = (f"Hola {row['Cliente']}, te contactamos de Valle Mart. 📲 "
                       f"Tu lote {row['Lote']} presenta un saldo pendiente de ${row['monto_vencido']:,.2f}. "
                       f"¿Podrías apoyarnos con tu comprobante?")
                return f"https://wa.me/{tel_f}?text={urllib.parse.quote(msg)}"
            except: return None
        
        df_viz['WhatsApp'] = df_viz.apply(generar_wa, axis=1)

        # Configuración de tabla optimizada para Dark Mode
        st.dataframe(
            df_viz[["Estatus", "Lote", "Cliente", "atraso", "monto_vencido", "WhatsApp"]],
            column_config={
                "atraso": st.column_config.NumberColumn("Días", help="Días de atraso"),
                "monto_vencido": st.column_config.NumberColumn("Deuda", format="$ %,.2f"),
                "WhatsApp": st.column_config.LinkColumn("📲 Contacto", display_text="Enviar WA")
            },
            use_container_width=True, 
            hide_index=True
        )
    else:
        st.success("🎉 Cartera al corriente.")
