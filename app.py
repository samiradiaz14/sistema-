import streamlit as st
import pandas as pd
import sqlite3
import datetime
import plotly.express as px
import plotly.graph_objects as go

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="Dashboard Analítico - Fundación",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- ESTILO TEMA OSCURO PREMIUM (CSS NATIVO CORREGIDO) ---
st.markdown("""
    <style>
    /* Estilo General */
    .stApp {
        background-color: #0E1117;
        color: #E0E0E0;
    }
    
    /* Textos en Sidebar */
    section[data-testid="stSidebar"] {
        background-color: #161B22;
        border-right: 1px solid #30363D;
    }
    section[data-testid="stSidebar"] p, 
    section[data-testid="stSidebar"] span, 
    section[data-testid="stSidebar"] div,
    section[data-testid="stSidebar"] label {
        color: #C9D1D9 !important;
    }
    
    /* Carga de Archivos (File Uploader) */
    div[data-testid="stFileUploader"] {
        background-color: #1F242D;
        border: 1px dashed #484F58;
        border-radius: 8px;
        padding: 10px;
    }
    div[data-testid="stFileUploader"] section {
        background-color: #1F242D !important;
    }
    div[data-testid="stFileUploader"] span, div[data-testid="stFileUploader"] button {
        color: #E0E0E0 !important;
    }

    /* Tarjetas de Métricas */
    [data-testid="stMetric"] {
        background-color: #161B22;
        border: 1px solid #30363D;
        border-radius: 10px;
        padding: 14px 20px;
        box-shadow: 0 4px 10px rgba(0, 0, 0, 0.4);
    }
    [data-testid="stMetricLabel"] {
        color: #8B949E !important;
        font-size: 0.9rem !important;
        font-weight: 600;
    }
    [data-testid="stMetricValue"] {
        color: #58A6FF !important;
        font-weight: 700;
    }

    /* Pestañas (Tabs) */
    .stTabs [data-baseweb="tab-list"] {
        gap: 10px;
        background-color: #161B22;
        padding: 8px;
        border-radius: 10px;
        border: 1px solid #30363D;
    }
    .stTabs [data-baseweb="tab"] {
        color: #8B949E !important;
        border-radius: 6px;
        padding: 8px 20px;
        font-weight: 600;
    }
    .stTabs [aria-selected="true"] {
        background-color: #238636 !important;
        color: #FFFFFF !important;
    }

    /* Tablas de Datos (DataFrames) */
    [data-testid="stDataFrame"] {
        background-color: #161B22;
        border: 1px solid #30363D;
        border-radius: 8px;
    }
    </style>
""", unsafe_allow_html=True)

DB_NAME = "fundacion.db"

# --- HISTORIAL EN STATE DE STREAMLIT ---
if "historial_consultas" not in st.session_state:
    st.session_state.historial_consultas = []

# --- HELPER DE CONEXIÓN A BASE DE DATOS ---
def get_db_connection():
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

# --- REGLAS Y DICCIONARIO DE EQUIVALENCIAS ---
DICCIONARIO_LOCACIONES = {
    "prof park": "Parque",
    "park": "Parque",
    "parque": "Parque",
    "general": "Rancho",
    "lunch": "Rancho",
    "tier 3": "Rancho",
    "special events": "Rancho"
}

def categorizar_locacion(nombre_pestana):
    nombre_clean = str(nombre_pestana).lower().strip()
    for clave, locacion in DICCIONARIO_LOCACIONES.items():
        if clave in nombre_clean:
            return locacion
    return "Rancho"

def limpiar_monto(val):
    if pd.isna(val):
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    
    raw_monto = str(val).replace("$", "").replace(",", "").strip()
    parts = raw_monto.split(".")
    if len(parts) == 2 and len(parts[1]) == 3:
        raw_monto = raw_monto.replace(".", "")
    try:
        return float(raw_monto)
    except ValueError:
        return 0.0

def limpiar_texto(texto):
    if pd.isna(texto) or str(texto).lower().strip() in ["nan", "none", "null", ""]:
        return ""
    return str(texto).strip()

