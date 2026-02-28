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
        st.subheader("1. Seleccione un Lote Disponible")
        lotes_libres = df_u[df_u["estatus_actual"] == "DISPONIBLE"].copy()
        
        if lotes_libres.empty:
            st.warning("No hay lotes disponibles.")
        else:
            lotes_libres['Ref'] = lotes_libres.apply(lambda x: f"M{int(x['manzana']):02d}-L{int(x['lote']):02d}", axis=1)
            
            event = st.dataframe(
                lotes_libres[["Ref", "etapa", "precio_lista", "enganche_req"]],
                column_config={
                    "Ref": "Lote",
                    "etapa": "Etapa",
                    "precio_lista": st.column_config.NumberColumn("Precio ($)", format="dollar"),
                    "enganche_req": st.column_config.NumberColumn("Enganche ($)", format="dollar"),
                },
                use_container_width=True,
                hide_index=True,
                on_select="rerun",
                selection_mode="single-row"
            )

            if len(event.selection.rows) > 0:
                idx_seleccionado = event.selection.rows[0]
                row_u = lotes_libres.iloc[idx_seleccionado]
                
                st.markdown("---")
                st.subheader(f"2. Formulario de Registro: {row_u['Ref']}")

                with st.form("form_nueva_venta", clear_on_submit=True):
                    # 1 y 2. Cliente y Vendedor
                    col_pers = st.columns(2)
                    f_cli_sel = col_pers[0].selectbox("👤 1. Cliente", ["--"] + df_dir[df_dir["tipo"] == "Cliente"]["nombre"].tolist())
                    f_vende_sel = col_pers[1].selectbox("👔 2. Vendedor", ["--"] + df_dir[df_dir["tipo"] == "Vendedor"]["nombre"].tolist())

                    # 3, 4 y 5. Precio, Plazo y Comisión
                    st.markdown(" ")
                    col_money = st.columns(3)
                    f_tot = col_money[0].number_input("💰 3. Precio Pactado ($)", min_value=0.0, value=float(row_u['precio_lista']), format="%.2f")
                    f_plazo = col_money[1].number_input("📅 4. Plazo (Meses)", min_value=1, max_value=240, value=48, step=1)
                    f_comision = col_money[2].number_input("💸 5. Comisión ($)", min_value=0.0, value=5000.0, step=500.0, format="%.2f")

                    # 6. Fecha (Al final para mejor visualización del calendario)
                    st.markdown(" ")
                    f_fec = st.date_input("🗓️ 6. Fecha de Registro / Contrato", value=datetime.now())

                    st.markdown("---")
                    if st.form_submit_button("💾 FINALIZAR Y GUARDAR APARTADO", type="primary", use_container_width=True):
                        if f_cli_sel == "--" or f_vende_sel == "--":
                            st.error("❌ Por favor, seleccione un Cliente y un Vendedor.")
                        else:
                            id_cliente = int(df_dir[df_dir["nombre"] == f_cli_sel]["id"].iloc[0])
                            id_vendedor = int(df_dir[df_dir["nombre"] == f_vende_sel]["id"].iloc[0])

                            nueva_v_data = {
                                "ubicacion_id": int(row_u['ubicacion_id']),
                                "cliente_id": id_cliente,
                                "vendedor_id": id_vendedor,
                                "fecha_venta": str(f_fec),
                                "comision_monto": f_comision,
                                "plazo": int(f_plazo),
                                "precio_final": f_tot # Asegúrate de tener esta columna o cámbiala por la que uses
                            }
                            try:
                                supabase.table("ventas").insert(nueva_v_data).execute()
                                st.success(f"✅ ¡Venta de {row_u['Ref']} registrada exitosamente!")
                                st.rerun()
                            except Exception as e: 
                                st.error(f"Error al insertar en base de datos: {e}")
            else:
                st.info("💡 Selecciona un lote en la tabla de arriba para habilitar el formulario.")

    # --- PESTAÑAS 2 Y 3 (Se mantienen con el formato dollar en tablas) ---
    with tab_editar:
        if df_v.empty:
            st.info("No hay ventas registradas.")
        else:
            df_v['edit_label'] = df_v.apply(lambda x: f"{x['display_lote']} - {x['cliente']['nombre']}", axis=1)
            edit_sel = st.selectbox("Seleccione Contrato para modificar", ["--"] + df_v["edit_label"].tolist())
            
            if edit_sel != "--":
                datos_v = df_v[df_v["edit_label"] == edit_sel].iloc[0]
                with st.form("form_edit_vta"):
                    st.warning(f"Modificando Lote: {datos_v['display_lote']}")
                    ce1, ce2 = st.columns(2)
                    e_plazo = ce1.number_input("Ajustar Plazo", value=int(datos_v.get("plazo", 48)))
                    e_com = ce2.number_input("Ajustar Comisión ($)", value=float(datos_v.get("comision_monto", 5000.0)), format="%.2f")
                    if st.form_submit_button("💾 GUARDAR CAMBIOS"):
                        supabase.table("ventas").update({"comision_monto": e_com, "plazo": e_plazo}).eq("id", datos_v['id']).execute()
                        st.success("Contrato actualizado."); st.rerun()

    with tab_lista:
        if not df_v.empty:
            st.dataframe(
                df_v[["display_lote", "fecha_venta", "plazo", "comision_monto"]],
                column_config={
                    "display_lote": "Lote",
                    "fecha_venta": "Fecha Venta",
                    "plazo": "Meses",
                    "comision_monto": st.column_config.NumberColumn("Comisión", format="dollar"),
                },
                use_container_width=True, hide_index=True
            )
