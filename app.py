import streamlit as st
import pandas as pd
import sqlite3
import datetime
import plotly.express as px
import plotly.graph_objects as go

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="Dashboard Analítico - Fundación La Puerta",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- PALETA DE COLORES (INSPIRADA EN FUNDACIÓN LA PUERTA) ---
COLOR_BG_PRINCIPAL = "#EAE6DF"   # Crema / Arena del fondo
COLOR_BG_TARJETA   = "#F5F3EE"   # Crema claro para tarjetas y sidebar
COLOR_VERDE_OSCURO = "#455342"   # Verde bosque del logo y texto
COLOR_VERDE_MEDIO  = "#62735E"   # Verde secundario para hovers/gráficas
COLOR_AMBAR        = "#DF9343"   # Naranja bellota (acento)
COLOR_BORDE        = "#D3CCC0"   # Borde suave tono tierra
COLOR_TEXTO_SEC    = "#6B7068"   # Gris verdoso para etiquetas secundarias

# --- ESTILO TEMA ORGÁNICO CÁLIDO (CSS NATIVO) ---
st.markdown(f"""
    <style>
    .stApp {{
        background-color: {COLOR_BG_PRINCIPAL};
        color: {COLOR_VERDE_OSCURO};
    }}
    h1, h2, h3, h4, h5, h6 {{
        color: {COLOR_VERDE_OSCURO} !important;
    }}
    section[data-testid="stSidebar"] {{
        background-color: {COLOR_BG_TARJETA};
        border-right: 1px solid {COLOR_BORDE};
    }}
    section[data-testid="stSidebar"] p, 
    section[data-testid="stSidebar"] span, 
    section[data-testid="stSidebar"] div,
    section[data-testid="stSidebar"] label {{
        color: {COLOR_VERDE_OSCURO} !important;
    }}
    div[data-testid="stFileUploader"] {{
        background-color: {COLOR_BG_PRINCIPAL};
        border: 1.5px dashed {COLOR_VERDE_OSCURO};
        border-radius: 8px;
        padding: 10px;
    }}
    div[data-testid="stFileUploader"] section {{
        background-color: {COLOR_BG_PRINCIPAL} !important;
    }}
    div[data-testid="stFileUploader"] span, 
    div[data-testid="stFileUploader"] button {{
        color: {COLOR_VERDE_OSCURO} !important;
    }}
    [data-testid="stMetric"] {{
        background-color: {COLOR_BG_TARJETA};
        border: 1px solid {COLOR_BORDE};
        border-left: 4px solid {COLOR_VERDE_OSCURO};
        border-radius: 10px;
        padding: 14px 20px;
        box-shadow: 0 3px 8px rgba(69, 83, 66, 0.08);
    }}
    [data-testid="stMetricLabel"] {{
        color: {COLOR_TEXTO_SEC} !important;
        font-size: 0.9rem !important;
        font-weight: 600;
    }}
    [data-testid="stMetricValue"] {{
        color: {COLOR_VERDE_OSCURO} !important;
        font-weight: 700;
    }}
    [data-testid="stMetricDelta"] svg {{
        fill: {COLOR_AMBAR} !important;
    }}
    .stTabs [data-baseweb="tab-list"] {{
        gap: 10px;
        background-color: {COLOR_BG_TARJETA};
        padding: 8px;
        border-radius: 10px;
        border: 1px solid {COLOR_BORDE};
    }}
    .stTabs [data-baseweb="tab"] {{
        color: {COLOR_VERDE_OSCURO} !important;
        border-radius: 6px;
        padding: 8px 20px;
        font-weight: 600;
        background-color: transparent;
    }}
    .stTabs [aria-selected="true"] {{
        background-color: {COLOR_VERDE_OSCURO} !important;
        color: #FFFFFF !important;
    }}
    [data-testid="stDataFrame"] {{
        background-color: {COLOR_BG_TARJETA};
        border: 1px solid {COLOR_BORDE};
        border-radius: 8px;
    }}
    div[data-baseweb="select"] > div {{
        background-color: {COLOR_BG_TARJETA} !important;
        border-color: {COLOR_BORDE} !important;
        color: {COLOR_VERDE_OSCURO} !important;
    }}
    hr {{
        border-color: {COLOR_BORDE} !important;
    }}
    </style>
""", unsafe_allow_html=True)

DB_NAME = "fundacion.db"

if "historial_consultas" not in st.session_state:
    st.session_state.historial_consultas = []

def get_db_connection():
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

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

def limpiar_fecha(val):
    """Parsea fechas y descarta errores de captura fuera del rango operativo (2023-2027)."""
    fecha = pd.to_datetime(val, errors='coerce')
    if pd.notnull(fecha) and (2023 <= fecha.year <= 2027):
        return fecha
    return pd.NaT

