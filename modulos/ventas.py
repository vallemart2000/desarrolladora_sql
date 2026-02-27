import streamlit as st
import pandas as pd
from datetime import datetime

def render_ventas(supabase):
    st.title("📝 Gestión de Apartados y Ventas")

    # --- 1. CARGA DE DATOS ---
    try:
        res_dir = supabase.table("directorio").select("id, nombre, tipo").order("nombre").execute()
        res_ub = supabase.table("vista_estatus_lotes").select("*").order("etapa").order("manzana").order("lote").execute()
        
        res_v = supabase.table("ventas").select("""
            *,
            cliente:directorio!cliente_id(nombre),
            vendedor:directorio!vendedor_id(nombre),
            ubicacion:ubicaciones(id, etapa, manzana, lote, precio, enganche_req)
        """).execute()

        df_dir = pd.DataFrame(res_dir.data)
        df_u = pd.DataFrame(res_ub.data)
        df_v = pd.DataFrame(res_v.data)

        # 1.1 GENERAR DISPLAY PARA SELECTBOX (Nuevo Requerimiento)
        if not df_u.empty:
            df_u['display'] = df_u.apply(
                lambda x: f"M{int(x['manzana']):02d}-L{int(x['lote']):02d} | ${x['precio_lista']:,.0f} | Eng. ${x['enganche_req']:,.0f}", 
                axis=1
            )
        
        if not df_v.empty:
            df_v['display_lote'] = df_v['ubicacion'].apply(
                lambda x: f"M{int(x['manzana']):02d}-L{int(x['lote']):02d}" if x else "N/A"
            )

    except Exception as e:
        st.error(f"Error al cargar datos: {e}")
        return

    tab_nueva, tab_editar, tab_lista = st.tabs(["✨ Nuevo Apartado", "✏️ Modificar Contrato", "📋 Historial"])

    # --- PESTAÑA 1: NUEVO APARTADO ---
    with tab_nueva:
        st.subheader("Registrar Intención de Compra")
        lotes_libres = df_u[df_u["estatus_actual"] == "DISPONIBLE"]
        
        if lotes_libres.empty:
            st.warning("No hay lotes disponibles en este momento.")
        else:
            f_lote_txt = st.selectbox("📍 Seleccione Lote (Referencia | Precio | Enganche)", ["--"] + lotes_libres["display"].tolist())
            
            if f_lote_txt != "--":
                row_u = lotes_libres[lotes_libres["display"] == f_lote_txt].iloc[0]
                id_lote = int(row_u['ubicacion_id'])
                costo_base = float(row_u['precio_lista'])
                
                st.success(f"Seleccionado: **{f_lote_txt.split(' | ')[0]}**")

                with st.form("form_nueva_venta"):
                    c1, c2 = st.columns(2)
                    f_fec = c1.date_input("📅 Fecha de Registro", value=datetime.now())
                    
                    vendedores_df = df_dir[df_dir["tipo"] == "Vendedor"]
                    f_vende_sel = c1.selectbox("👔 Vendedor", ["--"] + vendedores_df["nombre"].tolist())
                    
                    clientes_df = df_dir[df_dir["tipo"] == "Cliente"]
                    f_cli_sel = c2.selectbox("👤 Cliente", ["--"] + clientes_df["nombre"].tolist())
                    
                    st.markdown("---")
                    cf1, cf2 = st.columns(2)
                    f_tot = cf1.number_input("Precio Final Pactado ($)", min_value=0.0, value=costo_base)
                    
                    # El secreto es el parámetro 'value' y asegurarnos que sea float
                    f_comision = cf2.number_input(
                        "Comisión acordada ($)", 
                        min_value=0.0, 
                        value=5000.0, 
                        step=500.0,
                        format="%.2f"
                    )
                    
                    if st.form_submit_button("💾 REGISTRAR APARTADO", type="primary"):
                        if f_cli_sel == "--" or f_vende_sel == "--":
                            st.error("❌ Por favor asigne un Cliente y un Vendedor.")
                        else:
                            id_cliente = int(df_dir[df_dir["nombre"] == f_cli_sel]["id"].iloc[0])
                            id_vendedor = int(df_dir[df_dir["nombre"] == f_vende_sel]["id"].iloc[0])

                            nueva_v_data = {
                                "ubicacion_id": id_lote,
                                "cliente_id": id_cliente,
                                "vendedor_id": id_vendedor,
                                "fecha_venta": str(f_fec),
                                "comision_monto": f_comision
                            }
                            try:
                                supabase.table("ventas").insert(nueva_v_data).execute()
                                st.success("✅ Registro exitoso.")
                                st.rerun()
                            except Exception as e: 
                                st.error(f"Error: {e}")

    # --- PESTAÑA 2: EDITOR ---
    with tab_editar:
        st.subheader("Modificar Montos de Contrato")
        if df_v.empty:
            st.info("No hay ventas registradas.")
        else:
            df_v['edit_label'] = df_v.apply(lambda x: f"{x['display_lote']} - {x['cliente']['nombre']}", axis=1)
            edit_sel = st.selectbox("Seleccione Contrato", ["--"] + df_v["edit_label"].tolist())
            
            if edit_sel != "--":
                datos_v = df_v[df_v["edit_label"] == edit_sel].iloc[0]
                
                with st.form("form_edit_vta"):
                    st.warning(f"Editando valores para Lote: {datos_v['display_lote']}")
                    e_com = st.number_input("Ajustar Comisión ($)", value=float(datos_v.get("comision_monto", 0.0)))
                    
                    if st.form_submit_button("💾 ACTUALIZAR"):
                        supabase.table("ventas").update({"comision_monto": e_com}).eq("id", datos_v['id']).execute()
                        st.success("Cambios guardados."); st.rerun()

                if st.button("🗑️ Eliminar Registro de Venta"):
                    supabase.table("ventas").delete().eq("id", datos_v['id']).execute()
                    st.warning("Venta eliminada. El lote ha sido liberado.")
                    st.rerun()

    # --- PESTAÑA 3: HISTORIAL ---
    with tab_lista:
        if not df_v.empty:
            st.subheader("📋 Resumen de Ventas Activas")
            res_final = supabase.table("vista_estatus_lotes").select("*").filter("estatus_actual", "neq", "DISPONIBLE").execute()
            df_final_view = pd.DataFrame(res_final.data)
            
            if not df_final_view.empty:
                # Generar referencia limpia para la tabla de historial
                df_final_view['Ref'] = df_final_view.apply(lambda x: f"M{int(x['manzana']):02d}-L{int(x['lote']):02d}", axis=1)
                
                st.dataframe(
                    df_final_view[["Ref", "etapa", "precio_lista", "total_pagado", "estatus_actual"]],
                    column_config={
                        "precio_lista": st.column_config.NumberColumn("Precio Lista", format="$%,.2f"),
                        "total_pagado": st.column_config.NumberColumn("Total Pagado", format="$%,.2f"),
                        "estatus_actual": "Estado"
                    },
                    use_container_width=True, hide_index=True
                )
