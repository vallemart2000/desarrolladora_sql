import streamlit as st
import pandas as pd

def render_ubicaciones(supabase):
    st.title("📍 Gestión de Ubicaciones")

    # --- FORMULARIO PARA NUEVO LOTE ---
    with st.expander("➕ Registrar Nuevo Lote"):
        with st.form("form_nueva_ubicacion"):
            col1, col2, col3 = st.columns(3)
            fase = col1.text_input("Fase")
            manzana = col2.text_input("Manzana")
            lote = col3.text_input("Lote")
            
            precio = st.number_input("Precio de Lista", min_value=0.0, step=1000.0)
            estatus = st.selectbox("Estatus Inicial", ["Disponible", "Apartado", "Vendido"])
            
            if st.form_submit_button("Guardar Lote"):
                nueva_data = {
                    "fase": fase,
                    "manzana": manzana,
                    "lote": lote,
                    "precio_lista": precio,
                    "estatus": estatus
                }
                # INSERTAR EN SUPABASE
                try:
                    supabase.table("ubicaciones").insert(nueva_data).execute()
                    st.success(f"Lote {lote} Mza {manzana} guardado!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")

    # --- TABLA DE DATOS ---
    st.subheader("Inventario Actual")
    res = supabase.table("ubicaciones").select("*").order("fase", desc=False).execute()
    df = pd.DataFrame(res.data)

    if not df.empty:
        # Mostramos la tabla con opción de edición rápida
        st.data_editor(
            df,
            column_config={
                "id": None, # Ocultamos el ID para que el usuario no lo toque
                "precio_lista": st.column_config.NumberColumn(format="$ %.2f"),
                "estatus": st.column_config.SelectboxColumn(options=["Disponible", "Apartado", "Vendido"])
            },
            disabled=["id"],
            key="editor_ubicaciones",
            use_container_width=True
        )
        
        if st.button("💾 Guardar Cambios de la Tabla"):
            # Aquí agregaríamos la lógica para actualizar cambios en masa
            st.info("Lógica de actualización masiva pendiente (podemos hacerla en el siguiente paso)")
    else:
        st.info("No hay ubicaciones registradas aún.")
