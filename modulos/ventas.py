import streamlit as st
import pandas as pd
from datetime import datetime

def render_ventas(supabase):
    st.title("📝 Gestión de Apartados y Ventas")

    # --- 1. CARGA DE DATOS ---
    try:
        # 1.1 Traemos Directorio
        res_dir = supabase.table("directorio").select("id, nombre, tipo").order("nombre").execute()
        
        # 1.2 Traemos la VISTA para saber qué está disponible (estatus calculado)
        res_ub = supabase.table("vista_estatus_lotes").select("*").order("manzana").order("lote").execute()
        
        # 1.3 Traemos las Ventas con joins (ajustado a nuevos nombres de columna)
        # Nota: Ya no pedimos 'estatus_venta' porque la venta EXISTE implica apartado/vendido
        res_v = supabase.table("ventas").select("""
            *,
            cliente:directorio!cliente_id(nombre),
            vendedor:directorio!vendedor_id(nombre),
            ubicacion:ubicaciones(id, etapa, manzana, lote, enganche_req)
        """).execute()

        df_dir = pd.DataFrame(res_dir.data)
        df_u = pd.DataFrame(res_ub.data)
        df_v = pd.DataFrame(res_v.data)

        # Generamos el display name en Python para evitar errores de columna inexistente
        if not df_u.empty:
            df_u['display'] = df_u.apply(lambda x: f"E{x['etapa']}-M{x['manzana']}-L{x['lote']}", axis=1)
        
        if not df_v.empty:
            # Re-estructuramos el display para el historial
            df_v['display_lote'] = df_v['ubicacion'].apply(lambda x: f"E{x['etapa']}-M{x['manzana']}-L{x['lote']}" if x else "N/A")

    except Exception as e:
        st.error(f"Error al cargar datos: {e}")
        return

    tab_nueva, tab_editar, tab_lista = st.tabs(["✨ Nuevo Apartado", "✏️ Modificar Contrato", "📋 Historial"])

    # --- PESTAÑA 1: NUEVO APARTADO ---
    with tab_nueva:
        st.subheader("Registrar Intención de Compra")
        # Filtramos lotes que la VISTA dice que están DISPONIBLES
        lotes_libres = df_u[df_u["estatus_actual"] == "DISPONIBLE"]
        
        if lotes_libres.empty:
            st.warning("No hay lotes disponibles en este momento.")
        else:
            f_lote_txt = st.selectbox("📍 Seleccione Lote Disponible", ["--"] + lotes_libres["display"].tolist())
            
            if f_lote_txt != "--":
                row_u = lotes_libres[lotes_libres["display"] == f_lote_txt].iloc[0]
                id_lote = int(row_u['ubicacion_id'])
                costo_base = float(row_u['precio_lista'])
                eng_minimo = float(row_u['enganche_req'])
                
                st.info(f"💰 **Precio de Lista:** ${costo_base:,.2f} | **Enganche Requerido:** ${eng_minimo:,.2f}")

                with st.form("form_nueva_venta"):
                    c1, c2 = st.columns(2)
                    f_fec = c1.date_input("📅 Fecha de Registro", value=datetime.now())
                    
                    vendedores_df = df_dir[df_dir["tipo"] == "Vendedor"]
                    f_vende_sel = c1.selectbox("👔 Vendedor", ["--"] + vendedores_df["nombre"].tolist())
                    
                    clientes_df = df_dir[df_dir["tipo"] == "Cliente"]
                    f_cli_sel = c2.selectbox("👤 Cliente", ["--"] + clientes_df["nombre"].tolist())
                    
                    st.markdown("---")
                    cf1, cf2 = st.columns(2)
                    # El precio pactado puede ser diferente al de lista
                    f_tot = cf1.number_input("Precio Final Pactado ($)", min_value=0.0, value=costo_base)
                    f_comision = cf2.number_input("Comisión acordada ($)", min_value=0.0, value=0.0)
                    
                    if st.form_submit_button("💾 REGISTRAR APARTADO", type="primary"):
                        if f_cli_sel == "--" or f_vende_sel == "--":
                            st.error("❌ Por favor asigne un Cliente y un Vendedor.")
                        else:
                            id_cliente = int(df_dir[df_dir["nombre"] == f_cli_sel]["id"].iloc[0])
                            id_vendedor = int(df_dir[df_dir["nombre"] == f_vende_sel]["id"].iloc[0])

                            nueva_v_data = {
                                "ubicacion_id": id_lote, # Cambiado de lote_id
                                "cliente_id": id_cliente,
                                "vendedor_id": id_vendedor,
                                "fecha_venta": str(f_fec), # Cambiado de fecha_apartado
                                "comision_monto": f_comision
                                # Ya no enviamos estatus_venta
                            }
                            try:
                                supabase.table("ventas").insert(nueva_v_data).execute()
                                st.success(f"✅ Lote {f_lote_txt} registrado correctamente."); st.rerun()
                            except Exception as e: 
                                st.error(f"Error al insertar: {e}")

    # --- PESTAÑA 2: EDITOR (SIMPLIFICADO) ---
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
                    # Note: En tu tabla 'ventas' no definimos 'precio_pactado', pero si quieres guardarlo, 
                    # deberías agregarlo a la tabla. De momento usamos comision_monto.
                    e_com = st.number_input("Ajustar Comisión ($)", value=float(datos_v.get("comision_monto", 0.0)))
                    
                    if st.form_submit_button("💾 ACTUALIZAR"):
                        supabase.table("ventas").update({
                            "comision_monto": e_com
                        }).eq("id", datos_v['id']).execute()
                        st.success("Cambios guardados."); st.rerun()

                if st.button("🗑️ Eliminar Registro de Venta"):
                    # Al borrar la venta, el lote vuelve a ser DISPONIBLE automáticamente en la Vista
                    supabase.table("ventas").delete().eq("id", datos_v['id']).execute()
                    st.warning("Venta eliminada. El lote ha sido liberado.")
                    st.rerun()

    # --- PESTAÑA 3: HISTORIAL (CON LA VISTA) ---
    with tab_lista:
        if not df_v.empty:
            st.subheader("📋 Resumen de Ventas")
            # Unimos los datos para mostrar una tabla clara
            # Aquí podrías volver a llamar a la VISTA para tener el estatus "Vendido" o "Apartado" real
            res_final = supabase.table("vista_estatus_lotes").select("*").filter("estatus_actual", "neq", "DISPONIBLE").execute()
            df_final_view = pd.DataFrame(res_final.data)
            
            if not df_final_view.empty:
                st.dataframe(
                    df_final_view[["manzana", "lote", "etapa", "precio_lista", "total_pagado", "estatus_actual"]],
                    column_config={
                        "precio_lista": st.column_config.NumberColumn("Precio", format="$%,.2f"),
                        "total_pagado": st.column_config.NumberColumn("Pagado", format="$%,.2f"),
                        "estatus_actual": "Estado"
                    },
                    use_container_width=True, hide_index=True
                )
