import streamlit as st
import sqlite3
import bcrypt
import pandas as pd
from datetime import datetime, timedelta

# ==========================================
# 1. CONFIGURACIÓN Y BASE DE DATOS
# ==========================================
st.set_page_config(page_title="SmartPyme Dashboard", layout="wide", page_icon="🏢")

# Al quitar @st.cache_resource evitamos el error "no such table" en Streamlit Cloud
def init_db():
    conn = sqlite3.connect('smartpyme.db', check_same_thread=False)
    c = conn.cursor()
    
    # Tabla de Empresas
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
    st.markdown("El centro de control operativo y analítico para tu empresa.")
    
    tab1, tab2 = st.tabs(["Iniciar Sesión", "Registrar Empresa"])
    
    with tab1:
        email_login = st.text_input("Correo Electrónico", key="login_email")
        pass_login = st.text_input("Contraseña", type="password", key="login_pass")
        if st.button("Ingresar", type="primary"):
            c = conn.cursor()
            c.execute("SELECT id, password, nombre_empresa FROM empresas WHERE email=?", (email_login,))
            user = c.fetchone()
            if user and check_password(pass_login, user[1]):
                st.session_state['empresa_id'] = user[0]
                st.session_state['empresa_nombre'] = user[2]
                st.rerun()
            else:
                st.error("Credenciales incorrectas. Verifica tu correo y contraseña.")

    with tab2:
        nombre_reg = st.text_input("Nombre de la Empresa / Marca")
        email_reg = st.text_input("Correo Electrónico (Para recuperación)")
        pass_reg = st.text_input("Contraseña segura", type="password")
        if st.button("Crear Cuenta"):
            if nombre_reg and email_reg and pass_reg:
                try:
                    c = conn.cursor()
                    c.execute("INSERT INTO empresas (nombre_empresa, email, password) VALUES (?, ?, ?)", 
                              (nombre_reg, email_reg, hash_password(pass_reg)))
                    conn.commit()
                    st.success("✅ Empresa registrada con éxito. Ahora puedes iniciar sesión.")
                except sqlite3.IntegrityError:
                    st.error("⚠️ Este correo ya está registrado en el sistema.")
            else:
                st.warning("Por favor, completa todos los campos requeridos.")