# --- MODELO RELACIONAL ---
def inicializar_db():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS personas (
                id_persona INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE,
                nombre TEXT,
                apellido TEXT,
                direccion TEXT
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS visitas (
                id_visita INTEGER PRIMARY KEY AUTOINCREMENT,
                id_persona INTEGER,
                fecha_visita DATE,
                cuarto TEXT,
                locacion TEXT,
                origen TEXT,
                FOREIGN KEY (id_persona) REFERENCES personas(id_persona) ON DELETE CASCADE
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS donaciones (
                id_donacion INTEGER PRIMARY KEY AUTOINCREMENT,
                id_persona INTEGER,
                monto REAL,
                fecha_donacion DATE,
                origen TEXT,
                FOREIGN KEY (id_persona) REFERENCES personas(id_persona) ON DELETE CASCADE
            )
        ''')
        conn.commit()

def obtener_o_crear_persona(cursor, email, nombre, apellido, direccion=""):
    email_clean = email.lower().strip() if email else ""
    nombre_clean = nombre.strip()
    apellido_clean = apellido.strip()
    
    if email_clean:
        cursor.execute("SELECT id_persona FROM personas WHERE email = ?", (email_clean,))
        row = cursor.fetchone()
        if row:
            return row[0]
            
    if nombre_clean or apellido_clean:
        cursor.execute(
            "SELECT id_persona FROM personas WHERE LOWER(nombre) = LOWER(?) AND LOWER(apellido) = LOWER(?)",
            (nombre_clean, apellido_clean)
        )
        row = cursor.fetchone()
        if row:
            return row[0]
            
    cursor.execute(
        "INSERT INTO personas (email, nombre, apellido, direccion) VALUES (?, ?, ?, ?)",
        (email_clean if email_clean else None, nombre_clean, apellido_clean, direccion)
    )
    return cursor.lastrowid

# --- PIPELINE ETL ---
def procesar_excel(file):
    xls = pd.ExcelFile(file)
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM visitas")
        cursor.execute("DELETE FROM donaciones")
        cursor.execute("DELETE FROM personas")
        
        POSIBLES_COLS_VISITA = ["date of visit", "visit date", "fecha de visita", "fecha visita", "date", "fecha"]
        POSIBLES_COLS_DONACION = ["donation date", "fecha donacion", "fecha de donacion", "date of donation"]
        
        for sheet_name in xls.sheet_names:
            df = pd.read_excel(xls, sheet_name=sheet_name)
            df.columns = df.columns.astype(str).str.strip().str.lower()
            
            col_fecha_visita = next((col for col in POSIBLES_COLS_VISITA if col in df.columns), None)
            col_fecha_donacion = next((col for col in POSIBLES_COLS_DONACION if col in df.columns), None)
            locacion_cat = categorizar_locacion(sheet_name)
            
            if col_fecha_visita:
                for _, row in df.iterrows():
                    email = limpiar_texto(row.get("email"))
                    nombre = limpiar_texto(row.get("name") or row.get("nombre"))
                    apellido = limpiar_texto(row.get("last name") or row.get("apellido"))
                    direccion = limpiar_texto(row.get("home address") or row.get("address"))
                    fecha = pd.to_datetime(row.get(col_fecha_visita), errors='coerce')
                    cuarto = limpiar_texto(row.get("room number") or row.get("cuarto") or row.get("room"))
                    
                    if pd.notnull(fecha) and (email or nombre or apellido):
                        id_p = obtener_o_crear_persona(cursor, email, nombre, apellido, direccion)
                        cursor.execute(
                            "INSERT INTO visitas (id_persona, fecha_visita, cuarto, locacion, origen) VALUES (?, ?, ?, ?, ?)",
                            (id_p, fecha.strftime('%Y-%m-%d'), cuarto, locacion_cat, sheet_name)
                        )
                        
            if col_fecha_donacion:
                col_monto = next((col for col in ["monto", "amount", "donation", "donation amount", "donacion"] if col in df.columns), None)
                for _, row in df.iterrows():
                    email = limpiar_texto(row.get("email"))
                    nombre = limpiar_texto(row.get("name") or row.get("nombre"))
                    apellido = limpiar_texto(row.get("last name") or row.get("apellido"))
                    direccion = limpiar_texto(row.get("home address") or row.get("address"))
                    fecha = pd.to_datetime(row.get(col_fecha_donacion), errors='coerce')
                    monto_val = limpiar_monto(row.get(col_monto)) if col_monto else 0.0
                    
                    if pd.notnull(fecha) and (email or nombre or apellido):
                        id_p = obtener_o_crear_persona(cursor, email, nombre, apellido, direccion)
                        cursor.execute(
                            "INSERT INTO donaciones (id_persona, monto, fecha_donacion, origen) VALUES (?, ?, ?, ?)",
                            (id_p, monto_val, fecha.strftime('%Y-%m-%d'), sheet_name)
                        )
        conn.commit()

# --- ANALÍTICA ---
def obtener_estacion(mes):
    if mes in [12, 1, 2]: return "Invierno"
    elif mes in [3, 4, 5]: return "Primavera"
    elif mes in [6, 7, 8]: return "Verano"
    else: return "Otoño"

def calcular_analitica(donaciones_df, visitas_df):
    if not donaciones_df.empty:
        fechas = pd.to_datetime(donaciones_df["fecha_donacion"])
        estaciones = fechas.dt.month.apply(obtener_estacion)
        epoca = estaciones.mode()[0] if not estaciones.empty else "Sin registros"
    else:
        epoca = "Sin registros"
        
    if visitas_df.empty or donaciones_df.empty:
        tiempo_prom = "N/A"
    else:
        v_df = visitas_df.copy()
        d_df = donaciones_df.copy()
        v_df["fecha_visita"] = pd.to_datetime(v_df["fecha_visita"])
        d_df["fecha_donacion"] = pd.to_datetime(d_df["fecha_donacion"])
        
        dias_list = []
        for _, don in d_df.iterrows():
            f_don = don["fecha_donacion"]
            prev = v_df[v_df["fecha_visita"] < f_don]
            if not prev.empty:
                dias_list.append((f_don - prev["fecha_visita"].max()).days)
                
        tiempo_prom = f"{int(sum(dias_list)/len(dias_list))} días" if dias_list else "Sin visitas previas"
        
    return epoca, tiempo_prom

# --- INICIALIZACIÓN ---
inicializar_db()

# --- BARRA LATERAL ---
with st.sidebar:
    st.title("Gestión de Datos")
    st.caption("Carga y administración del sistema")
    
    archivo = st.file_uploader("Cargar Excel (.xlsx)", type=["xlsx"])
    if archivo:
        with st.spinner("Ejecutando proceso ETL..."):
            procesar_excel(archivo)
        st.success("Base de Datos Actualizada")

    st.divider()
    st.subheader("Consultas Recientes")
    if st.session_state.historial_consultas:
        for persona_hist in reversed(st.session_state.historial_consultas[-5:]):
            st.caption(f"• {persona_hist}")
    else:
        st.caption("Sin registros en esta sesión.")
        
    st.divider()
    st.subheader("Métricas Globales")
    with get_db_connection() as conn:
        total_p = conn.execute("SELECT COUNT(*) FROM personas").fetchone()[0]
        total_v = conn.execute("SELECT COUNT(*) FROM visitas").fetchone()[0]
        total_d = conn.execute("SELECT COUNT(*) FROM donaciones").fetchone()[0]

    c_s1, c_s2 = st.columns(2)
    c_s1.metric("Personas", total_p)
    c_s2.metric("Visitas", total_v)
    st.metric("Donaciones Registradas", total_d)

# --- INTERFAZ PRINCIPAL ---
st.title("Plataforma de Analítica - Fundación")

tab_persona, tab_graficas, tab_rankings = st.tabs([
    "Consulta por Persona", 
    "Tableros Visuales y Gráficas", 
    "Rankings y Reportes"
])

conn = get_db_connection()

with tab_persona:
    personas_df = pd.read_sql_query("SELECT id_persona, email, nombre, apellido, direccion FROM personas", conn)
    
    if not personas_df.empty:
        personas_df["display"] = personas_df["email"].fillna("Sin Email") + " | " + personas_df["nombre"].fillna("") + " " + personas_df["apellido"].fillna("")
        dict_personas = dict(zip(personas_df["display"], personas_df["id_persona"]))
        opciones_busqueda = ["-- Seleccionar Persona --"] + list(dict_personas.keys())
    else:
        dict_personas = {}
        opciones_busqueda = ["-- Sin registros --"]

    opcion = st.selectbox("Buscar Persona:", opciones_busqueda)
    
    if opcion and opcion in dict_personas:
        if opcion not in st.session_state.historial_consultas:
            st.session_state.historial_consultas.append(opcion)

        selected_id = dict_personas[opcion]
        persona_info = personas_df[personas_df["id_persona"] == selected_id].iloc[0]
        
        visitas_df = pd.read_sql_query("SELECT * FROM visitas WHERE id_persona = ? ORDER BY fecha_visita DESC", conn, params=[selected_id])
        donaciones_df = pd.read_sql_query("SELECT * FROM donaciones WHERE id_persona = ? ORDER BY fecha_donacion DESC", conn, params=[selected_id])
        
        sub_tab1, sub_tab2, sub_tab3, sub_tab4 = st.tabs([
            "Resumen Ejecutivo", 
            "Historial de Visitas", 
            "Historial de Donaciones", 
            "Analítica del Perfil"
        ])

        total_visitas = len(visitas_df)
        total_donado = donaciones_df["monto"].sum() if not donaciones_df.empty else 0.0
        prom_donado = donaciones_df["monto"].mean() if not donaciones_df.empty and total_donado > 0 else 0.0
        visitas_parque = len(visitas_df[visitas_df["locacion"] == "Parque"]) if not visitas_df.empty else 0
        visitas_rancho = len(visitas_df[visitas_df["locacion"] == "Rancho"]) if not visitas_df.empty else 0
        epoca, tiempo_prom = calcular_analitica(donaciones_df, visitas_df)

        with sub_tab1:
            st.markdown(f"### Persona: **{persona_info['nombre']} {persona_info['apellido']}**")
            st.caption(f"Correo: **{persona_info['email']}** | Dirección: **{persona_info['direccion'] or 'No registrada'}**")
            st.divider()
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Total Donado", f"${total_donado:,.2f}")
            c2.metric("Promedio Aporte", f"${prom_donado:,.2f}")
            c3.metric("Visitas Totales", total_visitas)
            c4.metric("Parque / Rancho", f"{visitas_parque} / {visitas_rancho}")

        with sub_tab2:
            st.markdown("### Visitas Registradas")
            if not visitas_df.empty:
                st.dataframe(visitas_df[["fecha_visita", "locacion", "cuarto", "origen"]], use_container_width=True, hide_index=True)
            else:
                st.info("Sin registros de visitas.")

        with sub_tab3:
            st.markdown("### Donaciones Registradas")
            if not donaciones_df.empty:
                st.dataframe(donaciones_df[["fecha_donacion", "monto", "origen"]].style.format({"monto": "${:,.2f}"}), use_container_width=True, hide_index=True)
                fig_don = px.bar(donaciones_df, x="fecha_donacion", y="monto", title="Historial de Donaciones por Fecha", template="plotly_dark")
                st.plotly_chart(fig_don, use_container_width=True)
            else:
                st.info("Sin registros de donaciones.")

        with sub_tab4:
            st.markdown("### Analítica Individual")
            col_a1, col_a2 = st.columns(2)
            col_a1.metric("Época Más Frecuente", epoca)
            col_a2.metric("Tiempo Promedio Visita ➔ Donación", tiempo_prom)

with tab_graficas:
    st.markdown("### Tableros Visuales y Tendencias Globales")
    
    all_donaciones = pd.read_sql_query("SELECT * FROM donaciones", conn)
    all_visitas = pd.read_sql_query("SELECT * FROM visitas", conn)
    
    if not all_donaciones.empty or not all_visitas.empty:
        col_g1, col_g2 = st.columns(2)
        
        with col_g1:
            if not all_visitas.empty:
                st.markdown("#### Distribución de Visitas por Locación")
                loc_counts = all_visitas["locacion"].value_counts().reset_index()
                loc_counts.columns = ["Locación", "Cantidad"]
                fig_pie = px.pie(loc_counts, names="Locación", values="Cantidad", hole=0.4, template="plotly_dark", color_discrete_sequence=px.colors.qualitative.Pastel)
                st.plotly_chart(fig_pie, use_container_width=True)

        with col_g2:
            if not all_donaciones.empty:
                st.markdown("#### Evolución Mensual del Recaudo ($)")
                all_donaciones["fecha_donacion"] = pd.to_datetime(all_donaciones["fecha_donacion"])
                # CORRECCIÓN APLICADA AQUÍ: 'ME' en lugar de 'M'
                don_mensual = all_donaciones.resample("ME", on="fecha_donacion")["monto"].sum().reset_index()
                fig_line = px.line(don_mensual, x="fecha_donacion", y="monto", markers=True, template="plotly_dark", labels={"fecha_donacion": "Mes", "monto": "Monto Total ($)"})
                fig_line.update_traces(line_color="#238636", line_width=3)
                st.plotly_chart(fig_line, use_container_width=True)

        st.divider()
        col_g3, col_g4 = st.columns(2)
        
        with col_g3:
            if not all_donaciones.empty:
                st.markdown("#### Distribución de Montos de Donación")
                fig_hist = px.histogram(all_donaciones, x="monto", nbins=15, title="Frecuencia según Montos ($)", template="plotly_dark", color_discrete_sequence=["#58A6FF"])
                st.plotly_chart(fig_hist, use_container_width=True)

        with col_g4:
            if not all_visitas.empty:
                st.markdown("#### Visitas por Pestaña de Origen (Excel)")
                origen_counts = all_visitas["origen"].value_counts().reset_index()
                origen_counts.columns = ["Origen", "Visitas"]
                fig_bar = px.bar(origen_counts, x="Visitas", y="Origen", orientation="h", template="plotly_dark", color="Visitas", color_continuous_scale="Viridis")
                st.plotly_chart(fig_bar, use_container_width=True)
    else:
        st.info("Carga un archivo Excel para activar los tableros interactivos.")

with tab_rankings:
    st.markdown("### Clasificación de Registros")
    f_rank = st.radio("Criterio de Ranking:", ["Mayor Donación Total", "Más Visitas al Parque", "Más Visitas al Rancho"], horizontal=True)
    st.divider()

    if f_rank == "Mayor Donación Total":
        query = '''
            SELECT p.email AS 'Correo', (p.nombre || ' ' || p.apellido) AS 'Nombre Completo', 
                   COUNT(d.id_donacion) AS 'Aportes Totales', SUM(d.monto) AS 'Total Donado ($)' 
            FROM donaciones d
            JOIN personas p ON d.id_persona = p.id_persona
            GROUP BY p.id_persona
            ORDER BY SUM(d.monto) DESC
        '''
        df_rank = pd.read_sql_query(query, conn)
        if not df_rank.empty:
            st.dataframe(df_rank.style.format({"Total Donado ($)": "${:,.2f}"}), use_container_width=True, hide_index=True)
        else:
            st.info("Sin datos de donaciones.")

    elif f_rank == "Más Visitas al Parque":
        query = '''
            SELECT p.email AS 'Correo', (p.nombre || ' ' || p.apellido) AS 'Nombre Completo', 
                   COUNT(v.id_visita) AS 'Visitas a Parque' 
            FROM visitas v
            JOIN personas p ON v.id_persona = p.id_persona
            WHERE v.locacion = 'Parque'
            GROUP BY p.id_persona
            ORDER BY COUNT(v.id_visita) DESC
        '''
        df_rank = pd.read_sql_query(query, conn)
        if not df_rank.empty:
            st.dataframe(df_rank, use_container_width=True, hide_index=True)
        else:
            st.info("Sin datos de visitas al Parque.")

    else:
        query = '''
            SELECT p.email AS 'Correo', (p.nombre || ' ' || p.apellido) AS 'Nombre Completo', 
                   COUNT(v.id_visita) AS 'Visitas a Rancho' 
            FROM visitas v
            JOIN personas p ON v.id_persona = p.id_persona
            WHERE v.locacion = 'Rancho'
            GROUP BY p.id_persona
            ORDER BY COUNT(v.id_visita) DESC
        '''
        df_rank = pd.read_sql_query(query, conn)
        if not df_rank.empty:
            st.dataframe(df_rank, use_container_width=True, hide_index=True)
        else:
            st.info("Sin datos de visitas al Rancho.")

conn.close()