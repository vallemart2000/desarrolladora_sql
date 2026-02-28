import streamlit as st
import pandas as pd
from datetime import datetime
import urllib.parse
import re

def render_inicio(supabase):
    # --- CSS AVANZADO PARA DARK MODE LIMPIO ---
    st.markdown("""
        <style>
        /* Fondo general y eliminación de espacios blancos */
        .main { background-color: #0E1117; }
        
        /* Estilizar métricas para que no parezcan cajas blancas */
        [data-testid="stMetric"] {
            background-color: #1E2129;
            border: 1px solid #31333F;
            padding: 15px 20px;
            border-radius: 12px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        
        /* Ajustar texto de métricas */
        [data-testid="stMetricValue"] { color: #00FFAA !important; font-size: 1.6rem !important; }
        [data-testid="stMetricLabel"] { color: #A0AEC0 !important; font-weight: 500; }

        /* Estilizar la tabla (Streamlit Dataframe) */
        .stDataFrame {
            border: 1px solid #31333F;
            border-radius: 12px;
            overflow: hidden;
        }

        /* Input de búsqueda y Toggles */
        .stTextInput input {
            background-color: #1E2129 !important;
            border: 1px solid #31333F !important;
            color: white !important;
            border-radius: 8px;
        }
        
        /* Divisores sutiles */
        hr { border: 0; border-top: 1px solid #31333F; margin: 2rem 0; }
        </style>
    """, unsafe_allow_html=True)

    st.title("🏠 Panel de Control")

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

    # --- 2. MÉTRICAS CON ESTILO ---
    total_recaudado = df_p["monto"].sum() if not df_p.empty else 0.0
    df_v['valor_lote'] = df_v['ubicacion'].apply(lambda x: float(x['precio']) if x else 0.0)
    total_cartera = df_v['valor_lote'].sum()
    
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("💰 Recaudación", f"$ {total_recaudado:,.0f}")
    m2.metric("👥 Clientes", df_v['cliente_id'].nunique())
    m3.metric("📈 Valor Cartera", f"$ {total_cartera:,.0f}")
    m4.metric("🏗️ Lotes Vendidos", len(df_v))

    st.markdown("<br>", unsafe_allow_html=True)

    # --- 3. ANÁLISIS DE CARTERA ---
    pagos_agrupados = df_p.groupby('venta_id')['monto'].sum().reset_index() if not df_p.empty else pd.DataFrame(columns=['venta_id', 'monto'])
    df_cartera = df_v.merge(pagos_agrupados, left_on='id', right_on='venta_id', how='left').fillna({'monto': 0})
    
    hoy = datetime.now()

    def calcular_mora(row):
        try:
            u = row['ubicacion']
            precio, enganche, plazo = float(u['precio']), float(u['enganche_req']), int(row['plazo'] or 12)
            mensualidad = (precio - enganche) / plazo if plazo > 0 else 0
            f_vta = pd.to_datetime(row['fecha_venta'])
            meses = (hoy.year - f_vta.year) * 12 + (hoy.month - f_vta.month)
            esperado = enganche + (max(0, meses) * mensualidad)
            pagado = float(row['monto'])
            saldo = max(0.0, esperado - pagado)
            
            dias = 0
            if saldo > 100:
                meses_c = (pagado - enganche) / mensualidad if mensualidad > 0 else 0
                vence = f_vta + pd.DateOffset(months=int(max(0, meses_c)) + 1)
                dias = (hoy - vence).days
            return pd.Series([max(0, dias), saldo])
        except: return pd.Series([0, 0.0])

    df_cartera[['atraso', 'monto_vencido']] = df_cartera.apply(calcular_mora, axis=1)

    # --- 4. INTERFAZ DE TABLA ---
    st.subheader("📋 Cobranza y Seguimiento")
    
    f1, f2 = st.columns([1, 2])
    solo_mora = f1.toggle("⚠️ Solo Deudores", value=True)
    busqueda = f2.text_input("🔍 Filtrar por nombre o lote...")

    df_cartera['Lote'] = df_cartera['ubicacion'].apply(lambda x: f"M{int(x['manzana']):02d}-L{int(x['lote']):02d}")
    df_cartera['Cliente'] = df_cartera['cliente'].apply(lambda x: x['nombre'] if x else "N/A")
    
    df_viz = df_cartera.copy()
    if solo_mora: df_viz = df_viz[df_viz['monto_vencido'] > 100]
    if busqueda:
        df_viz = df_viz[df_viz['Cliente'].str.contains(busqueda, case=False) | df_viz['Lote'].str.contains(busqueda, case=False)]

    if not df_viz.empty:
        df_viz = df_viz.sort_values("atraso", ascending=False)
        df_viz['Estatus'] = df_viz['atraso'].apply(lambda x: "🔴 Crítico" if x > 60 else ("🟡 Mora" if x > 0 else "🟢 Al día"))

        def get_wa(row):
            tel = re.sub(r'\D', '', str(row['cliente']['telefono']))
            tel_f = tel if tel.startswith("52") else "52" + tel
            msg = f"Hola {row['Cliente']}, te contactamos de Valle Mart por tu lote {row['Lote']}. Saldo: ${row['monto_vencido']:,.2f}."
            return f"https://wa.me/{tel_f}?text={urllib.parse.quote(msg)}"
        
        df_viz['WhatsApp'] = df_viz.apply(get_wa, axis=1)

        st.dataframe(
            df_viz[["Estatus", "Lote", "Cliente", "atraso", "monto_vencido", "WhatsApp"]],
            column_config={
                "atraso": st.column_config.NumberColumn("Días", format="%d d"),
                "monto_vencido": st.column_config.NumberColumn("Saldo", format="$ %,.2f"),
                "WhatsApp": st.column_config.LinkColumn("Acción", display_text="📲 Cobrar")
            },
            use_container_width=True, 
            hide_index=True
        )
    else:
        st.success("🎉 Sin adeudos pendientes.")
