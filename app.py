import streamlit as st
from supabase import create_client, Client

# --- 1. CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="Valle Mart - Sistema de Gestión",
    page_icon="🏘️",
    layout="wide"
)

# Importación de tus módulos
from modulos import (
    inicio, 
    ubicaciones, 
    directorio,
    ventas, 
    cobranza, 
    credito, 
    comisiones, 
    gastos
)

# --- 2. CONEXIÓN A SUPABASE ---
SUPABASE_URL = st.secrets["supabase_url"]
SUPABASE_KEY = st.secrets["supabase_key"]

@st.cache_resource
def init_connection():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = init_connection()

# --- 3. ESTILOS PERSONALIZADOS ---
st.markdown("""
    <style>
    .stButton>button { width: 100%; border-radius: 5px; }
    .stMetric { background-color: #f0f2f6; padding: 10px; border-radius: 10px; }
    [data-testid="stSidebar"] { background-color: #1a2634; }
    [data-testid="stSidebar"] .stMarkdown { color: white; }
    /* Ajuste para que el texto del radio button sea blanco */
    [data-testid="stSidebar"] label { color: white !important; }
    </style>
    """, unsafe_allow_html=True)

# --- 4. MENÚ LATERAL (Navegación) ---
with st.sidebar:
    st.markdown("<h1 style='text-align: center; color: white;'>🏘️ VALLE MART</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #8892b0;'>Gestión Inmobiliaria</p>", unsafe_allow_html=True)
    st.markdown("---")
    
    menu = st.radio(
        "📂 Menú Principal",
        ["🏠 Inicio", 
         "📍 Mapa de Lotes", 
         "👤 Directorio", 
         "📝 Ventas", 
         "💰 Cobranza", 
         "📊 Detalle de Crédito", 
         "🎖️ Comisiones", 
         "💸 Gastos"]
    )
    
    st.markdown("---")
    
    # BOTÓN DE ACTUALIZACIÓN MANUAL
    if st.button("🔄 Sincronizar Datos"):
        st.cache_resource.clear()
        st.rerun()
        
    st.caption("v2.1 - SQL Sync Active")

# --- 5. ENRUTADOR DE MÓDULOS ---
try:
    if menu == "🏠 Inicio":
        inicio.render_inicio(supabase)
        
    elif menu == "📍 Mapa de Lotes":
        # Usando el nombre de función que definimos en pasos anteriores
        ubicaciones.render_ubicaciones(supabase)
        
    elif menu == "👤 Directorio":
        directorio.render_directorio(supabase)
        
    elif menu == "📝 Ventas":
        ventas.render_ventas(supabase)
        
    elif menu == "💰 Cobranza":
        cobranza.render_cobranza(supabase)
        
    elif menu == "📊 Detalle de Crédito":
        credito.render_detalle_credito(supabase)
        
    elif menu == "🎖️ Comisiones":
        comisiones.render_comisiones(supabase)
        
    elif menu == "💸 Gastos":
        gastos.render_gastos(supabase)

except Exception as e:
    st.error(f"🚨 Error en la carga del módulo: {e}")
    st.info("Tip: Si acabas de hacer cambios en SQL, usa el botón 'Sincronizar Datos'.")
