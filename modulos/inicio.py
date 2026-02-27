import streamlit as st
import pandas as pd
from datetime import datetime
import urllib.parse
import re

def render_inicio(supabase):
    st.title("🏠 Panel de Control y Cartera")

    # --- 1. CARGA DE DATOS CONSOLIDADOS ---
    # Traemos Ventas, Clientes (para contacto) y Pagos
    res_v = supabase.table("ventas").select("*, clientes(nombre, telefono, correo), ubicaciones(ubicacion)").execute()
    res_p = supabase.table("pagos").select("monto").execute()
    
    df_v = pd.DataFrame(res_v.data)
    df_p = pd.DataFrame(res_p.data)

    if df_v.empty:
        st.info("👋 ¡Bienvenido! Aún no hay ventas registradas. Comienza en el módulo de Ventas.")
        return

    # --- 2. MÉTRICAS PRINCIPALES ---
    total_recaudado = df_v["enganche_pagado"].sum() + (df_p["monto"].sum() if not df_p.empty else 0)
    valor_cartera = df_v[df_v['estatus_pago'] != 'Cancelado']['precio_total'].sum()
    clientes_activos = df_v[df_v['estatus_pago'] != 'Cancelado'].shape[0]
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("💰 Ingresos Totales", f"$ {total_recaudado:,.2f}")
    c2.metric("👥 Clientes Activos", clientes_activos)
    c3.metric("📈 Valor Cartera", f"$ {valor_cartera:,.2f}")
    c4.metric("🏗️ Lotes Vendidos", df_v.shape[0])

    st.markdown("---")

    # --- 3. LÓGICA DE CARTERA Y MORA ---
    # Traemos resumen de pagos por venta para calcular mora
    res_p_vta = supabase.table("pagos").select("venta_id, monto").execute()
    df_p_vta = pd.DataFrame(res_p_vta.data)
    pagos_sum = df_p_vta.groupby('venta_id')['monto'].sum().reset_index() if not df_p_vta.empty else pd.DataFrame(columns=['venta_id', 'monto'])

    df_cartera = df_v.copy()
    df_cartera = df_cartera.merge(pagos_sum, left_on='id', right_on='venta_id', how='left').fillna({'monto': 0})
    
    hoy = datetime.now()

    def calc_mora_sql(row):
        try:
            # Si no hay fecha de inicio mensualidades, no hay mora aún
            if not row['inicio_mensualidades']: return pd.Series([0, 0.0])
            
            f_ini = pd.to_datetime(row['inicio_mensualidades'])
            # Meses que ya deberían estar pagados
            diff = (hoy.year - f_ini.year) * 12 + (hoy.month - f_ini.month)
            if hoy.day < f_ini.day: diff -= 1
            
            mensualidad = float(row['mensualidad'])
            deuda_teorica = max(0, diff) * mensualidad
            pagado_mensualidades = float(row['monto']) # Pagos en tabla 'pagos'
            
            saldo_vencido = max(0.0, deuda_teorica - pagado_mensualidades)
            
            # Cálculo de días (basado en cuántos meses faltan pagar)
            meses_cubiertos = pagado_mensualidades / mensualidad if mensualidad > 0 else 0
            vence_pendiente = f_ini + pd.DateOffset(months=int(meses_cubiertos))
            dias = (hoy - vence_pendiente).days if saldo_vencido > 0 else 0
            
            return pd.Series([max(0, dias), saldo_vencido])
        except:
            return pd.Series([0, 0.0])

    df_cartera[['atraso', 'monto_vencido']] = df_cartera.apply(calc_mora_sql, axis=1)

    # --- 4. GENERACIÓN DE LINKS DE CONTACTO ---
    def link_contacto_sql(row, tipo):
        try:
            cliente_info = row['clientes']
            nombre = cliente_info['nombre']
            if tipo == "WA":
                tel = re.sub(r'\D', '', str(cliente_info['telefono']))
                tel_final = "52" + tel if len(tel) == 10 else tel
                msg = (f"Hola {nombre}, te saludamos de Valle Mart. Detectamos un saldo pendiente en tu lote "
                       f"{row['ubicaciones']['ubicacion']} por $ {row['monto_vencido']:,.2f}. "
                       f"Contamos con {row['atraso']} días de atraso.")
                return f"https://wa.me/{tel_final}?text={urllib.parse.quote(msg)}"
            else:
                mail = cliente_info['correo']
                return f"mailto:{mail}?subject=Estado de Cuenta - Lote {row['ubicaciones']['ubicacion']}"
        except: return None

    df_cartera['WhatsApp'] = df_cartera.apply(lambda r: link_contacto_sql(r, "WA"), axis=1)
    df_cartera['Correo'] = df_cartera.apply(lambda r: link_contacto_sql(r, "Mail"), axis=1)

    # --- 5. TABLA DE COBRANZA ---
    st.subheader("📋 Control de Cobranza")
    
    col_f1, col_f2 = st.columns(2)
    solo_mora = col_f1.toggle("Ver solo clientes con adeudo", value=True)
    busqueda = col_f2.text_input("🔍 Buscar cliente o lote:")

    df_viz = df_cartera.copy()
    if solo_mora:
        df_viz = df_viz[df_viz['monto_vencido'] > 0]
    
    if busqueda:
        # Búsqueda en los nombres de clientes y ubicación (nested dicts)
        mask_cli = df_viz['clientes'].apply(lambda x: busqueda.lower() in x['nombre'].lower())
        mask_ubi = df_viz['ubicaciones'].apply(lambda x: busqueda.lower() in x['ubicacion'].lower())
        df_viz = df_viz[mask_cli | mask_ubi]

    if not df_viz.empty:
        df_viz = df_viz.sort_values("atraso", ascending=False)
        
        # Aplanamos para el dataframe de Streamlit
        df_viz['Lote'] = df_viz['ubicaciones'].apply(lambda x: x['ubicacion'])
        df_viz['Cliente'] = df_viz['clientes'].apply(lambda x: x['nombre'])
        df_viz['Estatus'] = df_viz['atraso'].apply(
            lambda x: "🔴 CRÍTICO(+75)" if x > 75 else ("🟡 MORA(+25)" if x > 25 else "🟢 AL CORRIENTE")
        )

        st.dataframe(
            df_viz[["Estatus", "Lote", "Cliente", "atraso", "monto_vencido", "WhatsApp", "Correo"]],
            column_config={
                "atraso": "Días",
                "monto_vencido": st.column_config.NumberColumn("Saldo Vencido", format="$ %.2f"),
                "WhatsApp": st.column_config.LinkColumn("📲 WA", display_text="Enviar Chat"),
                "Correo": st.column_config.LinkColumn("📧 Mail", display_text="Enviar Email")
            },
            use_container_width=True, 
            hide_index=True
        )
    else:
        st.success("🎉 ¡Felicidades! No hay saldos vencidos pendientes.")
