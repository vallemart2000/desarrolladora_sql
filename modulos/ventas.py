import streamlit as st
import pandas as pd
from datetime import datetime

def render_ventas(supabase):
    st.title("📝 Gestión de Apartados y Ventas")

    # --- 1. CARGA DE DATOS DESDE SUPABASE ---
    try:
        res_dir = supabase.table("directorio").select("id, nombre, tipo").order("nombre").execute()
        res_ub = supabase.table("ubicaciones").select("*").order("manzana").order("lote").execute()
        
        # Traemos todas las ventas (incluyendo las canceladas para el historial)
        res_v = supabase.table("ventas").select("""
            *,
            cliente:directorio!cliente_id(nombre),
            vendedor:directorio!vendedor_id(nombre),
            ubicacion:ubicaciones(ubicacion_display, enganche_requerido)
        """).order("created_at", desc=True).execute()

        df_dir = pd.DataFrame(res_dir.data)
        df_u = pd.DataFrame(res_ub.data)
        df_v = pd.DataFrame(res_v.data)
    except Exception as e:
        st.error(f"Error al cargar datos: {e}")
        return

    tab_nueva, tab_editar, tab_lista = st.tabs(["✨ Nuevo Apartado", "✏️ Editor y Archivo", "📋 Historial"])

    # --- PESTAÑA 1: NUEVO APARTADO --- (Sin cambios)
    with tab_nueva:
        st.subheader("Registrar Intención de Compra (Apartado)")
        lotes_libres = df_u[df_u["estatus"] == "Disponible"]
        
        if lotes_libres.empty:
            st.warning("No hay lotes disponibles.")
        else:
            f_lote_txt = st.selectbox("📍 Seleccione Lote", ["--"] + lotes_libres["ubicacion_display"].tolist())
            
            if f_lote_txt != "--":
                row_u = lotes_libres[lotes_libres["ubicacion_display"] == f_lote_txt].iloc[0]
                id_lote = int(row_u['id'])
                costo_base = float(row_u['precio_lista'])
                eng_minimo = float(row_u['enganche_requerido'])
                
                st.info(f"💰 **Condiciones de Lista:** Precio: ${costo_base:,.2f} | Enganche Requerido: ${eng_minimo:,.2f}")

                with st.form("form_nueva_venta"):
                    c1, c2 = st.columns(2)
                    f_fec = c1.date_input("📅 Fecha de Registro", value=datetime.now())
                    vendedores_df = df_dir[df_dir["tipo"] == "Vendedor"]
                    f_vende_sel = c1.selectbox("👔 Vendedor", ["-- SELECCIONAR --"] + vendedores_df["nombre"].tolist())
                    clientes_df = df_dir[df_dir["tipo"] != "Vendedor"]
                    f_cli_sel = c2.selectbox("👤 Cliente", ["-- SELECCIONAR --"] + clientes_df["nombre"].tolist())
                    
                    st.markdown("---")
                    cf1, cf2 = st.columns(2)
                    f_tot = cf1.number_input("Precio de Venta Final ($)", min_value=0.0, value=costo_base)
                    f_comision = cf2.number_input("Comisión de Venta ($)", min_value=0.0, value=5000.0)
                    
                    if st.form_submit_button("💾 REGISTRAR APARTADO", type="primary"):
                        if f_cli_sel == "-- SELECCIONAR --" or f_vende_sel == "-- SELECCIONAR --":
                            st.error("❌ Seleccione cliente y vendedor.")
                        else:
                            id_cliente = int(df_dir[df_dir["nombre"] == f_cli_sel]["id"].iloc[0])
                            id_vendedor = int(df_dir[df_dir["nombre"] == f_vende_sel]["id"].iloc[0])

                            nueva_v_data = {
                                "lote_id": id_lote, "cliente_id": id_cliente,
                                "vendedor_id": id_vendedor, "precio_venta": f_tot,
                                "comision_monto": f_comision, "fecha_apartado": str(f_fec),
                                "estatus_venta": "Apartado"
                            }
                            try:
                                supabase.table("ventas").insert(nueva_v_data).execute()
                                supabase.table("ubicaciones").update({"estatus": "Apartado"}).eq("id", id_lote).execute()
                                st.success(f"✅ Lote {f_lote_txt} registrado como APARTADO."); st.rerun()
                            except Exception as e: st.error(f"Error: {e}")

    # --- PESTAÑA 2: EDITOR Y ARCHIVO (IMPLEMENTACIÓN DE CANCELACIÓN) ---
    with tab_editar:
        st.subheader("Modificar Datos de Contrato")
        # Filtramos para no editar ventas ya canceladas aquí (esas van al historial)
        df_editables = df_v[df_v["estatus_venta"] != "Cancelado"]
        
        if df_editables.empty:
            st.info("No hay registros activos para editar.")
        else:
            df_editables['display_name'] = df_editables.apply(lambda x: f"{x['ubicacion']['ubicacion_display']} - {x['cliente']['nombre']}", axis=1)
            edit_sel = st.selectbox("Seleccione Registro para editar", ["--"] + df_editables["display_name"].tolist())
            
            if edit_sel != "--":
                datos_v = df_editables[df_editables["display_name"] == edit_sel].iloc[0]
                
                with st.form("form_edit_vta"):
                    st.warning(f"Editando trato de: {datos_v['cliente']['nombre']}")
                    e_tot = st.number_input("Precio Final ($)", value=float(datos_v["precio_venta"]))
                    e_com = st.number_input("Comisión ($)", value=float(datos_v.get("comision_monto", 5000.0)))
                    
                    if st.form_submit_button("💾 ACTUALIZAR MONTOS"):
                        supabase.table("ventas").update({
                            "precio_venta": e_tot, "comision_monto": e_com
                        }).eq("id", datos_v['id']).execute()
                        st.success("Cambios guardados."); st.rerun()

                st.markdown("---")
                # NUEVA SECCIÓN: CANCELACIÓN INTELIGENTE
                with st.expander("🚫 Cancelar Contrato / Liberar Lote"):
                    st.error("Esta acción liberará el lote y cambiará el estatus de la venta a 'Cancelado'.")
                    
                    decision_comision = st.radio(
                        "¿Qué hacer con la comisión del vendedor?",
                        ["Mantener Comisión (Pago merecido)", "Anular Comisión (Error/Fraude)"],
                        help="Mantener: El vendedor sigue cobrando por haber traído el enganche inicial."
                    )

                    if st.button("Confirmar Cancelación de Venta", type="primary"):
                        try:
                            # 1. Cambiar estatus de la Venta a 'Cancelado'
                            supabase.table("ventas").update({
                                "estatus_venta": "Cancelado"
                            }).eq("id", datos_v['id']).execute()

                            # 2. Liberar el Lote
                            supabase.table("ubicaciones").update({
                                "estatus": "Disponible"
                            }).eq("id", datos_v['lote_id']).execute()

                            # 3. Lógica de Comisión
                            if "Anular" in decision_comision:
                                supabase.table("pagos_comisiones").delete().eq("venta_id", datos_v['id']).execute()
                                st.info("Registro de comisión eliminado.")
                            else:
                                st.info("Comisión preservada en el historial.")

                            st.success(f"Lote {datos_v['ubicacion']['ubicacion_display']} liberado correctamente.")
                            st.rerun()

                        except Exception as e:
                            st.error(f"Error al cancelar: {e}")

    # --- PESTAÑA 3: HISTORIAL ---
    with tab_lista:
        if not df_v.empty:
            st.subheader("📋 Resumen General de Movimientos")
            df_m = df_v.copy()
            df_m['Lote'] = df_m['ubicacion'].apply(lambda x: x['ubicacion_display'] if x else "N/A")
            df_m['Cliente'] = df_m['cliente'].apply(lambda x: x['nombre'] if x else "N/A")
            df_m['Vendedor'] = df_m['vendedor'].apply(lambda x: x['nombre'] if x else "N/A")
            
            df_final = df_m[["fecha_apartado", "Lote", "Cliente", "Vendedor", "precio_venta", "comision_monto", "estatus_venta"]]
            
            # Colorear el estatus para identificar cancelados rápido
            def color_estatus(val):
                color = 'red' if val == 'Cancelado' else ('orange' if val == 'Apartado' else 'green')
                return f'color: {color}'

            st.dataframe(
                df_final.style.format({"precio_venta": "$ {:,.2f}", "comision_monto": "$ {:,.2f}"})
                .applymap(color_estatus, subset=['estatus_venta']),
                use_container_width=True,
                hide_index=True
            )
