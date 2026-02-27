import streamlit as st
from supabase import create_client

# Conexión (Asegúrate de tener tus secrets configurados)
supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

def guardar_nuevo_cliente(nombre, tel, mail):
    data = {"nombre": nombre, "telefono": tel, "correo": mail}
    # Esto reemplaza el .append_row que usabas en GSheets
    supabase.table("clientes").insert(data).execute()
    st.success("¡Cliente guardado con éxito!")

# --- UI DE PRUEBA ---
st.title("Valle Mart 2.0")

with st.form("nuevo_cliente"):
    st.write("### Registrar Cliente")
    nom = st.text_input("Nombre Completo")
    tel = st.text_input("Teléfono")
    ema = st.text_input("Email")
    if st.form_submit_button("Guardar en SQL"):
        guardar_nuevo_cliente(nom, tel, ema)

# Mostrar tabla actualizada
res = supabase.table("clientes").select("*").execute()
df_clientes = pd.DataFrame(res.data)
st.dataframe(df_clientes)
