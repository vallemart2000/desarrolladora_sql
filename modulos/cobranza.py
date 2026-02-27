import streamlit as st
import pandas as pd
from datetime import datetime
from dateutil.relativedelta import relativedelta

def render_cobranza(supabase):
    st.title("💰 Gestión de Cobranza (SQL)")
    
    # --- 1. CARGA DE DATOS ---
    # Traemos ventas con sus relaciones para el selector
    res_v = supabase.table("ventas").select("*, clientes(nombre), ubicaciones(ubicacion)").execute()
    df_v = pd.DataFrame(res_v.data)
    
    # Traemos historial de pagos
    res_p = supabase.table("pagos").select("*, ventas(id, cliente_id, clientes(nombre), ubicaciones(ubicacion))").order("fecha", desc=True).execute()
    df_p = pd.DataFrame(res_p.data)

    tab_pago, tab_historial = st.tabs(["💵 Registrar Nuevo Pago", "📋 Historial de Ingresos"])

    # --- PESTAÑA 1: REGISTRAR PAGO ---
    with tab_pago:
        if df_v.empty:
            st.warning("No hay contratos registrados.")
        else:
            # Preparamos las opciones del selector
            df_v['display_vta'] = df_v['ubicaciones'].apply(lambda x: x['ubicacion']) + " | " + df_v['clientes'].apply(lambda x: x['nombre'])
            seleccion = st.selectbox("🔍 Seleccione Lote o Cliente:", ["--"] + df_v["display_name" if "display_name" in df_v else "display_vta"].tolist())
            
            if seleccion != "--":
                # Extraer datos de la venta seleccionada
                v = df_v[df_v['display_vta'] == seleccion].iloc[0]
                v_id = v['id']
                l_id = v['lote_id']
                ubi_txt = v['ubicaciones']['ubicacion']
                
                eng_req = float(v['enganche_requerido'])
                eng_pag = float(v['enganche_pagado'])
                mensualidad_pactada = float(v['mensualidad'])
                
                faltante_eng = max(0.0, eng_req - eng_pag)
                es_apartado = eng_pag < eng_req

                if es_apartado:
                    st.warning(f"⚠️ **ESTADO: APARTADO** (Faltan $ {faltante_eng:,.2f} para completar enganche)")
                    monto_sugerido = faltante_eng
                else:
                    st.success(f"🟢 **ESTADO: ACTIVO** (Enganche cubierto)")
                    monto_sugerido = mensualidad_pactada

                with st.form("form_pago_sql"):
                    c1, c2, c3 = st.columns(3)
                    f_fec = c1.date_input("Fecha de Pago", value=datetime.now())
                    f_met = c2.selectbox("Método", ["Efectivo", "Transferencia", "Depósito"])
                    f_fol = c3.text_input("Folio / Referencia")
                    
                    f_mon = st.number_input("Importe a Recibir ($)", min_value=0.0, value=float(monto_sugerido))
                    f_com = st.text_area("Comentarios")
                    
                    if st.form_submit_button("✅ REGISTRAR PAGO", type="primary"):
                        if f_mon <= 0:
                            st.error("El monto debe ser mayor a 0.")
                        else:
                            try:
                                # 1. Registrar el pago
                                pago_data = {
                                    "venta_id": int(v_id),
                                    "fecha": str(f_fec),
                                    "monto": f_mon,
                                    "metodo": f_met,
                                    "folio": f_fol,
                                    "comentarios": f_com
                                }
                                supabase.table("pagos").insert(pago_data).execute()

                                # 2. Actualizar la Venta (Enganche)
                                nuevo_eng_pag = eng_pag + f_mon
                                update_venta = {"enganche_pagado": nuevo_eng_pag}
                                
                                # Si completa enganche, cambia estatus y actualiza lote
                                if eng_pag < eng_req and nuevo_eng_pag >= eng_req:
                                    update_venta["estatus_pago"] = "Al corriente"
                                    # La mensualidad inicia un mes después
                                    f_mens = (f_fec + relativedelta(months=1)).strftime('%Y-%m-%d')
                                    update_venta["fecha_contrato"] = str(f_fec)
                                    
                                    # Actualizar estatus del lote a VENDIDO
                                    supabase.table("ubicaciones").update({"estatus": "Vendido"}).eq("id", l_id).execute()
                                    st.balloons()

                                supabase.table("ventas").update(update_venta).eq("id", v_id).execute()
                                
                                st.success(f"✅ Pago de $ {f_mon:,.2f} registrado correctamente.")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error en la base de datos: {e}")

    # --- PESTAÑA 2: HISTORIAL ---
    with tab_historial:
        st.subheader("📋 Historial de Cobros")
        if df_p.empty:
            st.info("No hay pagos registrados.")
        else:
            # Aplanamos para mostrar en tabla
            df_hist = df_p.copy()
            df_hist['Lote'] = df_hist['ventas'].apply(lambda x: x['ubicaciones']['ubicacion'])
            df_hist['Cliente'] = df_hist['ventas'].apply(lambda x: x['clientes']['nombre'])
            
            st.metric("Total en Caja", f"$ {df_hist['monto'].sum():,.2f}")
            
            st.dataframe(
                df_hist[["fecha", "Lote", "Cliente", "monto", "metodo", "folio"]],
                column_config={"monto": st.column_config.NumberColumn("Importe", format="$ %.2f")},
                use_container_width=True,
                hide_index=True
            )
