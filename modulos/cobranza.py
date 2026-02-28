import streamlit as st
import pandas as pd
from datetime import datetime

def render_cobranza(supabase):
    st.title("💰 Gestión de Cobranza")
    
    # --- 1. CARGA DE DATOS ---
    try:
        # 1.1 Traemos ventas activas (usando columnas reales: id, ubicacion_id, cliente_id)
        # Nota: 'enganche_pagado' y 'estatus_venta' deben existir en tu tabla 'ventas'
        res_v = supabase.table("ventas").select("""
            id, ubicacion_id, cliente_id, comision_monto,
            cliente:directorio!cliente_id(nombre),
            ubicacion:ubicaciones(id, etapa, manzana, lote, precio, enganche_req)
        """).execute()
        df_v = pd.DataFrame(res_v.data)
        
        # 1.2 Traemos pagos
        res_p = supabase.table("pagos").select("""
            id, venta_id, fecha, monto, metodo, folio, comentarios,
            venta:ventas!venta_id(
                cliente:directorio!cliente_id(nombre),
                ubicacion:ubicaciones(manzana, lote)
            )
        """).order("fecha", desc=True).execute()
        df_p = pd.DataFrame(res_p.data)

        # 1.3 PROCESAMIENTO DE REFERENCIAS (M##-L##)
        if not df_v.empty:
            df_v['display_vta'] = df_v.apply(
                lambda x: f"M{int(x['ubicacion']['manzana']):02d}-L{int(x['ubicacion']['lote']):02d} | {x['cliente']['nombre']}", 
                axis=1
            )
        
    except Exception as e:
        st.error(f"Error cargando datos: {e}")
        return

    tab_pago, tab_historial, tab_admin = st.tabs([
        "💵 Registrar Nuevo Pago", 
        "📋 Historial de Ingresos", 
        "✏️ Administrar Pagos"
    ])

    # --- PESTAÑA 1: REGISTRAR PAGO ---
    with tab_pago:
        if df_v.empty:
            st.warning("No hay ventas registradas.")
        else:
            seleccion = st.selectbox("🔍 Seleccione Lote o Cliente:", ["--"] + df_v["display_vta"].tolist(), key="sel_pago_nuevo")
            
            if seleccion != "--":
                v = df_v[df_v['display_vta'] == seleccion].iloc[0]
                
                # Consultamos el total pagado desde la VISTA para ser precisos
                res_status = supabase.table("vista_estatus_lotes").select("total_pagado, enganche_req, estatus_actual").eq("ubicacion_id", v['ubicacion_id']).execute()
                status_data = res_status.data[0] if res_status.data else {"total_pagado": 0, "enganche_req": 0, "estatus_actual": "DESPONIBLE"}

                eng_req = float(status_data['enganche_req'])
                pagado_actual = float(status_data['total_pagado'])
                faltante_eng = max(0.0, eng_req - pagado_actual)
                
                if status_data['estatus_actual'] == "APARTADO":
                    st.warning(f"⚠️ **ESTADO: APARTADO** (Faltan $ {faltante_eng:,.2f} para cubrir el enganche)")
                else:
                    st.success(f"🟢 **ESTADO: {status_data['estatus_actual']}**")

                with st.form("form_pago_sql", clear_on_submit=True):
                    c1, c2, c3 = st.columns(3)
                    f_fec = c1.date_input("Fecha de Pago", value=datetime.now())
                    f_met = c2.selectbox("Método", ["Efectivo", "Transferencia", "Depósito", "Tarjeta"])
                    f_fol = c3.text_input("Folio / Referencia")
                    f_mon = st.number_input("Importe a Recibir ($)", min_value=0.01, value=faltante_eng if faltante_eng > 0 else 5000.0)
                    f_com = st.text_area("Notas / Comentarios")
                    
                    if st.form_submit_button("✅ REGISTRAR PAGO", type="primary"):
                        try:
                            supabase.table("pagos").insert({
                                "venta_id": int(v['id']), 
                                "fecha": str(f_fec), 
                                "monto": f_mon,
                                "metodo": f_met, 
                                "folio": f_fol, 
                                "comentarios": f_com
                            }).execute()
                            st.success("¡Pago registrado exitosamente!"); st.rerun()
                        except Exception as e: st.error(f"Error: {e}")

    # --- PESTAÑA 2: HISTORIAL ---
    with tab_historial:
        if not df_p.empty:
            df_hist = df_p.copy()
            df_hist['Lote'] = df_hist['venta'].apply(lambda x: f"M{int(x['ubicacion']['manzana']):02d}-L{int(x['ubicacion']['lote']):02d}" if x else "N/A")
            df_hist['Cliente'] = df_hist['venta'].apply(lambda x: x['cliente']['nombre'] if x else "N/A")
            st.metric("Total Recaudado", f"$ {df_hist['monto'].sum():,.2f}")
            st.dataframe(df_hist[["fecha", "Lote", "Cliente", "monto", "metodo", "folio", "comentarios"]], use_container_width=True, hide_index=True)
        else:
            st.info("No hay historial de pagos.")

    # --- PESTAÑA 3: ADMINISTRAR ---
    with tab_admin:
        if not df_p.empty:
            df_admin_p = df_p.dropna(subset=['venta']).copy()
            df_admin_p['pago_display'] = df_admin_p.apply(
                lambda x: f"{x['fecha']} | M{int(x['venta']['ubicacion']['manzana']):02d}-L{int(x['venta']['ubicacion']['lote']):02d} | ${x['monto']:,.2f}", axis=1
            )
            
            pago_sel = st.selectbox("Seleccione un pago para modificar:", ["--"] + df_admin_p['pago_display'].tolist())
            
            if pago_sel != "--":
                p_data = df_admin_p[df_admin_p['pago_display'] == pago_sel].iloc[0]
                
                with st.form("form_edit_pago"):
                    e_monto = st.number_input("Monto ($)", value=float(p_data['monto']))
                    e_folio = st.text_input("Folio", value=p_data['folio'] if p_data['folio'] else "")
                    e_coment = st.text_area("Comentarios", value=p_data['comentarios'] if p_data['comentarios'] else "")
                    
                    col1, col2 = st.columns(2)
                    if col1.form_submit_button("💾 GUARDAR"):
                        supabase.table("pagos").update({"monto": e_monto, "folio": e_folio, "comentarios": e_coment}).eq("id", p_data['id']).execute()
                        st.success("Actualizado."); st.rerun()
                    
                    if col2.form_submit_button("🗑️ ELIMINAR"):
                        supabase.table("pagos").delete().eq("id", p_data['id']).execute()
                        st.warning("Pago eliminado."); st.rerun()
