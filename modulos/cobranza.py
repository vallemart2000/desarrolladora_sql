import streamlit as st
import pandas as pd
from datetime import datetime

def render_cobranza(supabase):
    st.title("💰 Gestión de Cobranza")
    
    # --- 1. CARGA DE DATOS ---
    try:
        res_v = supabase.table("ventas").select("""
            id, lote_id, cliente_id, precio_venta, enganche_pagado, estatus_venta,
            cliente:directorio!cliente_id(nombre),
            ubicacion:ubicaciones(ubicacion_display, enganche_requerido)
        """).execute()
        df_v = pd.DataFrame(res_v.data)
        
        res_p = supabase.table("pagos").select("""
            id, venta_id, fecha, monto, metodo, folio, comentarios,
            venta:ventas!venta_id(
                cliente:directorio!cliente_id(nombre),
                ubicacion:ubicaciones(ubicacion_display)
            )
        """).order("fecha", desc=True).execute()
        df_p = pd.DataFrame(res_p.data)
        
    except Exception as e:
        st.error(f"Error cargando datos: {e}")
        return

    tab_pago, tab_historial, tab_admin = st.tabs(["💵 Registrar Nuevo Pago", "📋 Historial de Ingresos", "✏️ Administrar Pagos"])

    # --- PESTAÑA 1: REGISTRAR PAGO (Tu lógica actual) ---
    with tab_pago:
        if df_v.empty:
            st.warning("No hay contratos o apartados registrados.")
        else:
            df_v['display_vta'] = df_v.apply(lambda x: f"{x['ubicacion']['ubicacion_display']} | {x['cliente']['nombre']}", axis=1)
            seleccion = st.selectbox("🔍 Seleccione Lote o Cliente:", ["--"] + df_v["display_vta"].tolist())
            
            if seleccion != "--":
                v = df_v[df_v['display_vta'] == seleccion].iloc[0]
                eng_req = float(v['ubicacion']['enganche_requerido'])
                eng_pag_actual = float(v.get('enganche_pagado') or 0.0)
                faltante_eng = max(0.0, eng_req - eng_pag_actual)
                
                if v['estatus_venta'] == "Apartado":
                    st.warning(f"⚠️ **ESTADO: APARTADO** (Faltan $ {faltante_eng:,.2f} para cubrir el enganche)")
                else:
                    st.success(f"🟢 **ESTADO: VENDIDO / ACTIVO**")

                with st.form("form_pago_sql", clear_on_submit=True):
                    c1, c2, c3 = st.columns(3)
                    f_fec = c1.date_input("Fecha de Pago", value=datetime.now())
                    f_met = c2.selectbox("Método", ["Efectivo", "Transferencia", "Depósito", "Tarjeta"])
                    f_fol = c3.text_input("Folio / Referencia")
                    f_mon = st.number_input("Importe a Recibir ($)", min_value=0.01, value=float(faltante_eng) if faltante_eng > 0 else 5000.0)
                    f_com = st.text_area("Notas del pago")
                    
                    if st.form_submit_button("✅ REGISTRAR PAGO", type="primary"):
                        try:
                            supabase.table("pagos").insert({
                                "venta_id": int(v['id']), "fecha": str(f_fec), "monto": f_mon,
                                "metodo": f_met, "folio": f_fol, "comentarios": f_com
                            }).execute()

                            nuevo_acumulado = eng_pag_actual + f_mon
                            upd_v = {"enganche_pagado": nuevo_acumulado}
                            
                            if v['estatus_venta'] == "Apartado" and nuevo_acumulado >= eng_req:
                                upd_v["estatus_venta"] = "Activa"
                                upd_v["fecha_contrato"] = str(f_fec)
                                supabase.table("ubicaciones").update({"estatus": "Vendido"}).eq("id", v['lote_id']).execute()
                                st.balloons()
                            
                            supabase.table("ventas").update(upd_v).eq("id", v['id']).execute()
                            st.success("Pago registrado."); st.rerun()
                        except Exception as e: st.error(f"Error: {e}")

    # --- PESTAÑA 2: HISTORIAL ---
    with tab_historial:
        if not df_p.empty:
            df_hist = df_p.copy()
            df_hist['Lote'] = df_hist['venta'].apply(lambda x: x['ubicacion']['ubicacion_display'] if x else "N/A")
            df_hist['Cliente'] = df_hist['venta'].apply(lambda x: x['cliente']['nombre'] if x else "N/A")
            st.metric("Total Recaudado", f"$ {df_hist['monto'].sum():,.2f}")
            st.dataframe(df_hist[["fecha", "Lote", "Cliente", "monto", "metodo", "folio"]], use_container_width=True, hide_index=True)

    # --- PESTAÑA 3: ADMINISTRAR (EDITAR/ELIMINAR) ---
    with tab_admin:
        st.subheader("🛠️ Editor de Pagos")
        if df_p.empty:
            st.info("No hay pagos para administrar.")
        else:
            # Crear un selector descriptivo para los pagos
            df_p['pago_display'] = df_p.apply(
                lambda x: f"{x['fecha']} | {x['venta']['ubicacion']['ubicacion_display']} | ${x['monto']:,.2f} | {x['venta']['cliente']['nombre']}", axis=1
            )
            pago_sel = st.selectbox("Seleccione el pago a modificar o eliminar:", ["--"] + df_p['pago_display'].tolist())
            
            if pago_sel != "--":
                p_data = df_p[df_p['pago_display'] == pago_sel].iloc[0]
                
                with st.form("form_edit_pago"):
                    col1, col2 = st.columns(2)
                    e_monto = col1.number_input("Monto ($)", value=float(p_data['monto']))
                    e_fecha = col2.date_input("Fecha", value=datetime.strptime(p_data['fecha'], '%Y-%m-%d'))
                    e_metodo = col1.selectbox("Método", ["Efectivo", "Transferencia", "Depósito", "Tarjeta"], 
                                            index=["Efectivo", "Transferencia", "Depósito", "Tarjeta"].index(p_data['metodo']))
                    e_folio = col2.text_input("Folio", value=p_data['folio'])
                    e_coment = st.text_area("Comentarios", value=p_data['comentarios'])
                    
                    c_edit, c_del = st.columns(2)
                    
                    if c_edit.form_submit_button("💾 GUARDAR CAMBIOS"):
                        # 1. Actualizar el pago
                        supabase.table("pagos").update({
                            "monto": e_monto, "fecha": str(e_fecha), "metodo": e_metodo, "folio": e_folio, "comentarios": e_coment
                        }).eq("id", p_data['id']).execute()
                        
                        # 2. Recalcular el acumulado de la venta
                        todos_p_vta = supabase.table("pagos").select("monto").eq("venta_id", p_data['venta_id']).execute()
                        nuevo_total = sum(item['monto'] for item in todos_p_vta.data)
                        supabase.table("ventas").update({"enganche_pagado": nuevo_total}).eq("id", p_data['venta_id']).execute()
                        
                        st.success("Pago actualizado y balance recalculado."); st.rerun()

                    if c_del.form_submit_button("🗑️ ELIMINAR PAGO"):
                        # 1. Borrar el pago
                        supabase.table("pagos").delete().eq("id", p_data['id']).execute()
                        
                        # 2. Recalcular el acumulado de la venta tras la eliminación
                        todos_p_vta = supabase.table("pagos").select("monto").eq("venta_id", p_data['venta_id']).execute()
                        nuevo_total = sum(item['monto'] for item in todos_p_vta.data) if todos_p_vta.data else 0
                        supabase.table("ventas").update({"enganche_pagado": nuevo_total}).eq("id", p_data['venta_id']).execute()
                        
                        st.warning("Pago eliminado y balance de venta actualizado."); st.rerun()
