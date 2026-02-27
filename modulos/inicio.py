import streamlit as st
import pandas as pd
from datetime import datetime
import urllib.parse
import re

def render_inicio(supabase):
    st.title("🏠 Panel de Control y Cartera")

    # --- 1. CARGA DE DATOS CONSOLIDADOS ---
    try:
        # Traemos Ventas con sus relaciones corregidas
        res_v = supabase.table("ventas").select("""
            *,
            cliente:directorio!cliente_id(nombre, telefono, correo),
            ubicacion:ubicaciones(ubicacion_display)
        """).execute()
        
        # Traemos todos los pagos para calcular el ingreso total
        res_p = supabase.table("pagos").select("monto").execute()
        
        df_v = pd.DataFrame(res_v.data)
        df_p = pd.DataFrame(res_p.data)
    except Exception as e:
        st.error(f"Error cargando dashboard: {e}")
        return

    if df_v.empty:
        st.info("👋 ¡Bienvenido! Aún no hay ventas registradas. Comienza en el módulo de Ventas.")
        return

    # --- 2. MÉTRICAS PRINCIPALES ---
    # Ingresos = Enganches pagados + suma de todos los abonos en la tabla pagos
    total_recaudado = df_v["enganche_pagado"].fillna(0).sum() + (df_p["monto"].sum() if not df_p.empty else 0)
    valor_cartera = df_v[df_v['estatus_venta'] != 'Cancelado']['precio_venta'].sum()
    clientes_activos = df_v[df_v['estatus_venta'] != 'Cancelado']['cliente_id'].nunique()
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("💰 Ingresos Totales", f"$ {total_recaudado:,.2f}")
    c2.metric("👥 Clientes Activos", clientes_activos)
    c3.metric("📈 Valor Cartera", f"$ {valor_cartera:,.2f}")
    c4.metric("🏗️ Lotes Vendidos", df_v.shape[0])

    st.markdown("---")

    # --- 3. LÓGICA DE CARTERA Y MORA ---
    # Obtenemos suma de pagos por venta
    res_p_vta = supabase.table("pagos").select("venta_id, monto").execute()
    df_p_vta = pd.DataFrame(res_p_vta.data)
    pagos_sum = df_p_vta.groupby('venta_id')['monto'].sum().reset_index() if not df_p_vta.empty else pd.DataFrame(columns=['venta_id', 'monto'])

    df_cartera = df_v.copy()
    df_cartera = df_cartera.merge(pagos_sum, left_on='id', right_on='venta_id', how='left').fillna({'monto': 0})
    
    hoy = datetime.now()

    def calc_mora(row):
        try:
            # Si no hay fecha_contrato (aún es apartado), no calculamos mora de mensualidades
            if not row['fecha_contrato']: return pd.Series([0, 0.0])
            
            f_ini = pd.to_datetime(row['fecha_contrato'])
            # Meses transcurridos desde el contrato
            diff_meses = (hoy.year - f_ini.year) * 12 + (hoy.month - f_ini.month)
            
            mensualidad = float(row.get('mensualidad') or 0)
            if mensualidad <= 0: return pd.Series([0, 0.0])

            # Lo que debería haber pagado hasta hoy (sin contar el enganche)
            deuda_esperada = max(0, diff_meses) * mensualidad
            # Lo que ha pagado realmente en la tabla 'pagos'
            pagado_real = float(row['monto']) 
            
            saldo_vencido = max(0.0, deuda_esperada - pagado_real)
            
            # Cálculo aproximado de días de atraso
            meses_cubiertos = pagado_real / mensualidad
            vence_pendiente = f_ini + pd.DateOffset(months=int(meses_cubiertos))
            dias = (hoy - vence_pendiente).days if saldo_vencido > 0 else 0
            
            return pd.Series([max(0, dias), saldo_vencido])
        except:
            return pd.Series([0, 0.0])

    df_cartera[['atraso', 'monto_vencido']] = df_cartera.apply(calc_mora, axis=1)

    # --- 4. GENERACIÓN DE LINKS DE CONTACTO ---
    def link_contacto(row, tipo):
        try:
            nombre = row['cliente']['nombre']
            if tipo == "WA":
                tel = re.sub(r'\D', '', str(row['cliente']['telefono']))
                tel_final = tel if tel.startswith("52") else "52" + tel
                msg = (f"Hola {nombre}, te saludamos de Valle Mart. Detectamos un saldo pendiente en tu lote "
                       f"{row['ubicacion']['ubicacion_display']} por $ {row['monto_vencido']:,.2f}. "
                       f"Contamos con {row['atraso']} días de atraso. ¿Podrías apoyarnos con tu comprobante?")
                return f"https://wa.me/{tel_final}?text={urllib.parse.quote(msg)}"
            else:
                mail = row['cliente']['correo']
                return f"mailto:{mail}?subject=Estado de Cuenta - Lote {row['ubicacion']['ubicacion_display']}"
        except: return None

    df_cartera['WhatsApp'] = df_cartera.apply(lambda r: link_contacto(r, "WA"), axis=1)
    df_cartera['Correo'] = df_cartera.apply(lambda r: link_contacto(r, "Mail"), axis=1)

    # --- 5. TABLA DE COBRANZA ---
    st.subheader("📋 Control de Cobranza y Seguimiento")
    
    col_f1, col_f2 = st.columns(2)
    solo_mora = col_f1.toggle("Ver solo clientes con adeudo", value=True)
    busqueda = col_f2.text_input("🔍 Buscar por cliente o lote:")

    df_viz = df_cartera.copy()
    
    # Aplanamos nombres para facilitar filtros
    df_viz['Lote'] = df_viz['ubicacion'].apply(lambda x: x['ubicacion_display'])
    df_viz['Cliente'] = df_viz['cliente'].apply(lambda x: x['nombre'])

    if solo_mora:
        df_viz = df_viz[df_viz['monto_vencido'] > 0]
    
    if busqueda:
        df_viz = df_viz[df_viz['Cliente'].str.contains(busqueda, case=False) | 
                        df_viz['Lote'].str.contains(busqueda, case=False)]

    if not df_viz.empty:
        df_viz = df_viz.sort_values("atraso", ascending=False)
        df_viz['Estatus'] = df_viz['atraso'].apply(
            lambda x: "🔴 CRÍTICO(+60)" if x > 60 else ("🟡 MORA(+1)" if x > 0 else "🟢 AL CORRIENTE")
        )

        st.dataframe(
            df_viz[["Estatus", "Lote", "Cliente", "atraso", "monto_vencido", "WhatsApp", "Correo"]],
            column_config={
                "atraso": st.column_config.NumberColumn("Días", help="Días desde su último pago vencido"),
                "monto_vencido": st.column_config.NumberColumn("Saldo Vencido", format="$ %.2f"),
                "WhatsApp": st.column_config.LinkColumn("📲 WA", display_text="Enviar Chat"),
                "Correo": st.column_config.LinkColumn("📧 Mail", display_text="Enviar Email")
            },
            use_container_width=True, 
            hide_index=True
        )
    else:
        st.success("🎉 ¡Felicidades! No hay saldos vencidos pendientes.")
