import streamlit as st
import sqlite3
import bcrypt
import pandas as pd
from datetime import datetime

# ==========================================
# 1. CONFIGURACIÓN Y BASE DE DATOS
# ==========================================
st.set_page_config(page_title="SmartPyme Dashboard", layout="wide")

def init_db():
    conn = sqlite3.connect('smartpyme.db')
    c = conn.cursor()
    # Tabla de Mipymes (Usuarios)
    c.execute('''CREATE TABLE IF NOT EXISTS empresas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT UNIQUE,
                    password BLOB)''')
    # Tabla de Inventario
    c.execute('''CREATE TABLE IF NOT EXISTS productos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    empresa_id INTEGER,
                    nombre TEXT,
                    categoria TEXT,
                    stock INTEGER,
                    stock_minimo INTEGER,
                    precio_venta REAL,
                    costo REAL)''')
    # Tabla de Ventas
    c.execute('''CREATE TABLE IF NOT EXISTS ventas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    empresa_id INTEGER,
                    producto_id INTEGER,
                    nombre_producto TEXT,
                    cantidad INTEGER,
                    total REAL,
                    fecha TEXT)''')
    conn.commit()
    return conn

conn = init_db()

# ==========================================
# 2. SEGURIDAD Y AUTENTICACIÓN
# ==========================================
def hash_password(password):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

def check_password(password, hashed):
    return bcrypt.checkpw(password.encode('utf-8'), hashed)

if 'empresa_id' not in st.session_state:
    st.session_state['empresa_id'] = None
if 'empresa_email' not in st.session_state:
    st.session_state['empresa_email'] = None

def login_register_ui():
    st.title("🔐 Acceso a SmartPyme")
    tab1, tab2 = st.tabs(["Iniciar Sesión", "Registrar Empresa"])
    
    with tab1:
        email_login = st.text_input("Correo Electrónico", key="login_email")
        pass_login = st.text_input("Contraseña", type="password", key="login_pass")
        if st.button("Ingresar"):
            c = conn.cursor()
            c.execute("SELECT id, password FROM empresas WHERE email=?", (email_login,))
            user = c.fetchone()
            if user and check_password(pass_login, user[1]):
                st.session_state['empresa_id'] = user[0]
                st.session_state['empresa_email'] = email_login
                st.rerun()
            else:
                st.error("Credenciales incorrectas")

    with tab2:
        email_reg = st.text_input("Nuevo Correo Electrónico")
        pass_reg = st.text_input("Nueva Contraseña", type="password")
        if st.button("Registrar Mipyme"):
            if email_reg and pass_reg:
                try:
                    c = conn.cursor()
                    c.execute("INSERT INTO empresas (email, password) VALUES (?, ?)", 
                              (email_reg, hash_password(pass_reg)))
                    conn.commit()
                    st.success("Empresa registrada. Ahora puedes iniciar sesión.")
                except sqlite3.IntegrityError:
                    st.error("Este correo ya está registrado.")
            else:
                st.warning("Completa todos los campos.")