# ==========================================
# 3. MÓDULOS DE LA APLICACIÓN
# ==========================================
def app_ui():
    st.sidebar.title(f"🏢 {st.session_state['empresa_nombre']}")
    menu = st.sidebar.radio("Navegación", ["📊 Analítica Avanzada", "📦 Inventario y Valor", "💰 Punto de Venta"])
    
    st.sidebar.markdown("---")
    if st.sidebar.button("Cerrar Sesión"):
        st.session_state['empresa_id'] = None
        st.rerun()

    empresa_id = st.session_state['empresa_id']

    # ------------------------------------------
    # MÓDULO: INVENTARIO Y VALORACIÓN
    # ------------------------------------------
    if menu == "📦 Inventario y Valor":
        st.header("Gestión de Inventario")
        
        with st.expander("➕ Agregar Nuevo Producto al Catálogo"):
            with st.form("nuevo_producto"):
                col1, col2 = st.columns(2)
                nombre = col1.text_input("Nombre del Producto")
                categoria = col2.text_input("Categoría (Ej: Ropa, Accesorios, Servicios)")
                stock = col1.number_input("Stock Inicial (Unidades)", min_value=0, step=1)
                stock_minimo = col2.number_input("Stock Mínimo (Alerta de reabastecimiento)", min_value=0, step=1)
                precio = col1.number_input("Precio de Venta al Público ($)", min_value=0.0)
                costo = col2.number_input("Costo Unitario de Producción/Compra ($)", min_value=0.0)
                
                if st.form_submit_button("Guardar Producto"):
                    c = conn.cursor()
                    c.execute('''INSERT INTO productos 
                                 (empresa_id, nombre, categoria, stock, stock_minimo, precio_venta, costo) 
                                 VALUES (?, ?, ?, ?, ?, ?, ?)''', 
                              (empresa_id, nombre, categoria, stock, stock_minimo, precio, costo))
                    conn.commit()
                    st.success(f"Producto '{nombre}' agregado correctamente.")
                    st.rerun()
        
        st.subheader("Catálogo de Productos y Análisis de Márgenes")
        df_inv = pd.read_sql_query(f"SELECT nombre, categoria, stock, stock_minimo, costo, precio_venta FROM productos WHERE empresa_id={empresa_id}", conn)
        
        if not df_inv.empty:
            df_inv['Margen Neto (%)'] = ((df_inv['precio_venta'] - df_inv['costo']) / df_inv['precio_venta']) * 100
            df_inv['Valor Bodega (Costo)'] = df_inv['stock'] * df_inv['costo']
            df_inv['Valor Proyectado (Venta)'] = df_inv['stock'] * df_inv['precio_venta']
            
            st.dataframe(df_inv.style.format({
                'costo': '${:,.2f}', 
                'precio_venta': '${:,.2f}', 
                'Margen Neto (%)': '{:.2f}%',
                'Valor Bodega (Costo)': '${:,.2f}', 
                'Valor Proyectado (Venta)': '${:,.2f}'
            }), use_container_width=True)
            
            st.markdown("### 💰 Capital en Bodega (Valoración Total)")
            col1, col2 = st.columns(2)
            col1.metric("Capital Invertido (Costo Total)", f"${df_inv['Valor Bodega (Costo)'].sum():,.2f}")
            col2.metric("Ingreso Potencial (Si se vende todo)", f"${df_inv['Valor Proyectado (Venta)'].sum():,.2f}")
        else:
            st.info("Aún no tienes productos registrados. Usa el formulario de arriba para empezar.")

    # ------------------------------------------
    # MÓDULO: PUNTO DE VENTA Y FACTURACIÓN
    # ------------------------------------------
    elif menu == "💰 Punto de Venta":
        st.header("Terminal de Ventas")
        c = conn.cursor()
        c.execute("SELECT id, nombre, precio_venta, stock, costo, categoria FROM productos WHERE empresa_id=? AND stock > 0", (empresa_id,))
        productos = c.fetchall()
        
        if not productos:
            st.warning("No hay productos con stock disponible para vender. Revisa tu inventario.")
        else:
            col1, col2 = st.columns(2)
            with col1:
                st.subheader("1. Detalle del Producto")
                prod_dict = {f"{p[1]} - ${p[2]:,.2f} (Disponibles: {p[3]})": p for p in productos}
                seleccion = st.selectbox("Buscar y Seleccionar Producto", list(prod_dict.keys()))
                prod_info = prod_dict[seleccion]
                
                cantidad = st.number_input("Cantidad a vender", min_value=1, max_value=prod_info[3], step=1)
                medio_venta = st.selectbox("Canal de Venta", ["Físico (Local)", "WhatsApp / Redes", "Marketplace", "E-commerce", "Live Streaming"])
            
            with col2:
                st.subheader("2. Datos del Cliente (Opcional)")
                cliente_nombre = st.text_input("Nombre Completo")
                cliente_celular = st.text_input("Número de Celular")
                cliente_edad = st.text_input("Edad o Rango de Edad")

            subtotal = cantidad * prod_info[2]
            costo_total = cantidad * prod_info[4]
            categoria_prod = prod_info[5]
            
            st.markdown("---")
            st.markdown(f"### *Total a Cobrar: ${subtotal:,.2f}*")
            
            if st.button("Confirmar Venta y Generar Factura", type="primary"):
                fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                # Registrar la transacción
                c.execute('''INSERT INTO ventas 
                            (empresa_id, producto_id, nombre_producto, categoria, cantidad, total, costo_total, fecha, cliente_nombre, cliente_celular, cliente_edad, medio_venta) 
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                          (empresa_id, prod_info[0], prod_info[1], categoria_prod, cantidad, subtotal, costo_total, fecha_actual, cliente_nombre, cliente_celular, cliente_edad, medio_venta))
                
                # Actualizar el inventario
                c.execute("UPDATE productos SET stock = stock - ? WHERE id = ?", (cantidad, prod_info[0]))
                conn.commit()
                
                # Renderizar Factura
                st.success("✅ Transacción procesada correctamente.")
                st.markdown("---")
                st.markdown("### 🧾 RECIBO DE COMPRA")
                st.markdown(f"*Establecimiento:* {st.session_state['empresa_nombre']}<br>*Fecha de Emisión:* {fecha_actual}<br>*Atención a:* {cliente_nombre if cliente_nombre else 'Consumidor Final'} {('- Tel: ' + cliente_celular) if cliente_celular else ''}", unsafe_allow_html=True)
                
                factura_df = pd.DataFrame([{
                    "Descripción": prod_info[1], 
                    "Cant.": cantidad, 
                    "Precio Unit.": f"${prod_info[2]:,.2f}", 
                    "Subtotal": f"${subtotal:,.2f}"
                }])
                st.table(factura_df)
                
                st.markdown(f"#### TOTAL PAGADO: ${subtotal:,.2f}")
                st.markdown("*milcolores haz brillar tu look*")
                st.markdown("---")

    # ------------------------------------------
    # MÓDULO: ANALÍTICA AVANZADA Y DIAGNÓSTICO
    # ------------------------------------------
    elif menu == "📊 Analítica Avanzada":
        st.header("Dashboard Gerencial")
        
        df_ventas = pd.read_sql_query(f"SELECT * FROM ventas WHERE empresa_id={empresa_id}", conn)
        df_prod = pd.read_sql_query(f"SELECT * FROM productos WHERE empresa_id={empresa_id}", conn)
        
        if df_ventas.empty:
            st.info("Aún no hay datos suficientes. Registra operaciones en el Punto de Venta para visualizar el análisis.")
        else:
            df_ventas['fecha'] = pd.to_datetime(df_ventas['fecha'])
            
            # Control de Filtros de Tiempo
            st.markdown("*Selecciona el periodo de análisis:*")
            filtro_tiempo = st.radio("Filtro Temporal", ["Todo el histórico", "Hoy", "Esta Semana", "Este Mes", "Este Año"], horizontal=True, label_visibility="collapsed")
            
            hoy = datetime.now()
            if filtro_tiempo == "Hoy":
                df_filtro = df_ventas[df_ventas['fecha'].dt.date == hoy.date()]
            elif filtro_tiempo == "Esta Semana":
                df_filtro = df_ventas[df_ventas['fecha'] >= (hoy - timedelta(days=7))]
            elif filtro_tiempo == "Este Mes":
                df_filtro = df_ventas[df_ventas['fecha'].dt.month == hoy.month]
            elif filtro_tiempo == "Este Año":
                df_filtro = df_ventas[df_ventas['fecha'].dt.year == hoy.year]
            else:
                df_filtro = df_ventas
            
            if df_filtro.empty:
                st.warning(f"No se registraron ventas en el periodo seleccionado: {filtro_tiempo}.")
            else:
                # Indicadores Macro
                ingresos_totales = df_filtro['total'].sum()
                costos_totales = df_filtro['costo_total'].sum()
                margen_promedio = ((ingresos_totales - costos_totales) / ingresos_totales) * 100 if ingresos_totales > 0 else 0
                
                col1, col2 = st.columns(2)
                col1.metric(f"Ingresos Brutos ({filtro_tiempo})", f"${ingresos_totales:,.2f}")
                col2.metric("Margen de Ganancia Promedio", f"{margen_promedio:.2f}%")
                st.markdown("---")
                
                # Diagnóstico de Negocio
                st.subheader("💡 Diagnóstico Estratégico Automático")
                col_bien, col_mal = st.columns(2)
                
                with col_bien:
                    st.success("🟢 Fortalezas Operativas")
                    top_prod = df_filtro.groupby('nombre_producto')['cantidad'].sum().nlargest(2).reset_index()
                    st.write(f"- *Tus productos más populares:* {', '.join(top_prod['nombre_producto'].tolist())}")
                    canal_top = df_filtro.groupby('medio_venta')['total'].sum().idxmax()
                    st.write(f"- *Canal más rentable:* {canal_top}")
                
                with col_mal:
                    st.error("🔴 Alertas y Áreas de Mejora")
                    stock_critico = df_prod[df_prod['stock'] <= df_prod['stock_minimo']]
                    if not stock_critico.empty:
                        st.write(f"- *⚠️ Urgente reabastecer:* {', '.join(stock_critico['nombre'].tolist())}")
                    else:
                        st.write("- *Inventario:* Niveles operativos saludables.")
                        
                    prod_margen = df_filtro.groupby('nombre_producto').agg(Ingresos=('total', 'sum'), Costos=('costo_total', 'sum'))
                    prod_margen['Margen'] = ((prod_margen['Ingresos'] - prod_margen['Costos']) / prod_margen['Ingresos']) * 100
                    margen_bajo = prod_margen[prod_margen['Margen'] < 20]
                    
                    if not margen_bajo.empty:
                        st.write(f"- *📉 Baja rentabilidad (<20%):* Revisa costos de: {', '.join(margen_bajo.index.tolist())}")
                
                st.markdown("---")
                
                # Tablas Detalladas Interactivas
                st.subheader("Rendimiento a Detalle (Tablas Dinámicas)")
                st.write("(Haz clic en los encabezados de las columnas para ordenar los datos a tu preferencia)")
                
                st.markdown("*Desempeño por Producto*")
                prod_tabla = df_filtro.groupby('nombre_producto').agg(
                    Unidades_Vendidas=('cantidad', 'sum'),
                    Ingresos=('total', 'sum'),
                    Costos_Directos=('costo_total', 'sum')
                ).reset_index()
                prod_tabla['Rentabilidad Neta (%)'] = ((prod_tabla['Ingresos'] - prod_tabla['Costos_Directos']) / prod_tabla['Ingresos']) * 100
                st.dataframe(prod_tabla.style.format({
                    'Ingresos': '${:,.2f}', 
                    'Costos_Directos': '${:,.2f}', 
                    'Rentabilidad Neta (%)': '{:.2f}%'
                }), use_container_width=True, hide_index=True)
                
                col_cat, col_can = st.columns(2)
                with col_cat:
                    st.markdown("*Flujo por Categorías*")
                    cat_tabla = df_filtro.groupby('categoria').agg(Unidades=('cantidad', 'sum'), Ingresos=('total', 'sum')).reset_index().sort_values('Ingresos', ascending=False)
                    st.dataframe(cat_tabla.style.format({'Ingresos': '${:,.2f}'}), use_container_width=True, hide_index=True)
                
                with col_can:
                    st.markdown("*Rendimiento por Canal de Venta*")
                    can_tabla = df_filtro.groupby('medio_venta').agg(Ingresos=('total', 'sum')).reset_index().sort_values('Ingresos', ascending=False)
                    st.dataframe(can_tabla.style.format({'Ingresos': '${:,.2f}'}), use_container_width=True, hide_index=True)

# Lógica de Inicialización Principal
if st.session_state['empresa_id'] is None:
    login_register_ui()
else:
    app_ui()
