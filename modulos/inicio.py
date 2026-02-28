import streamlit as st
import pandas as pd
from datetime import datetime
import urllib.parse
import re

def render_inicio(supabase):
    st.title("🏠 Panel de Control y Cartera")

    # --- 1. CARGA DE DATOS (Esquema Real SQL) ---
    try:
        # Consulta de Ventas con sus relaciones
        res_v = supabase.table("ventas").select("""
            id,
            fecha_venta,
            plazo,
            cliente_id,
            ubicacion_id,
            cliente:directorio!cliente_id(nombre, telefono, correo),
            ubicacion:ubicaciones(id, manzana, lote, etapa, precio, enganche_req)
        """).execute()
        
        # Consulta de Pagos (solo columnas existentes: id, venta_id, monto, fecha)
        res_p = supabase.table("pagos").select("venta_id, monto").execute()
        
        df_v = pd.DataFrame(res_v.data)
        df_p = pd.DataFrame(res_p.data)
    except Exception as e:
        st.error(f"🚨 Error de conexión con Base de Datos: {e}")
        return

    if df_v.empty:
        st.info("👋 El sistema está listo. Comienza registrando una venta en el módulo correspondiente.")
        return

    # --- 2. CÁLCULOS FINANCIEROS GLOBALES ---
    # Ingresos Totales (Suma simple de todos los montos en la tabla pagos)
    total_recaudado = df_p["monto"].sum() if not df_p.empty else 0.0
    
    # Valor de la Cartera (Suma de los precios de los lotes vendidos)
    df_v['valor_lote'] = df_v['ubicacion'].apply(lambda x: float(x['precio']) if x else 0.0)
    total_cartera = df_v['valor_lote'].sum()
    
    # Métricas en pantalla
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("💰 Recaudación Total", f"$ {total_recaudado:,.2f}")
    m2.metric("👥 Clientes", df_v['cliente_id'].nunique())
    m3.metric("📈 Valor de Cartera", f"$ {total_cartera:,.2f}")
    m4.metric("🏗️ Lotes Vendidos", len(df_v))

    st.divider()

    # --- 3. ANÁLISIS DE MORA POR CLIENTE ---
    # Agrupamos pagos por venta
    pagos_agrupados = df_p.groupby('venta_id')['monto'].sum().reset_index() if not df_p.empty else pd.DataFrame(columns=['venta_id', 'monto'])
    
    # Unimos Ventas con sus Pagos Totales
    df_cartera = df_v.merge(pagos_agrupados, left_on='id', right_on='venta_id', how='left').fillna({'monto': 0})
    
    hoy = datetime.now()

    def calcular_estado_cuenta(row):
        try:
            u = row['ubicacion']
            precio = float(u['precio'])
            enganche_req = float(u['enganche_req'])
            plazo = int(row['plazo'] or 12)
            
            # Cálculo de mensualidad: (Precio - Enganche) / Plazo
            mensualidad = (precio - enganche_req) / plazo if plazo > 0 else 0
            
            # Tiempo transcurrido desde la venta
            f_vta = pd.to_datetime(row['fecha_venta'])
            meses_transcurridos = (hoy.year - f_vta.year) * 12 + (hoy.month - f_vta.month)
            
            # Lo que el cliente DEBERÍA haber pagado a día de hoy
            # (Enganche inicial + mensualidades de los meses que ya pasaron)
            deuda_teorica = enganche_req + (max(0, meses_transcurridos) * mensualidad)
            
            # Lo que el cliente HA pagado realmente
            pagado_real = float(row['monto'])
            
            saldo_vencido = max(0.0, deuda_teorica - pagado_real)
            
            # Cálculo de días de atraso (si debe más de $100 pesos)
            dias_atraso = 0
            if saldo_vencido > 100:
                # Calculamos cuántos meses de mensualidad ha cubierto realmente
                meses_cubiertos = (pagado_real - enganche_req) / mensualidad if mensualidad > 0 else 0
                # El siguiente vencimiento es: fecha_venta + (meses cubiertos + 1)
                fecha_vencimiento_pendiente = f_vta + pd.DateOffset(months=int(max(0, meses_cubiertos)) + 1)
                dias_atraso = (hoy - fecha_vencimiento_pendiente).days
            
            return pd.Series([max(0, dias_atraso), saldo_vencido])
        except:
            return pd.Series([0, 0.0])

    df_cartera[['atraso', 'monto_vencido']] = df_cartera.apply(calcular_estado_cuenta, axis=1)

    # --- 4. INTERFAZ DE COBRANZA ---
    st.subheader("📋 Control de Cartera Vencida")
    
    col_f1, col_f2 = st.columns([1, 1])
    solo_mora = col_f1.toggle("⚠️ Filtrar solo deudores", value=True)
    busqueda = col_f2.text_input("🔍 Buscar cliente o manzana-lote:")

    # Formatear datos para la tabla
    df_cartera['Lote'] = df_cartera['ubicacion'].apply(lambda x: f"M{int(x['manzana']):02d}-L{int(x['lote']):02d} (Etapa {x['etapa']})")
    df_cartera['Cliente'] = df_cartera['cliente'].apply(lambda x: x['nombre'] if x else "N/A")
    
    df_viz = df_cartera.copy()
    if solo_mora:
        df_viz = df_viz[df_viz['monto_vencido'] > 100] # Ocultar ruidos de centavos
    
    if busqueda:
        df_viz = df_viz[df_viz['Cliente'].str.contains(busqueda, case=False) | 
                        df_viz['Lote'].str.contains(busqueda, case=False)]

    if not df_viz.empty:
        df_viz = df_viz.sort_values("atraso", ascending=False)
        
        # Clasificación por colores/emojis
        df_viz['Estatus'] = df_viz['atraso'].apply(
            lambda x: "🔴 Crítico (+60)" if x > 60 else ("🟡 Mora" if x > 0 else "🟢 Al corriente")
        )

        # Generador de Link para WhatsApp
        def generar_wa(row):
            try:
                tel = re.sub(r'\D', '', str(row['cliente']['telefono']))
                tel_f = tel if tel.startswith("52") else "52" + tel
                msg = (f"Hola {row['Cliente']}, te contactamos de Valle Mart. 📲 "
                       f"Detectamos un saldo pendiente en tu lote {row['Lote']} por ${row['monto_vencido']:,.2f}. "
                       f"¿Podrías apoyarnos con tu comprobante para actualizar tu estado de cuenta?")
                return f"https://wa.me/{tel_f}?text={urllib.parse.quote(msg)}"
            except: return None
        
        df_viz['WhatsApp'] = df_viz.apply(generar_wa, axis=1)

        st.dataframe(
            df_viz[["Estatus", "Lote", "Cliente", "atraso", "monto_vencido", "WhatsApp"]],
            column_config={
                "atraso": st.column_config.NumberColumn("Días Atraso", help="Días transcurridos desde el vencimiento del pago no cubierto."),
                "monto_vencido": st.column_config.NumberColumn("Saldo Vencido", format="$%,.2f"),
                "WhatsApp": st.column_config.LinkColumn("📲 Recordatorio", display_text="Enviar WA")
            },
            use_container_width=True, 
            hide_index=True
        )
    else:
        st.success("🎉 ¡Excelente! No hay cuentas por cobrar vencidas en este momento.")
