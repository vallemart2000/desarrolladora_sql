import streamlit as st
import pandas as pd
from datetime import datetime
from dateutil.relativedelta import relativedelta

def render_cobranza(supabase):
    st.title("💰 Gestión de Cobranza")
    
    # --- 1. CARGA DE DATOS ---
    try:
        # Traemos ventas con sus relaciones
        res_v = supabase.table("ventas").select("""
            id,
            lote_id,
            cliente_id,
            precio_venta,
            enganche_pagado,
            estatus_venta,
            cliente:directorio!cliente_id(nombre),
            ubicacion:ubicaciones(ubicacion_display, enganche_requerido)
        """).execute()
        df_v = pd.DataFrame(res_v.data)
        
        # Traemos historial de pagos
        # Nota: Si el error persiste, usamos una consulta más plana
        res_p = supabase.table("pagos").select("""
            fecha,
            monto,
            metodo,
            folio,
            comentarios,
            venta:ventas!venta_id(
                cliente:directorio!cliente_id(nombre),
                ubicacion:ubicaciones(ubicacion_display)
            )
        """).order("fecha", desc=True).execute()
        df_p = pd.DataFrame(res_p.data)
        
    except Exception as e:
        st.error(f"Error cargando datos: {e}")
        st.info("💡 Intenta presionar el botón 'Sincronizar Datos' en la barra lateral después de correr el SQL.")
        return

    tab_pago, tab_historial = st.tabs(["💵 Registrar Nuevo Pago", "📋 Historial de Ingresos"])

    # --- PESTAÑA 1: REGISTRAR PAGO ---
    with tab_pago:
        if df_v.empty:
            st.warning("No hay contratos o apartados registrados.")
        else:
            # Creamos el nombre para mostrar en el selector (Lote | Nombre del Cliente)
            # Usamos .get() por seguridad para evitar errores si un dato viene nulo
            df_v['display_vta'] = df_v.apply(
                lambda x: f"{x['ubicacion']['ubicacion_display']} | {x['cliente']['nombre']}", 
                axis=1
            )
            
            seleccion = st.selectbox("🔍 Seleccione Lote o Cliente:", ["--"] + df_v["display_vta"].tolist())
            
            if seleccion != "--":
                # Extraer la fila seleccionada
                v = df_v[df_v['display_vta'] == seleccion].iloc[0]
                v_id = v['id']
                l_id = v['lote_id']
                
                # Datos financieros desde la relación y la tabla ventas
                eng_req = float(v['ubicacion']['enganche_requerido'])
                # Si enganche_pagado es None en la DB, lo tratamos como 0.0
                eng_pag_actual = float(v.get('enganche_pagado') or 0.0)
                faltante_eng = max(0.0, eng_req - eng_pag_actual)
                
                # Interfaz visual de estatus
                if v['estatus_venta'] == "Apartado":
                    st.warning(f"⚠️ **ESTADO: APARTADO** (Faltan $ {faltante_eng:,.2f} para cubrir el enganche de $ {eng_req:,.2f})")
                else:
                    st.success(f"🟢 **ESTADO: VENDIDO / ACTIVO** (Enganche cubierto)")

                with st.form("form_pago_sql", clear_on_submit=True):
                    c1, c2, c3 = st.columns(3)
                    f_fec = c1.date_input("Fecha de Pago", value=datetime.now())
                    f_met = c2.selectbox("Método", ["Efectivo", "Transferencia", "Depósito", "Tarjeta"])
                    f_fol = c3.text_input("Folio / Referencia")
                    
                    # El monto sugerido es el faltante del enganche, o una cifra base si ya se cubrió
                    f_mon = st.number_input("Importe a Recibir ($)", min_value=0.01, value=float(faltante_eng) if faltante_eng > 0 else 5000.0)
                    f_com = st.text_area("Notas del pago")
                    
                    if st.form_submit_button("✅ REGISTRAR PAGO", type="primary"):
                        try:
                            # 1. Insertar el pago en Supabase
                            pago_data = {
                                "venta_id": int(v_id),
                                "fecha": str(f_fec),
                                "monto": f_mon,
                                "metodo": f_met,
                                "folio": f_fol,
                                "comentarios": f_com
                            }
                            supabase.table("pagos").insert(pago_data).execute()

                            # 2. Calcular nuevo acumulado para actualizar la venta
                            nuevo_acumulado = eng_pag_actual + f_mon
                            update_v = {"enganche_pagado": nuevo_acumulado}
                            
                            # LÓGICA DE TRANSICIÓN: APARTADO -> VENDIDO
                            if v['estatus_venta'] == "Apartado" and nuevo_acumulado >= eng_req:
                                update_v["estatus_venta"] = "Activa"
                                update_v["fecha_contrato"] = str(f_fec)
                                
                                # Actualizar la ubicación físicamente a VENDIDO
                                supabase.table("ubicaciones").update({"estatus": "Vendido"}).eq("id", l_id).execute()
                                st.balloons()
                            
                            # Actualizar la tabla de ventas
                            supabase.table("ventas").update(update_v).eq("id", v_id).execute()
                            
                            st.success(f"✅ Pago de $ {f_mon:,.2f} registrado con éxito.")
                            st.rerun()
                            
                        except Exception as e:
                            st.error(f"Error al procesar pago: {e}")

    # --- PESTAÑA 2: HISTORIAL ---
    with tab_historial:
        st.subheader("📋 Historial de Ingresos")
        if df_p.empty:
            st.info("No hay pagos registrados aún.")
        else:
            # Aplanamos los datos anidados para mostrarlos en el dataframe
            df_hist = df_p.copy()
            df_hist['Lote'] = df_hist['venta'].apply(lambda x: x['ubicacion']['ubicacion_display'] if x and x['ubicacion'] else "N/A")
            df_hist['Cliente'] = df_hist['venta'].apply(lambda x: x['cliente']['nombre'] if x and x['cliente'] else "N/A")
            
            st.metric("Total Recaudado en Caja", f"$ {df_hist['monto'].sum():,.2f}")
            
            st.dataframe(
                df_hist[["fecha", "Lote", "Cliente", "monto", "metodo", "folio", "comentarios"]],
                column_config={
                    "fecha": "Fecha",
                    "monto": st.column_config.NumberColumn("Importe", format="$ %.2f"),
                    "metodo": "Método de Pago",
                    "folio": "Referencia"
                },
                use_container_width=True,
                hide_index=True
            )
