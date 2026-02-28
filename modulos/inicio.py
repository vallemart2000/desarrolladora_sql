import streamlit as st
import pandas as pd
from datetime import datetime
import urllib.parse
import re

def render_inicio(supabase):
    st.title("🏠 Panel de Control y Cartera")

    # --- 1. CARGA DE DATOS (Basado en tu SQL Real) ---
    try:
        # Solo columnas que existen en tu tabla 'ventas'
        res_v = supabase.table("ventas").select("""
            id,
            fecha_venta,
            plazo,
            cliente_id,
            ubicacion_id,
            cliente:directorio!cliente_id(nombre, telefono, correo),
            ubicacion:ubicaciones(id, manzana, lote, etapa, precio, enganche_req)
        """).execute()
        
        # Traemos todos los pagos para saber qué se ha cobrado
        res_p = supabase.table("pagos").select("venta_id, monto, tipo").execute()
        
        df_v = pd.DataFrame(res_v.data)
        df_p = pd.DataFrame(res_p.data)
    except Exception as e:
        st.error(f"🚨 Error de base de datos: {e}")
        return

    if df_v.empty:
        st.info("👋 Aún no hay ventas registradas.")
        return

    # --- 2. PROCESAMIENTO DE PAGOS ---
    # Separamos enganches de abonos para métricas limpias
    enganches_total = df_p[df_p['tipo'] == 'Enganche']['monto'].sum() if not df_p.empty else 0
    abonos_total = df_p[df_p['tipo'] != 'Enganche']['monto'].sum() if not df_p.empty else 0
    
    # Suma de pagos totales por cada venta (para la tabla de cartera)
    pagos_por_venta = df_p.groupby('venta_id')['monto'].sum().reset_index() if not df_p.empty else pd.DataFrame(columns=['venta_id', 'monto'])

    # --- 3. MÉTRICAS PRINCIPALES ---
    df_v['valor_lote'] = df_v['ubicacion'].apply(lambda x: float(x['precio']) if x else 0.0)
    
    total_ingresos = enganches_total + abonos_total
    valor_cartera = df_v['valor_lote'].sum()
    clientes_activos = df_v['cliente_id'].nunique()
    
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("💰 Ingresos Totales", f"$ {total_ingresos:,.2f}")
    m2.metric("👥 Clientes", clientes_activos)
    m3.metric("📈 Valor Cartera", f"$ {valor_cartera:,.2f}")
    m4.metric("🏗️ Lotes Vendidos", len(df_v))

    st.divider()

    # --- 4. CÁLCULO DE MORA Y COBRANZA ---
    df_cartera = df_v.copy()
    df_cartera = df_cartera.merge(pagos_por_venta, left_on='id', right_on='venta_id', how='left').fillna({'monto': 0})
    
    hoy = datetime.now()

    def analizar_mora(row):
        try:
            u = row['ubicacion']
            precio = float(u['precio'])
            enganche_req = float(u['enganche_req'])
            plazo = int(row['plazo'] or 12)
            
            # Cálculo de mensualidad teórica
            mensualidad = (precio - enganche_req) / plazo if plazo > 0 else 0
            
            # ¿Cuántos meses han pasado desde la venta?
            f_vta = pd.to_datetime(row['fecha_venta'])
            meses_transcurridos = (hoy.year - f_vta.year) * 12 + (hoy.month - f_vta.month)
            
            # Deuda esperada: Enganche + (Meses * Mensualidad)
            deuda_esperada_total = enganche_req + (max(0, meses_transcurridos) * mensualidad)
            pagado_total = float(row['monto'])
            
            saldo_vencido = max(0.0, deuda_esperada_total - pagado_total)
            
            # Días de atraso aproximados
            dias = 0
            if saldo_vencido > 50: # Margen para ignorar diferencias mínimas
                # Calculamos en qué mes de pago debería ir
                meses_cubiertos = (pagado_total - enganche_req) / mensualidad if mensualidad > 0 else 0
                vencimiento_pendiente = f_vta + pd.DateOffset(months=int(max(0, meses_cubiertos)) + 1)
                dias = (hoy - vencimiento_pendiente).days
            
            return pd.Series([max(0, dias), saldo_vencido])
        except:
            return pd.Series([0, 0.0])

    df_cartera[['atraso', 'monto_vencido']] = df_cartera.apply(analizar_mora, axis=1)

    # --- 5. TABLA DE SEGUIMIENTO ---
    st.subheader("📋 Gestión de Cobranza")
    
    c_f1, c_f2 = st.columns([1, 1])
    solo_adeudo = c_f1.toggle("⚠️ Ver solo saldos vencidos", value=True)
    busqueda = c_f2.text_input("🔍 Buscar por nombre o ubicación:")

    # Preparar vista
    df_cartera['Lote'] = df_cartera['ubicacion'].apply(lambda x: f"M{int(x['manzana']):02d}-L{int(x['lote']):02d} (E{x['etapa']})")
    df_cartera['Cliente'] = df_cartera['cliente'].apply(lambda x: x['nombre'])
    
    df_viz = df_cartera.copy()
    if solo_adeudo: df_viz = df_viz[df_viz['monto_vencido'] > 50]
    if busqueda:
        df_viz = df_viz[df_viz['Cliente'].str.contains(busqueda, case=False) | 
                        df_viz['Lote'].str.contains(busqueda, case=False)]

    if not df_viz.empty:
        df_viz = df_viz.sort_values("atraso", ascending=False)
        df_viz['Estatus'] = df_viz['atraso'].apply(lambda x: "🔴 Crítico" if x > 60 else ("🟡 Mora" if x > 0 else "🟢 Al día"))

        # Link de WhatsApp
        def make_wa(row):
            try:
                tel = re.sub(r'\D', '', str(row['cliente']['telefono']))
                tel_f = tel if tel.startswith("52") else "52" + tel
                msg = f"Hola {row['Cliente']}, te contactamos de Valle Mart. 📲 Detectamos un saldo pendiente en tu lote {row['Lote']} por ${row['monto_vencido']:,.2f}. ¿Podrías apoyarnos con tu comprobante?"
                return f"https://wa.me/{tel_f}?text={urllib.parse.quote(msg)}"
            except: return None
        
        df_viz['WhatsApp'] = df_viz.apply(make_wa, axis=1)

        st.dataframe(
            df_viz[["Estatus", "Lote", "Cliente", "atraso", "monto_vencido", "WhatsApp"]],
            column_config={
                "atraso": st.column_config.NumberColumn("Días Mora"),
                "monto_vencido": st.column_config.NumberColumn("Monto Vencido", format="$%,.2f"),
                "WhatsApp": st.column_config.LinkColumn("📲 Recordatorio", display_text="Enviar WA")
            },
            use_container_width=True, hide_index=True
        )
    else:
        st.success("🎉 Cartera al día.")
