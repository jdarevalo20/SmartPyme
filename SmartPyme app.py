import streamlit as st
import sqlite3
import bcrypt
import pandas as pd
from datetime import datetime, timedelta

# ==========================================
# 1. CONFIGURACIÓN Y BASE DE DATOS (CACHÉ ESTABILIZADO)
# ==========================================
st.set_page_config(page_title="SmartPyme Dashboard", layout="wide")

# El decorador cache_resource mantiene viva la base de datos y evita el error "no such table"
@st.cache_resource
def init_db():
    conn = sqlite3.connect('smartpyme.db', check_same_thread=False)
    c = conn.cursor()
    
    # Tabla de Mipymes
    c.execute('''CREATE TABLE IF NOT EXISTS empresas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nombre_empresa TEXT,
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
                    categoria TEXT,
                    cantidad INTEGER,
                    total REAL,
                    costo_total REAL,
                    fecha TEXT,
                    cliente_nombre TEXT,
                    cliente_celular TEXT,
                    cliente_edad TEXT,
                    medio_venta TEXT)''')
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
    st.session_state['empresa_nombre'] = None

def login_register_ui():
    st.title("🔐 Acceso a SmartPyme")
    tab1, tab2 = st.tabs(["Iniciar Sesión", "Registrar Empresa"])
    
    with tab1:
        email_login = st.text_input("Correo Electrónico", key="login_email")
        pass_login = st.text_input("Contraseña", type="password", key="login_pass")
        if st.button("Ingresar"):
            c = conn.cursor()
            c.execute("SELECT id, password, nombre_empresa FROM empresas WHERE email=?", (email_login,))
            user = c.fetchone()
            if user and check_password(pass_login, user[1]):
                st.session_state['empresa_id'] = user[0]
                st.session_state['empresa_nombre'] = user[2]
                st.rerun()
            else:
                st.error("Credenciales incorrectas")

    with tab2:
        nombre_reg = st.text_input("Nombre de la Empresa")
        email_reg = st.text_input("Correo Electrónico")
        pass_reg = st.text_input("Contraseña", type="password")
        if st.button("Registrar Mipyme"):
            if nombre_reg and email_reg and pass_reg:
                try:
                    c = conn.cursor()
                    c.execute("INSERT INTO empresas (nombre_empresa, email, password) VALUES (?, ?, ?)", 
                              (nombre_reg, email_reg, hash_password(pass_reg)))
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
    st.sidebar.title(f"🏢 {st.session_state['empresa_nombre']}")
    menu = st.sidebar.radio("Navegación", ["📊 Analítica Avanzada", "📦 Inventario y Valor", "💰 Punto de Venta"])
    
    if st.sidebar.button("Cerrar Sesión"):
        st.session_state['empresa_id'] = None
        st.rerun()

    empresa_id = st.session_state['empresa_id']

    # --- MÓDULO DE INVENTARIO ---
    if menu == "📦 Inventario y Valor":
        st.header("Gestión de Inventario")
        with st.expander("➕ Agregar Nuevo Producto"):
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
                    st.success("Producto agregado.")
                    st.rerun()
        
        st.subheader("Catálogo de Productos y Márgenes")
        df_inv = pd.read_sql_query(f"SELECT nombre, categoria, stock, stock_minimo, costo, precio_venta FROM productos WHERE empresa_id={empresa_id}", conn)
        
        if not df_inv.empty:
            df_inv['Margen de Ganancia (%)'] = ((df_inv['precio_venta'] - df_inv['costo']) / df_inv['precio_venta']) * 100
            df_inv['Valor Stock (Costo Neto)'] = df_inv['stock'] * df_inv['costo']
            df_inv['Valor Stock (Venta Bruto)'] = df_inv['stock'] * df_inv['precio_venta']
            
            st.dataframe(df_inv.style.format({
                'costo': '${:,.2f}', 'precio_venta': '${:,.2f}', 
                'Margen de Ganancia (%)': '{:.2f}%',
                'Valor Stock (Costo Neto)': '${:,.2f}', 'Valor Stock (Venta Bruto)': '${:,.2f}'
            }), use_container_width=True)
            
            st.markdown("### 💰 Valor Total del Inventario Actual")
            col1, col2 = st.columns(2)
            col1.metric("Valor Neto (Lo que invertiste)", f"${df_inv['Valor Stock (Costo Neto)'].sum():,.2f}")
            col2.metric("Valor Bruto (Si vendes todo)", f"${df_inv['Valor Stock (Venta Bruto)'].sum():,.2f}")
        else:
            st.info("Agrega productos para ver tu inventario.")

    # --- MÓDULO DE VENTAS Y FACTURACIÓN ---
    elif menu == "💰 Punto de Venta":
        st.header("Registro de Ventas")
        c = conn.cursor()
        c.execute("SELECT id, nombre, precio_venta, stock, costo, categoria FROM productos WHERE empresa_id=? AND stock > 0", (empresa_id,))
        productos = c.fetchall()
        
        if not productos:
            st.warning("No hay productos con stock. Ve a inventario.")
        else:
            col1, col2 = st.columns(2)
            with col1:
                st.subheader("Datos de la Venta")
                prod_dict = {f"{p[1]} - ${p[2]} (Stock: {p[3]})": p for p in productos}
                seleccion = st.selectbox("Seleccionar Producto", list(prod_dict.keys()))
                prod_info = prod_dict[seleccion]
                cantidad = st.number_input("Cantidad", min_value=1, max_value=prod_info[3], step=1)
                medio_venta = st.selectbox("Medio de Venta", ["Físico", "Marketplace", "Live", "E-commerce"])
            
            with col2:
                st.subheader("Datos del Cliente (Opcional)")
                cliente_nombre = st.text_input("Nombre del Cliente")
                cliente_celular = st.text_input("Celular")
                cliente_edad = st.text_input("Edad")

            subtotal = cantidad * prod_info[2]
            costo_total = cantidad * prod_info[4]
            categoria_prod = prod_info[5]
            st.markdown(f"### *Total a Cobrar:* ${subtotal:,.2f}")
            
            if st.button("Registrar Venta y Generar Factura"):
                fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                c.execute('''INSERT INTO ventas 
                            (empresa_id, producto_id, nombre_producto, categoria, cantidad, total, costo_total, fecha, cliente_nombre, cliente_celular, cliente_edad, medio_venta) 
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                          (empresa_id, prod_info[0], prod_info[1], categoria_prod, cantidad, subtotal, costo_total, fecha_actual, cliente_nombre, cliente_celular, cliente_edad, medio_venta))
                c.execute("UPDATE productos SET stock = stock - ? WHERE id = ?", (cantidad, prod_info[0]))
                conn.commit()
                
                st.success("✅ Venta registrada")
                st.markdown("---")
                st.markdown(f"### FACTURA DE VENTA")
                st.markdown(f"*Empresa:* {st.session_state['empresa_nombre']}<br>*Fecha:* {fecha_actual}<br>*Cliente:* {cliente_nombre} / {cliente_celular}", unsafe_allow_html=True)
                st.table(pd.DataFrame([{"Producto": prod_info[1], "Cantidad": cantidad, "Precio Unitario": f"${prod_info[2]:,.2f}", "Subtotal": f"${subtotal:,.2f}"}]))
                st.markdown(f"### TOTAL: ${subtotal:,.2f}")
                st.markdown("*milcolores haz brillar tu look*")
                st.markdown("---")

    # --- MÓDULO DE ANALÍTICA AVANZADA ---
    elif menu == "📊 Analítica Avanzada":
        st.header("Análisis de Rendimiento de la Empresa")
        
        df_ventas = pd.read_sql_query(f"SELECT * FROM ventas WHERE empresa_id={empresa_id}", conn)
        df_prod = pd.read_sql_query(f"SELECT * FROM productos WHERE empresa_id={empresa_id}", conn)
        
        if df_ventas.empty:
            st.info("Registra ventas para ver el análisis de datos.")
        else:
            df_ventas['fecha'] = pd.to_datetime(df_ventas['fecha'])
            
            filtro_tiempo = st.radio("Filtrar Análisis por:", ["Todo", "Hoy", "Esta Semana", "Este Mes", "Este Año"], horizontal=True)
            hoy = datetime.now()
            
            if filtro_tiempo == "Hoy":
                df_filtrado = df_ventas[df_ventas['fecha'].dt.date == hoy.date()]
            elif filtro_tiempo == "Esta Semana":
                df_filtrado = df_ventas[df_ventas['fecha'] >= (hoy - timedelta(days=7))]
            elif filtro_tiempo == "Este Mes":
                df_filtrado = df_ventas[df_ventas['fecha'].dt.month == hoy.month]
            elif filtro_tiempo == "Este Año":
                df_filtrado = df_ventas[df_ventas['fecha'].dt.year == hoy.year]
            else:
                df_filtrado = df_ventas
            
            if df_filtrado.empty:
                st.warning("No hay ventas en este periodo.")
            else:
                ingresos_totales = df_filtrado['total'].sum()
                costos_totales = df_filtrado['costo_total'].sum()
                margen_promedio = ((ingresos_totales - costos_totales) / ingresos_totales) * 100 if ingresos_totales > 0 else 0
                
                col1, col2 = st.columns(2)
                col1.metric(f"Ventas Totales ({filtro_tiempo})", f"${ingresos_totales:,.2f}")
                col2.metric("Margen Promedio de Ganancia", f"{margen_promedio:.2f}%")
                
                st.markdown("---")
                
                # --- DIAGNÓSTICO ESTRATÉGICO ---
                st.subheader("💡 Diagnóstico Gerencial")
                col_bien, col_mal = st.columns(2)
                
                with col_bien:
                    st.success("🟢 Lo que se está haciendo bien")
                    top_prod = df_filtrado.groupby('nombre_producto')['cantidad'].sum().nlargest(2).reset_index()
                    st.write(f"Tus productos estrella son: *{', '.join(top_prod['nombre_producto'].tolist())}*")
                    canal_top = df_filtrado.groupby('medio_venta')['total'].sum().idxmax()
                    st.write(f"Tu mejor canal de ventas es: *{canal_top}*")
                
                with col_mal:
                    st.error("🔴 Lo que no va tan bien y requiere enfoque")
                    stock_critico = df_prod[df_prod['stock'] <= df_prod['stock_minimo']]
                    if not stock_critico.empty:
                        st.write("⚠️ *Stock Crítico:* Reabastece urgente estos productos:")
                        st.write(', '.join(stock_critico['nombre'].tolist()))
                    else:
                        st.write("Tu inventario está estable por encima de los niveles mínimos.")
                        
                    prod_agrupados = df_filtrado.groupby('nombre_producto').agg(Ingresos=('total', 'sum'), Costos=('costo_total', 'sum'))
                    prod_agrupados['Margen'] = ((prod_agrupados['Ingresos'] - prod_agrupados['Costos']) / prod_agrupados['Ingresos']) * 100
                    margen_bajo = prod_agrupados[prod_agrupados['Margen'] < 20]
                    if not margen_bajo.empty:
                        st.write("📉 *Enfócate en los precios:* Estos productos dejan menos del 20% de ganancia:")
                        st.write(', '.join(margen_bajo.index.tolist()))
                
                st.markdown("---")
                st.subheader("Rendimiento por Productos (Ordenable)")
                prod_tabla = df_filtrado.groupby('nombre_producto').agg(
                    Unidades_Vendidas=('cantidad', 'sum'),
                    Ingresos_Totales=('total', 'sum'),
                    Costos=('costo_total', 'sum')
                ).reset_index()
                prod_tabla['Margen (%)'] = ((prod_tabla['Ingresos_Totales'] - prod_tabla['Costos']) / prod_tabla['Ingresos_Totales']) * 100
                st.dataframe(prod_tabla.style.format({'Ingresos_Totales': '${:,.2f}', 'Costos': '${:,.2f}', 'Margen (%)': '{:.2f}%'}), use_container_width=True)

# Lógica de enrutamiento
if st.session_state['empresa_id'] is None:
    login_register_ui()
else:
    app_ui()
