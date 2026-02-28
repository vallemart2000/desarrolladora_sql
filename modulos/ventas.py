import streamlit as st
import pandas as pd
from datetime import datetime

def render_ventas(supabase):
    st.title("📝 Gestión de Apartados y Ventas")

    # --- 1. CARGA DE DATOS ---
    try:
        res_dir = supabase.table("directorio").select("id, nombre, tipo").order("nombre").execute()
        res_ub = supabase.table("vista_estatus_lotes").select("*").order("etapa").order("manzana").order("lote").execute()
        
        # IMPORTANTE: Seleccionamos 'plazo' explícitamente
        res_v = supabase.table("ventas").select("""
            *,
            cliente:directorio!cliente_id(nombre),
            vendedor:directorio!vendedor_id(nombre),
            ubicacion:ubicaciones(id, etapa, manzana, lote, precio, enganche_req)
        """).execute()

        df_dir = pd.DataFrame(res_dir.data)
        df_u = pd.DataFrame(res_ub.data)
        df_v = pd.DataFrame(res_v.data)

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
            st.warning("No hay lotes disponibles.")
        else:
            f_lote_txt = st.selectbox("📍 Seleccione Lote", ["--"] + lotes_libres["display"].tolist())
            
            if f_lote_txt != "--":
                row_u = lotes_libres[lotes_libres["display"] == f_lote_txt].iloc[0]
                
                with st.form("form_nueva_venta"):
                    c1, c2 = st.columns(2)
                    f_fec = c1.date_input("📅 Fecha de Registro", value=datetime.now())
                    f_vende_sel = c1.selectbox("👔 Vendedor", ["--"] + df_dir[df_dir["tipo"] == "Vendedor"]["nombre"].tolist())
                    f_cli_sel = c2.selectbox("👤 Cliente", ["--"] + df_dir[df_dir["tipo"] == "Cliente"]["nombre"].tolist())
                    
                    st.markdown("---")
                    cf1, cf2, cf3 = st.columns(3) # Añadimos tercera columna
                    f_tot = cf1.number_input("Precio Pactado ($)", min_value=0.0, value=float(row_u['precio_lista']))
                    f_plazo = cf2.number_input("Plazo (Meses)", min_value=1, max_value=240, value=36, step=1)
                    f_comision = cf3.number_input("Comisión ($)", min_value=0.0, value=5000.0, step=500.0)
                    
                    if st.form_submit_button("💾 REGISTRAR APARTADO", type="primary"):
                        if f_cli_sel == "--" or f_vende_sel == "--":
                            st.error("❌ Complete los datos de Cliente y Vendedor.")
                        else:
                            id_cliente = int(df_dir[df_dir["nombre"] == f_cli_sel]["id"].iloc[0])
                            id_vendedor = int(df_dir[df_dir["nombre"] == f_vende_sel]["id"].iloc[0])

                            nueva_v_data = {
                                "ubicacion_id": int(row_u['ubicacion_id']),
                                "cliente_id": id_cliente,
                                "vendedor_id": id_vendedor,
                                "fecha_venta": str(f_fec),
                                "comision_monto": f_comision,
                                "plazo": int(f_plazo) # Guardamos el plazo
                            }
                            try:
                                supabase.table("ventas").insert(nueva_v_data).execute()
                                st.success("✅ Registro exitoso.")
                                st.rerun()
                            except Exception as e: 
                                st.error(f"Error: {e}")

    # --- PESTAÑA 2: EDITOR ---
    with tab_editar:
        st.subheader("Modificar Contrato Existente")
        if df_v.empty:
            st.info("No hay ventas para editar.")
        else:
            df_v['edit_label'] = df_v.apply(lambda x: f"{x['display_lote']} - {x['cliente']['nombre']}", axis=1)
            edit_sel = st.selectbox("Seleccione Contrato", ["--"] + df_v["edit_label"].tolist())
            
            if edit_sel != "--":
                datos_v = df_v[df_v["edit_label"] == edit_sel].iloc[0]
                
                with st.form("form_edit_vta"):
                    st.warning(f"Editando Lote: {datos_v['display_lote']}")
                    ce1, ce2 = st.columns(2)
                    e_plazo = ce1.number_input("Ajustar Plazo (Meses)", value=int(datos_v.get("plazo", 36)))
                    e_com = ce2.number_input("Ajustar Comisión ($)", value=float(datos_v.get("comision_monto", 0.0)))
                    
                    if st.form_submit_button("💾 ACTUALIZAR"):
                        supabase.table("ventas").update({
                            "comision_monto": e_com,
                            "plazo": e_plazo
                        }).eq("id", datos_v['id']).execute()
                        st.success("Cambios guardados."); st.rerun()

    # --- PESTAÑA 3: HISTORIAL ---
    with tab_lista:
        if not df_v.empty:
            st.subheader("📋 Ventas Activas")
            # Unimos los datos para ver el plazo en la tabla de historial
            df_historial = df_v.copy()
            df_historial['vendedor_nom'] = df_historial['vendedor'].apply(lambda x: x['nombre'] if x else 'N/A')
            
            st.dataframe(
                df_historial[["display_lote", "fecha_venta", "plazo", "comision_monto"]],
                column_config={
                    "display_lote": "Lote",
                    "fecha_venta": "Fecha",
                    "plazo": st.column_config.NumberColumn("Plazo (meses)"),
                    "comision_monto": st.column_config.NumberColumn("Comisión", format="$%,.2f"),
                },
                use_container_width=True, hide_index=True
            )