# ==========================================
# 3. MÓDULOS DE LA APLICACIÓN
# ==========================================
def app_ui():
    st.sidebar.title(f"🏢 {st.session_state['empresa_email']}")
    menu = st.sidebar.radio("Navegación", ["📊 Dashboard", "📦 Inventario", "💰 Nueva Venta"])
    
    if st.sidebar.button("Cerrar Sesión"):
        st.session_state['empresa_id'] = None
        st.rerun()

    empresa_id = st.session_state['empresa_id']

    # --- MÓDULO DE INVENTARIO ---
    if menu == "📦 Inventario":
        st.header("Gestión de Inventario")
        with st.form("nuevo_producto"):
            col1, col2 = st.columns(2)
            nombre = col1.text_input("Nombre del Producto")
            categoria = col2.text_input("Categoría")
            stock = col1.number_input("Stock Inicial", min_value=0, step=1)
            stock_minimo = col2.number_input("Stock Mínimo (Alerta)", min_value=0, step=1)
            precio = col1.number_input("Precio de Venta ($)", min_value=0.0)
            costo = col2.number_input("Costo Unitario ($)", min_value=0.0)
            
            if st.form_submit_button("Guardar Producto"):
                c = conn.cursor()
                c.execute('''INSERT INTO productos 
                             (empresa_id, nombre, categoria, stock, stock_minimo, precio_venta, costo) 
                             VALUES (?, ?, ?, ?, ?, ?, ?)''', 
                          (empresa_id, nombre, categoria, stock, stock_minimo, precio, costo))
                conn.commit()
                st.success("Producto agregado exitosamente.")
        
        st.subheader("Catálogo Actual")
        df_inv = pd.read_sql_query(f"SELECT nombre, categoria, stock, stock_minimo, precio_venta FROM productos WHERE empresa_id={empresa_id}", conn)
        st.dataframe(df_inv, use_container_width=True)

    # --- MÓDULO DE VENTAS Y FACTURACIÓN ---
    elif menu == "💰 Nueva Venta":
        st.header("Registro de Ventas")
        c = conn.cursor()
        c.execute("SELECT id, nombre, precio_venta, stock FROM productos WHERE empresa_id=? AND stock > 0", (empresa_id,))
        productos = c.fetchall()
        
        if not productos:
            st.warning("No hay productos con stock disponible. Ve a inventario.")
        else:
            prod_dict = {f"{p[1]} - ${p[2]} (Stock: {p[3]})": p for p in productos}
            seleccion = st.selectbox("Seleccionar Producto", list(prod_dict.keys()))
            prod_info = prod_dict[seleccion]
            
            cantidad = st.number_input("Cantidad", min_value=1, max_value=prod_info[3], step=1)
            subtotal = cantidad * prod_info[2]
            st.write(f"*Total a Pagar:* ${subtotal:,.2f}")
            
            if st.button("Registrar Venta y Generar Factura"):
                fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                # Insertar venta
                c.execute("INSERT INTO ventas (empresa_id, producto_id, nombre_producto, cantidad, total, fecha) VALUES (?, ?, ?, ?, ?, ?)",
                          (empresa_id, prod_info[0], prod_info[1], cantidad, subtotal, fecha_actual))
                # Descontar stock
                c.execute("UPDATE productos SET stock = stock - ? WHERE id = ?", (cantidad, prod_info[0]))
                conn.commit()
                
                # FACTURA BÁSICA
                st.success("✅ Venta registrada con éxito")
                st.markdown("---")
                st.markdown(f"### FACTURA DE VENTA")
                st.markdown(f"*Empresa:* {st.session_state['empresa_email']}<br>*Fecha:* {fecha_actual}", unsafe_allow_html=True)
                st.table(pd.DataFrame([{"Producto": prod_info[1], "Cantidad": cantidad, "Precio Unitario": f"${prod_info[2]:,.2f}", "Subtotal": f"${subtotal:,.2f}"}]))
                st.markdown(f"### TOTAL: ${subtotal:,.2f}")
                st.markdown("milcolores haz brillar tu look") # Mensaje solicitado
                st.markdown("---")

    # --- CORAZÓN DEL DASHBOARD (DIAGNÓSTICO) ---
    elif menu == "📊 Dashboard":
        st.header("Diagnóstico Gerencial de la Empresa")
        
        # Cargar datos
        df_ventas = pd.read_sql_query(f"SELECT * FROM ventas WHERE empresa_id={empresa_id}", conn)
        df_prod = pd.read_sql_query(f"SELECT * FROM productos WHERE empresa_id={empresa_id}", conn)
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.success("🟢 Lo que se está haciendo bien (Fortalezas)")
            if not df_ventas.empty:
                top_productos = df_ventas.groupby('nombre_producto')['cantidad'].sum().nlargest(3).reset_index()
                st.write("*Top 3 Productos Más Vendidos:*")
                st.dataframe(top_productos)
                ingresos_totales = df_ventas['total'].sum()
                st.metric("Ingresos Totales", f"${ingresos_totales:,.2f}")
            else:
                st.info("Aún no hay datos de ventas registrados.")

        with col2:
            st.error("🔴 Lo que no va tan bien (Alertas)")
            if not df_prod.empty:
                stock_critico = df_prod[df_prod['stock'] <= df_prod['stock_minimo']]
                if not stock_critico.empty:
                    st.warning("Productos en Stock Crítico o Agotados:")
                    st.dataframe(stock_critico[['nombre', 'stock', 'stock_minimo']])
                else:
                    st.write("Todos los inventarios están en niveles saludables.")
            else:
                st.info("No hay productos registrados en el inventario.")

        st.markdown("---")
        st.info("💡 ¿En qué enfocarse?")
        if not df_ventas.empty and not df_prod.empty:
            if not stock_critico.empty:
                st.write("- *Urgente:* Reabastecer los productos en alerta roja para no perder oportunidades de venta.")
            # Sugerencia de rentabilidad básica
            df_prod['margen'] = ((df_prod['precio_venta'] - df_prod['costo']) / df_prod['precio_venta']) * 100
            baja_rentabilidad = df_prod[df_prod['margen'] < 20]
            if not baja_rentabilidad.empty:
                st.write("- *Rentabilidad:* Los siguientes productos tienen un margen menor al 20%. Considera ajustar sus precios de venta:")
                st.write(', '.join(baja_rentabilidad['nombre'].tolist()))
            else:
                st.write("- Mantén la estrategia actual, tus márgenes y operaciones están estables.")
        else:
            st.write("- Empieza a registrar tus productos y ventas para recibir sugerencias automáticas.")

# Lógica de enrutamiento
if st.session_state['empresa_id'] is None:
    login_register_ui()
else:
    app_ui()