def aplicar_estilo_plotly(fig):
    """Fuerza fondo transparente y tipografía verde bosque en tema claro."""
    fig.update_layout(
        template="plotly_white",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=COLOR_VERDE_OSCURO),
        title_font=dict(color=COLOR_VERDE_OSCURO),
        xaxis=dict(gridcolor=COLOR_BORDE, zerolinecolor=COLOR_BORDE),
        yaxis=dict(gridcolor=COLOR_BORDE, zerolinecolor=COLOR_BORDE),
        margin=dict(t=40, b=30, l=20, r=20)
    )
    return fig

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
                    direccion = limpiar_texto(row.get("home address") or row.get("home adress") or row.get("address"))
                    fecha = limpiar_fecha(row.get(col_fecha_visita))
                    cuarto = limpiar_texto(row.get("room number") or row.get("cuarto") or row.get("room"))
                    
                    if pd.notnull(fecha) and (email or nombre or apellido):
                        id_p = obtener_o_crear_persona(cursor, email, nombre, apellido, direccion)
                        cursor.execute(
                            "INSERT INTO visitas (id_persona, fecha_visita, cuarto, locacion, origen) VALUES (?, ?, ?, ?, ?)",
                            (id_p, fecha.strftime('%Y-%m-%d'), cuarto, locacion_cat, sheet_name.strip())
                        )
                        
            if col_fecha_donacion:
                col_monto = next((col for col in ["monto", "amount", "donation", "donation amount", "donacion"] if col in df.columns), None)
                for _, row in df.iterrows():
                    email = limpiar_texto(row.get("email"))
                    nombre = limpiar_texto(row.get("name") or row.get("nombre"))
                    apellido = limpiar_texto(row.get("last name") or row.get("apellido"))
                    direccion = limpiar_texto(row.get("home address") or row.get("home adress") or row.get("address"))
                    fecha = limpiar_fecha(row.get(col_fecha_donacion))
                    monto_val = limpiar_monto(row.get(col_monto)) if col_monto else 0.0
                    
                    if pd.notnull(fecha) and (email or nombre or apellido):
                        id_p = obtener_o_crear_persona(cursor, email, nombre, apellido, direccion)
                        cursor.execute(
                            "INSERT INTO donaciones (id_persona, monto, fecha_donacion, origen) VALUES (?, ?, ?, ?)",
                            (id_p, monto_val, fecha.strftime('%Y-%m-%d'), sheet_name.strip())
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
    st.caption("Fundación La Puerta Voluntarios")
    
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
st.title("Plataforma de Analítica - Fundación La Puerta")

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
                fig_don = px.bar(
                    donaciones_df, x="fecha_donacion", y="monto", 
                    title="Historial de Donaciones por Fecha", text_auto="$.2s",
                    color_discrete_sequence=[COLOR_VERDE_OSCURO]
                )
                st.plotly_chart(aplicar_estilo_plotly(fig_don), use_container_width=True)
            else:
                st.info("Sin registros de donaciones.")

        with sub_tab4:
            st.markdown("### Analítica Individual")
            col_a1, col_a2 = st.columns(2)
            col_a1.metric("Época Más Frecuente", epoca)
            col_a2.metric("Tiempo Promedio Visita ➔ Donación", tiempo_prom)

with tab_graficas:
    st.markdown("### Tableros Visuales y Tendencias Globales")
    
    all_donaciones = pd.read_sql_query("""
        SELECT d.*, COALESCE(NULLIF(TRIM(p.nombre || ' ' || p.apellido), ''), p.email, 'Anónimo') AS donante
        FROM donaciones d
        LEFT JOIN personas p ON d.id_persona = p.id_persona
    """, conn)
    all_visitas = pd.read_sql_query("SELECT * FROM visitas", conn)
    
    if not all_donaciones.empty or not all_visitas.empty:
        # --- FILA SUPERIOR: INDICADORES CLAVE DE RENDIMIENTO (KPIs) ---
        don_efectivas = all_donaciones[all_donaciones["monto"] > 0].copy() if not all_donaciones.empty else pd.DataFrame()
        recaudo_total = don_efectivas["monto"].sum() if not don_efectivas.empty else 0.0
        ticket_prom = don_efectivas["monto"].mean() if not don_efectivas.empty else 0.0
        ticket_mediana = don_efectivas["monto"].median() if not don_efectivas.empty else 0.0
        donacion_max = don_efectivas["monto"].max() if not don_efectivas.empty else 0.0

        visitantes_unicos = set(all_visitas["id_persona"].unique()) if not all_visitas.empty else set()
        donantes_unicos = set(don_efectivas["id_persona"].unique()) if not don_efectivas.empty else set()
        convertidos = len(visitantes_unicos.intersection(donantes_unicos))
        tasa_conv = (convertidos / len(visitantes_unicos) * 100) if visitantes_unicos else 0.0

        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
        kpi1.metric("Recaudo Total", f"${recaudo_total:,.0f}", f"{len(don_efectivas)} aportes efectivos")
        kpi2.metric("Ticket Promedio", f"${ticket_prom:,.0f}", f"Mediana: ${ticket_mediana:,.0f}")
        kpi3.metric("Aporte Máximo", f"${donacion_max:,.0f}", f"{len(donantes_unicos)} donantes únicos")
        kpi4.metric("Conversión Visitante ➔ Donante", f"{tasa_conv:.1f}%", f"{convertidos} de {len(visitantes_unicos)} visitantes")

        st.divider()
        col_g1, col_g2 = st.columns(2)
        
        # --- GRÁFICA 1: DONA DE VISITAS ---
        with col_g1:
            if not all_visitas.empty:
                st.markdown("#### Distribución de Visitas por Locación")
                loc_counts = all_visitas["locacion"].value_counts().reset_index()
                loc_counts.columns = ["Locación", "Cantidad"]
                fig_pie = px.pie(
                    loc_counts, names="Locación", values="Cantidad", hole=0.5,
                    color_discrete_sequence=[COLOR_VERDE_OSCURO, COLOR_AMBAR]
                )
                fig_pie.update_traces(
                    textinfo="percent+value",
                    texttemplate="%{percent:.1%}<br>(%{value} visitas)",
                    hovertemplate="<b>%{label}</b><br>Visitas: %{value}<br>Porcentaje: %{percent:.1%}<extra></extra>"
                )
                fig_pie.add_annotation(
                    text=f"<b>{len(all_visitas)}</b><br>Visitas",
                    x=0.5, y=0.5, font_size=16, showarrow=False, font_color=COLOR_VERDE_OSCURO
                )
                st.plotly_chart(aplicar_estilo_plotly(fig_pie), use_container_width=True)

        # --- GRÁFICA 2: EVOLUCIÓN MENSUAL ---
        with col_g2:
            if not don_efectivas.empty:
                st.markdown("#### Evolución Mensual del Recaudo ($)")
                df_evol = don_efectivas.copy()
                df_evol["fecha_donacion"] = pd.to_datetime(df_evol["fecha_donacion"])
                df_evol = df_evol[df_evol["fecha_donacion"] >= "2024-01-01"]
                
                don_mensual = df_evol.resample("ME", on="fecha_donacion").agg(
                    monto=("monto", "sum"),
                    aportes=("monto", "count")
                ).reset_index()
                don_mensual["mes_str"] = don_mensual["fecha_donacion"].dt.strftime("%Y-%m")
                prom_mensual = don_mensual["monto"].mean()

                fig_line = go.Figure()
                fig_line.add_trace(go.Scatter(
                    x=don_mensual["mes_str"],
                    y=don_mensual["monto"],
                    mode="lines+markers",
                    name="Recaudo Mensual",
                    line=dict(color=COLOR_VERDE_OSCURO, width=3),
                    marker=dict(size=8, color=COLOR_AMBAR, line=dict(width=1.5, color=COLOR_VERDE_OSCURO)),
                    customdata=don_mensual["aportes"],
                    hovertemplate="<b>Mes: %{x}</b><br>Recaudo: $%{y:,.0f}<br>Aportes: %{customdata}<extra></extra>"
                ))
                fig_line.add_hline(
                    y=prom_mensual, line_dash="dash", line_color=COLOR_AMBAR,
                    annotation_text=f"Promedio mensual: ${prom_mensual:,.0f}",
                    annotation_position="top left",
                    annotation_font_color="#B86E22"
                )
                fig_line.update_layout(xaxis_title="Mes", yaxis_title="Recaudo Total ($)", showlegend=False)
                st.plotly_chart(aplicar_estilo_plotly(fig_line), use_container_width=True)

        st.divider()
        col_g3, col_g4 = st.columns(2)
        
        # --- GRÁFICA 3: SEGMENTACIÓN POR RANGOS ---
        with col_g3:
            if not don_efectivas.empty:
                st.markdown("#### Segmentación por Nivel de Aporte (Tiers)")
                bins = [0, 100, 500, 1000, 5000, 15000, float('inf')]
                labels = ['$1 - $100', '$101 - $500', '$501 - $1k', '$1k - $5k', '$5k - $15k', '+$15k']
                df_tiers = don_efectivas.copy()
                df_tiers["Rango"] = pd.cut(df_tiers["monto"], bins=bins, labels=labels)
                
                resumen_tiers = df_tiers.groupby("Rango", observed=False).agg(
                    Cantidad=("monto", "count"),
                    Total_Recaudado=("monto", "sum")
                ).reset_index()

                fig_tiers = px.bar(
                    resumen_tiers, x="Rango", y="Cantidad",
                    text="Cantidad",
                    custom_data=["Total_Recaudado"],
                    color="Total_Recaudado",
                    color_continuous_scale=["#D8C3A5", COLOR_AMBAR, "#9E5814"],
                    labels={"Cantidad": "Nº de Donaciones", "Total_Recaudado": "Recaudado ($)"}
                )
                fig_tiers.update_traces(
                    textposition="outside",
                    textfont_color=COLOR_VERDE_OSCURO,
                    hovertemplate="<b>Rango: %{x}</b><br>Nº Donaciones: %{y}<br>Total Recaudado: $%{customdata[0]:,.0f}<extra></extra>"
                )
                fig_tiers.update_layout(coloraxis_showscale=False, yaxis_title="Cantidad de Aportes")
                st.plotly_chart(aplicar_estilo_plotly(fig_tiers), use_container_width=True)
                st.caption(f"💡 Mientras el 50% de los aportes son ≤ **${ticket_mediana:,.0f}** (mediana), los aportes **+$15k** concentran la mayor parte del capital.")

        # --- GRÁFICA 4: VISITAS POR PESTAÑA ---
        with col_g4:
            if not all_visitas.empty:
                st.markdown("#### Visitas por Pestaña de Origen (Excel)")
                origen_counts = all_visitas["origen"].value_counts().reset_index()
                origen_counts.columns = ["Origen", "Visitas"]
                origen_counts = origen_counts.sort_values("Visitas", ascending=True)
                origen_counts["Pct"] = (origen_counts["Visitas"] / origen_counts["Visitas"].sum() * 100).round(1)

                fig_bar = px.bar(
                    origen_counts, x="Visitas", y="Origen", orientation="h",
                    text=origen_counts.apply(lambda r: f"{r['Visitas']} ({r['Pct']}%)", axis=1),
                    color="Visitas", 
                    color_continuous_scale=["#A3B19E", COLOR_VERDE_MEDIO, COLOR_VERDE_OSCURO]
                )
                fig_bar.update_traces(
                    textposition="outside",
                    textfont_color=COLOR_VERDE_OSCURO,
                    hovertemplate="<b>%{y}</b><br>Visitas: %{x}<extra></extra>"
                )
                fig_bar.update_layout(
                    coloraxis_showscale=False,
                    xaxis=dict(range=[0, origen_counts["Visitas"].max() * 1.25])
                )
                st.plotly_chart(aplicar_estilo_plotly(fig_bar), use_container_width=True)

        # --- GRÁFICA 5: DIAGRAMA DE CAJA (BOXPLOT) DE DONACIONES ---
        st.divider()
        if not don_efectivas.empty:
            st.markdown("#### Diagrama de Caja: Dispersión y Valores Atípicos de Donaciones")
            col_ctrl1, col_ctrl2 = st.columns(2)
            with col_ctrl1:
                agrupar_box = st.radio(
                    "Agrupar distribución por:",
                    ["Año", "Pestaña de Origen", "Global"],
                    horizontal=True,
                    key="box_group"
                )
            with col_ctrl2:
                escala_log = st.checkbox(
                    "Usar escala logarítmica (recomendado para visualizar cuartiles y outliers)",
                    value=True,
                    key="box_log"
                )

            df_box = don_efectivas.copy()
            df_box["Año"] = pd.to_datetime(df_box["fecha_donacion"]).dt.year.astype(str)
            df_box = df_box.sort_values("Año")

            if agrupar_box == "Año":
                x_col = "Año"
            elif agrupar_box == "Pestaña de Origen":
                x_col = "origen"
            else:
                df_box["Global"] = "Todas las Donaciones"
                x_col = "Global"

            fig_box = px.box(
                df_box,
                x=x_col,
                y="monto",
                color=x_col,
                points="outliers",
                hover_data={"donante": True, "fecha_donacion": True, "monto": ":$,.2f"},
                color_discrete_sequence=[COLOR_VERDE_OSCURO, COLOR_AMBAR, COLOR_VERDE_MEDIO, "#9E5814"],
                labels={x_col: agrupar_box, "monto": "Monto de Donación ($)", "donante": "Donante", "fecha_donacion": "Fecha"}
            )
            fig_box.update_traces(
                boxmean=True,
                marker=dict(size=7, opacity=0.85, line=dict(width=1, color=COLOR_VERDE_OSCURO))
            )
            fig_box.update_layout(
                showlegend=False,
                yaxis_type="log" if escala_log else "linear",
                yaxis_title="Monto Donado ($)"
            )
            st.plotly_chart(aplicar_estilo_plotly(fig_box), use_container_width=True)
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