import streamlit as st
from supabase import create_client, Client

# Importación de tus módulos convertidos
from modulos import (
    inicio, 
    ubicaciones, 
    clientes, 
    ventas, 
    cobranza, 
    credito, 
    comisiones, 
    gastos
)

# --- 1. CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="Valle Mart - Sistema de Gestión",
    page_icon="🏘️",
    layout="wide"
)

# --- 2. CONEXIÓN A SUPABASE ---
# Estos datos los obtienes de Project Settings -> API en tu panel de Supabase
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
    </style>
    """, unsafe_allow_html=True)

# --- 4. MENÚ LATERAL (Navegación) ---
with st.sidebar:
    st.image("https://via.placeholder.com/150?text=VALLE+MART", width=150) # Pon aquí tu logo real
    st.title("Inmobiliaria")
    st.markdown("---")
    
    menu = st.radio(
        "📂 Menú Principal",
        ["🏠 Inicio", 
         "📍 Mapa de Lotes", 
         "👤 Clientes", 
         "📝 Nueva Venta", 
         "💰 Cobranza", 
         "📊 Detalle de Crédito", 
         "🎖️ Comisiones", 
         "💸 Gastos"]
    )
    
    st.markdown("---")
    st.caption("v2.0 - Migración SQL Completa")

# --- 5. ENRUTADOR DE MÓDULOS ---
# Cada módulo recibe ahora solo el objeto 'supabase'
try:
    if menu == "🏠 Inicio":
        inicio.render_inicio(supabase)
        
    elif menu == "📍 Mapa de Lotes":
        ubicaciones.render_ubicaciones(supabase)
        
    elif menu == "👤 Clientes":
        clientes.render_clientes(supabase)
        
    elif menu == "📝 Nueva Venta":
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
    st.info("Asegúrate de que todas las tablas estén creadas en Supabase.")
