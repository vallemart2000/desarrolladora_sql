import streamlit as st
import pandas as pd
from datetime import datetime
import urllib.parse
import re

def render_inicio(supabase):
    st.title("🏠 Panel de Control y Cartera")

    # --- 1. CARGA DE DATOS (Ajustado a SQL Real) ---
    try:
        # Traemos Ventas con los nombres de columna reales de 'ubicaciones'
        res_v = supabase.table("ventas").select("""
            *,
            cliente:directorio!cliente_id(nombre, telefono, correo),
            ubicacion:ubicaciones(id, manzana, lote, etapa, precio)
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

    # Creamos el identificador de lote manualmente ya que no existe en SQL
    def get_lote_str(u):
        return f"M{int(u['manzana']):02d}-L{int(u['lote']):02d} (E{u['etapa']})"
    
    df_v['Lote_Ref'] = df_v['ubicacion'].apply(get_lote_str)
    df_v['Cliente_Nom'] = df_v['cliente'].apply(lambda x: x['nombre'])

    # --- 2. MÉTRICAS PRINCIPALES ---
    total_recaudado = df_v["enganche_pagado"].fillna(0).sum() + (df_p["monto"].sum() if not df_p.empty else 0)
    valor_cartera = df_v[df_v['estatus_venta'] != 'Cancelado']['precio_venta'].sum()
    clientes_activos = df_v[df_v['estatus_venta'] != 'Cancelado']['cliente_id'].nunique()
    
    # Diseño de métricas estilo Dashboard Pro
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("💰 Ingresos Totales", f"$ {total_recaudado:,.2f}")
    m2.metric("👥 Clientes Activos", clientes_activos)
    m3.metric("📈 Valor Cartera", f"$ {valor_cartera:,.2f}")
    m4.metric("🏗️ Lotes Vendidos", len(df_v))

    st.markdown("---")

    # --- 3. LÓGICA DE COBRANZA ---
    res_p_vta = supabase.table("pagos").select("venta_id, monto").execute()
    df_p_vta = pd.DataFrame(res_p_vta.data)
    pagos_sum = df_p_vta.groupby('venta_id')['monto'].sum().reset_index() if not df_p_vta.empty else pd.DataFrame(columns=['venta_id', 'monto'])

    df_cartera = df_v.copy()
    df_cartera = df_cartera.merge(pagos_sum, left_on='id', right_on='venta_id', how='left').fillna({'monto': 0})
    
    hoy = datetime.now()

    def calc_mora(row):
        try:
            if not row['fecha_venta']: return pd.Series([0, 0.0])
            
            f_ini = pd.to_datetime(row['fecha_venta'])
            # Meses transcurridos
            diff_meses = (hoy.year - f_ini.year) * 12 + (hoy.month - f_ini.month)
            mensualidad = float(row.get('mensualidad') or 0)
            
            if mensualidad <= 0: return pd.Series([0, 0.0])

            # Deuda teórica acumulada vs Pagado real
            deuda_teorica = max(0, diff_meses) * mensualidad
            pagado_real = float(row['monto']) 
            saldo_vencido = max(0.0, deuda_teorica - pagado_real)
            
            # Días de atraso
            dias = 0
            if saldo_vencido > 10: # Margen de tolerancia
                meses_cubiertos = pagado_real / mensualidad
                prox_vencimiento = f_ini + pd.DateOffset(months=int(meses_cubiertos) + 1)
                dias = (hoy - prox_vencimiento).days
            
            return pd.Series([max(0, dias), saldo_vencido])
        except:
            return pd.Series([0, 0.0])

    df_cartera[['atraso', 'monto_vencido']] = df_cartera.apply(calc_mora, axis=1)

    # --- 4. LINKS DE CONTACTO AUTOMATIZADOS ---
    def link_contacto(row, tipo):
        try:
            nombre = row['Cliente_Nom']
            if tipo == "WA":
                tel = re.sub(r'\D', '', str(row['cliente']['telefono']))
                # Asegurar prefijo 52 para México
                tel_final = tel if tel.startswith("52") else "52" + tel
                msg = (f"Hola {nombre}, te saludamos de Valle Mart. 📲 Detectamos un saldo pendiente en tu lote "
                       f"{row['Lote_Ref']} por ${row['monto_vencido']:,.2f}. "
                       f"¿Podrías apoyarnos con tu comprobante?")
                return f"https://wa.me/{tel_final}?text={urllib.parse.quote(msg)}"
            else:
                mail = row['cliente']['correo']
                return f"mailto:{mail}?subject=Estado de Cuenta - Lote {row['Lote_Ref']}"
        except: return None

    df_cartera['WhatsApp'] = df_cartera.apply(lambda r: link_contacto(r, "WA"), axis=1)
    df_cartera['Correo'] = df_cartera.apply(lambda r: link_contacto(r, "Mail"), axis=1)

    # --- 5. TABLA DE SEGUIMIENTO ---
    st.subheader("📋 Control de Cobranza")
    
    c_f1, c_f2 = st.columns([1, 1])
    solo_mora = c_f1.toggle("⚠️ Ver solo clientes con adeudo", value=True)
    busqueda = c_f2.text_input("🔍 Buscar:", placeholder="Nombre o Lote...")

    df_viz = df_cartera.copy()
    if solo_mora: df_viz = df_viz[df_viz['monto_vencido'] > 10]
    if busqueda:
        df_viz = df_viz[df_viz['Cliente_Nom'].str.contains(busqueda, case=False) | 
                        df_viz['Lote_Ref'].str.contains(busqueda, case=False)]

    if not df_viz.empty:
        df_viz = df_viz.sort_values("atraso", ascending=False)
        df_viz['Estatus'] = df_viz['atraso'].apply(
            lambda x: "🔴 Crítico (+60)" if x > 60 else ("🟡 Mora" if x > 0 else "🟢 Al día")
        )

        st.dataframe(
            df_viz[["Estatus", "Lote_Ref", "Cliente_Nom", "atraso", "monto_vencido", "WhatsApp", "Correo"]],
            column_config={
                "Lote_Ref": "Ubicación",
                "Cliente_Nom": "Cliente",
                "atraso": st.column_config.NumberColumn("Días Atraso"),
                "monto_vencido": st.column_config.NumberColumn("Saldo Vencido", format="$%,.2f"),
                "WhatsApp": st.column_config.LinkColumn("📲 WA", display_text="Enviar"),
                "Correo": st.column_config.LinkColumn("📧 Mail", display_text="Enviar")
            },
            use_container_width=True, 
            hide_index=True
        )
    else:
        st.success("🎉 Todo está al corriente.")
