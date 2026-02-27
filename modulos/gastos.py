import streamlit as st
import pandas as pd
from datetime import datetime

def render_gastos(supabase):
    st.title("💸 Gestión de Gastos")
    
    # --- 1. CARGA DE DATOS ---
    res = supabase.table("gastos").select("*").order("fecha", desc=True).execute()
    df_g = pd.DataFrame(res.data)

    # --- 2. VISTA GENERAL ---
    st.write("### 🔍 Historial de Gastos")
    if not df_g.empty:
        total_gastos = df_g["monto"].sum()
        st.metric("Gasto Total Acumulado", f"$ {total_gastos:,.2f}")

        st.dataframe(
            df_g[["fecha", "categoria", "monto", "concepto", "notas"]],
            column_config={
                "monto": st.column_config.NumberColumn("Monto", format="$ %.2f"),
                "fecha": st.column_config.DateColumn("Fecha", format="DD/MM/YYYY")
            },
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("No hay gastos registrados aún.")

    tab_nuevo, tab_editar = st.tabs(["✨ Registrar Gasto", "✏️ Editar / Eliminar"])

    categorias = ["Publicidad", "Comisiones", "Mantenimiento", "Papelería", "Servicios", "Sueldos", "Otros"]

    # --- PESTAÑA 1: REGISTRAR ---
    with tab_nuevo:
        with st.form("form_nuevo_gasto"):
            c1, c2 = st.columns(2)
            f_fec = c1.date_input("📅 Fecha", value=datetime.now())
            f_cat = c2.selectbox("📂 Categoría", categorias)
            f_mon = c1.number_input("💵 Monto ($)", min_value=0.0, step=100.0)
            f_des = c2.text_input("📝 Descripción", placeholder="Ej: Pago de Luz")
            f_not = st.text_area("🗒️ Notas adicionales")

            if st.form_submit_button("✅ REGISTRAR GASTO", type="primary"):
                if f_mon <= 0:
                    st.error("El monto debe ser mayor a $0")
                else:
                    nuevo_gasto = {
                        "fecha": str(f_fec),
                        "categoria": f_cat,
                        "monto": f_mon,
                        "concepto": f_des,
                        "notas": f_not
                    }
                    supabase.table("gastos").insert(nuevo_gasto).execute()
                    st.success("Gasto registrado correctamente.")
                    st.rerun()

    # --- PESTAÑA 2: EDITAR / ELIMINAR ---
    with tab_editar:
        if not df_g.empty:
            # Selector basado en el ID real de la DB
            gastos_opciones = {f"{r['id']} | {r['fecha']} | {r['concepto']}": r for r in df_g.to_dict('records')}
            g_sel_key = st.selectbox("Seleccione gasto a modificar:", ["--"] + list(gastos_opciones.keys()))
            
            if g_sel_key != "--":
                gasto_data = gastos_opciones[g_sel_key]
                g_id = gasto_data['id']

                with st.form("form_edit_gasto"):
                    ce1, ce2 = st.columns(2)
                    e_fec = ce1.date_input("Fecha", value=pd.to_datetime(gasto_data["fecha"]))
                    
                    try: idx_cat = categorias.index(gasto_data["categoria"])
                    except: idx_cat = 0
                    
                    e_cat = ce2.selectbox("Categoría", categorias, index=idx_cat)
                    e_mon = ce1.number_input("Monto ($)", min_value=0.0, value=float(gasto_data["monto"]))
                    e_des = ce2.text_input("Concepto", value=str(gasto_data["concepto"]))
                    e_not = st.text_area("Notas", value=str(gasto_data["notas"] or ""))
                    
                    b1, b2 = st.columns(2)
                    if b1.form_submit_button("💾 GUARDAR CAMBIOS"):
                        update_data = {
                            "fecha": str(e_fec),
                            "categoria": e_cat,
                            "monto": e_mon,
                            "concepto": e_des,
                            "notas": e_not
                        }
                        supabase.table("gastos").update(update_data).eq("id", g_id).execute()
                        st.success("Gasto actualizado.")
                        st.rerun()
                        
                    if b2.form_submit_button("🗑️ ELIMINAR GASTO"):
                        supabase.table("gastos").delete().eq("id", g_id).execute()
                        st.warning("Gasto eliminado.")
                        st.rerun()
