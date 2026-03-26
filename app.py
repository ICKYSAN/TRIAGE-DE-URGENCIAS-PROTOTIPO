import io
import sqlite3
import hashlib
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st

DB_FILE = "triage_hospital.db"

st.set_page_config(
    page_title="TRIAGE IA HOSPITAL V4",
    page_icon="🏥",
    layout="wide",
)

st.markdown(
    """
    <style>
    .orange-box {background-color: #fff7ed; border-left: 8px solid #f97316; padding: 1rem; border-radius: 0.8rem;}
    .yellow-box {background-color: #fefce8; border-left: 8px solid #eab308; padding: 1rem; border-radius: 0.8rem;}
    .green-box {background-color: #f0fdf4; border-left: 8px solid #22c55e; padding: 1rem; border-radius: 0.8rem;}
    .small-muted {color: #6b7280; font-size: 0.9rem;}
    .pill-orange {background:#f97316;color:white;padding:0.2rem 0.6rem;border-radius:999px;font-weight:700;}
    .pill-yellow {background:#eab308;color:black;padding:0.2rem 0.6rem;border-radius:999px;font-weight:700;}
    .pill-green {background:#22c55e;color:white;padding:0.2rem 0.6rem;border-radius:999px;font-weight:700;}
    </style>
    """,
    unsafe_allow_html=True,
)


@dataclass
class TriageInput:
    folio: str
    nombre_paciente: str
    edad: int
    sexo: str
    motivo_consulta: str
    usuario_captura: str
    rol_usuario: str
    fecha_hora_ingreso: str

    frecuencia_cardiaca: int
    frecuencia_respiratoria: int
    presion_sistolica: int
    presion_diastolica: int
    temperatura: float
    saturacion_oxigeno: int
    glucosa_capilar: int
    dolor_eva: int
    estado_conciencia: str

    dolor_toracico: bool
    dificultad_respiratoria: bool
    fiebre: bool
    sangrado_activo: bool
    convulsiones: bool
    alteracion_mental: bool
    debilidad_unilateral: bool
    alteracion_habla: bool
    asimetria_facial: bool
    inicio_subito: bool
    sincope: bool
    palidez_diaforesis: bool
    trauma_reciente: bool
    antecedente_hipertension: bool
    antecedente_diabetes: bool
    puede_caminar: bool


def get_conn():
    return sqlite3.connect(DB_FILE, check_same_thread=False)


def hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        100000
    ).hex()


def authenticate_user(username: str, password: str) -> Optional[dict]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, username, full_name, role, salt, password_hash, is_active
        FROM users
        WHERE username = ?
    """, (username,))
    row = cur.fetchone()
    conn.close()

    if not row:
        return None

    user = {
        "id": row[0],
        "username": row[1],
        "full_name": row[2],
        "role": row[3],
        "salt": row[4],
        "password_hash": row[5],
        "is_active": row[6],
    }

    if user["is_active"] != 1:
        return None

    candidate_hash = hash_password(password, user["salt"])
    return user if candidate_hash == user["password_hash"] else None


def create_user(username: str, full_name: str, role: str, password: str):
    conn = get_conn()
    cur = conn.cursor()

    salt = hashlib.sha256(f"{username}{datetime.now()}".encode()).hexdigest()[:32]
    password_hash = hash_password(password, salt)

    cur.execute("""
        INSERT INTO users (username, full_name, role, salt, password_hash)
        VALUES (?, ?, ?, ?, ?)
    """, (username, full_name, role, salt, password_hash))

    conn.commit()
    conn.close()


def update_user(user_id: int, full_name: str, role: str, is_active: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        UPDATE users
        SET full_name = ?, role = ?, is_active = ?
        WHERE id = ?
    """, (full_name, role, is_active, user_id))
    conn.commit()
    conn.close()


def load_users_df() -> pd.DataFrame:
    conn = get_conn()
    df = pd.read_sql_query("""
        SELECT id, username, full_name, role, is_active, created_at
        FROM users
        ORDER BY id DESC
    """, conn)
    conn.close()
    return df


def resultado(
    semaforo: str,
    accion: str,
    motivos: List[str],
    alertas: List[str],
    data: TriageInput
) -> Dict[str, Any]:
    return {
        "folio": data.folio,
        "nombre_paciente": data.nombre_paciente,
        "semaforo": semaforo,
        "accion_sugerida": accion,
        "motivos": motivos,
        "alertas": alertas,
        "datos_capturados": asdict(data),
        "aviso_legal": (
            "Herramienta de apoyo para priorización clínica. "
            "No sustituye la valoración médica ni el juicio clínico del personal de salud."
        ),
    }


def evaluar_triage(data: TriageInput) -> Dict[str, Any]:
    alertas: List[str] = []
    motivos: List[str] = []
    estado_conciencia = data.estado_conciencia.strip().lower()

    if estado_conciencia == "inconsciente":
        motivos.append("Paciente inconsciente")
        return resultado("NARANJA", "Valoración médica inmediata", motivos, alertas, data)

    if data.convulsiones:
        motivos.append("Convulsiones activas o recientes")
        return resultado("NARANJA", "Valoración médica inmediata", motivos, alertas, data)

    if data.saturacion_oxigeno < 90:
        motivos.append(f"Saturación de oxígeno crítica: {data.saturacion_oxigeno}%")
        alertas.append("Compromiso respiratorio")
        return resultado("NARANJA", "Valoración médica inmediata", motivos, alertas, data)

    if data.presion_sistolica < 90:
        motivos.append(f"Hipotensión: TA sistólica {data.presion_sistolica} mmHg")
        return resultado("NARANJA", "Valoración médica inmediata", motivos, alertas, data)

    if data.sangrado_activo:
        motivos.append("Sangrado activo")
        return resultado("NARANJA", "Valoración médica inmediata", motivos, alertas, data)

    if data.dificultad_respiratoria and data.saturacion_oxigeno < 90:
        motivos.append("Dificultad respiratoria con desaturación")
        alertas.append("Compromiso respiratorio")
        return resultado("NARANJA", "Valoración médica inmediata", motivos, alertas, data)

    if data.frecuencia_respiratoria > 30:
        motivos.append(f"Taquipnea severa: FR {data.frecuencia_respiratoria}")
        alertas.append("Compromiso respiratorio")
        return resultado("NARANJA", "Valoración médica inmediata", motivos, alertas, data)

    if data.inicio_subito and (
        data.alteracion_habla or data.debilidad_unilateral or data.asimetria_facial
    ):
        motivos.append("Déficit neurológico súbito")
        if data.alteracion_habla:
            motivos.append("Alteración del habla")
        if data.debilidad_unilateral:
            motivos.append("Debilidad unilateral")
        if data.asimetria_facial:
            motivos.append("Asimetría facial")
        alertas.append("Código Cerebro")
        return resultado(
            "NARANJA",
            "Activar protocolo neurológico / valoración inmediata",
            motivos,
            alertas,
            data,
        )

    if data.dolor_toracico and data.palidez_diaforesis and (
        data.presion_sistolica < 90 or data.saturacion_oxigeno < 94
    ):
        motivos.append("Dolor torácico con datos de alto riesgo")
        if data.palidez_diaforesis:
            motivos.append("Palidez o diaforesis")
        alertas.append("Código Infarto")
        return resultado(
            "NARANJA",
            "Activar protocolo cardiovascular / valoración inmediata",
            motivos,
            alertas,
            data,
        )

    if estado_conciencia == "confuso" and not data.puede_caminar:
        motivos.append("Confusión con incapacidad funcional")
        return resultado("NARANJA", "Valoración médica inmediata", motivos, alertas, data)

    sepsis_criterios = 0
    if data.temperatura > 38 or data.temperatura < 36:
        sepsis_criterios += 1
    if data.frecuencia_cardiaca > 90:
        sepsis_criterios += 1
    if data.frecuencia_respiratoria > 22:
        sepsis_criterios += 1
    if data.alteracion_mental or estado_conciencia in ["somnoliento", "confuso"]:
        sepsis_criterios += 1

    if sepsis_criterios >= 3:
        motivos.append("Sospecha de sepsis")
        motivos.append(f"Criterios positivos: {sepsis_criterios}")
        alertas.append("Código Sepsis")
        return resultado("AMARILLO", "Valoración médica prioritaria", motivos, alertas, data)

    if 90 <= data.saturacion_oxigeno <= 93:
        motivos.append(f"Saturación limítrofe: {data.saturacion_oxigeno}%")
        return resultado("AMARILLO", "Valoración médica prioritaria", motivos, alertas, data)

    if data.frecuencia_cardiaca > 120:
        motivos.append(f"Taquicardia: FC {data.frecuencia_cardiaca}")
        return resultado("AMARILLO", "Valoración médica prioritaria", motivos, alertas, data)

    if data.frecuencia_respiratoria > 22:
        motivos.append(f"Taquipnea: FR {data.frecuencia_respiratoria}")
        return resultado("AMARILLO", "Valoración médica prioritaria", motivos, alertas, data)

    if estado_conciencia in ["somnoliento", "confuso"] or data.alteracion_mental:
        motivos.append("Alteración del estado mental no crítica")
        return resultado("AMARILLO", "Valoración médica prioritaria", motivos, alertas, data)

    if data.dolor_toracico:
        motivos.append("Dolor torácico sin criterios de máxima prioridad")
        return resultado("AMARILLO", "Valoración médica prioritaria", motivos, alertas, data)

    if data.dificultad_respiratoria:
        motivos.append("Dificultad respiratoria leve a moderada")
        alertas.append("Compromiso respiratorio")
        return resultado("AMARILLO", "Valoración médica prioritaria", motivos, alertas, data)

    if data.dolor_eva >= 5:
        motivos.append(f"Dolor significativo EVA {data.dolor_eva}/10")
        return resultado("AMARILLO", "Valoración médica prioritaria", motivos, alertas, data)

    if data.fiebre:
        motivos.append("Fiebre")
        return resultado("AMARILLO", "Valoración médica prioritaria", motivos, alertas, data)

    if data.trauma_reciente:
        motivos.append("Trauma reciente con estabilidad hemodinámica")
        return resultado("AMARILLO", "Valoración médica prioritaria", motivos, alertas, data)

    if data.glucosa_capilar < 70 or data.glucosa_capilar > 250:
        motivos.append(f"Glucosa alterada: {data.glucosa_capilar} mg/dL")
        return resultado("AMARILLO", "Valoración médica prioritaria", motivos, alertas, data)

    motivos.append("Paciente estable, sin datos de alarma mayores")
    return resultado("VERDE", "Atención diferida", motivos, alertas, data)


def save_triage(data: TriageInput, res: Dict[str, Any], tipo_registro: str = "Inicial"):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO triage_records (
            fecha_registro, tipo_registro, folio, nombre_paciente, edad, sexo, motivo_consulta,
            usuario_captura, rol_usuario, fecha_hora_ingreso,
            frecuencia_cardiaca, frecuencia_respiratoria, presion_sistolica, presion_diastolica,
            temperatura, saturacion_oxigeno, glucosa_capilar, dolor_eva, estado_conciencia,
            dolor_toracico, dificultad_respiratoria, fiebre, sangrado_activo, convulsiones,
            alteracion_mental, debilidad_unilateral, alteracion_habla, asimetria_facial,
            inicio_subito, sincope, palidez_diaforesis, trauma_reciente,
            antecedente_hipertension, antecedente_diabetes, puede_caminar,
            semaforo, accion_sugerida, motivos, alertas, estado_operativo
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        tipo_registro,
        data.folio,
        data.nombre_paciente,
        data.edad,
        data.sexo,
        data.motivo_consulta,
        data.usuario_captura,
        data.rol_usuario,
        data.fecha_hora_ingreso,
        data.frecuencia_cardiaca,
        data.frecuencia_respiratoria,
        data.presion_sistolica,
        data.presion_diastolica,
        data.temperatura,
        data.saturacion_oxigeno,
        data.glucosa_capilar,
        data.dolor_eva,
        data.estado_conciencia,
        int(data.dolor_toracico),
        int(data.dificultad_respiratoria),
        int(data.fiebre),
        int(data.sangrado_activo),
        int(data.convulsiones),
        int(data.alteracion_mental),
        int(data.debilidad_unilateral),
        int(data.alteracion_habla),
        int(data.asimetria_facial),
        int(data.inicio_subito),
        int(data.sincope),
        int(data.palidez_diaforesis),
        int(data.trauma_reciente),
        int(data.antecedente_hipertension),
        int(data.antecedente_diabetes),
        int(data.puede_caminar),
        res["semaforo"],
        res["accion_sugerida"],
        " | ".join(res["motivos"]),
        " | ".join(res["alertas"]) if res["alertas"] else "",
        "Pendiente"
    ))

    conn.commit()
    conn.close()


def load_triage_df() -> pd.DataFrame:
    conn = get_conn()
    df = pd.read_sql_query("SELECT * FROM triage_records ORDER BY id DESC", conn)
    conn.close()
    return df


def load_operational_df() -> pd.DataFrame:
    conn = get_conn()
    df = pd.read_sql_query("""
        SELECT id, fecha_registro, tipo_registro, folio, nombre_paciente,
               semaforo, accion_sugerida, usuario_captura, rol_usuario,
               estado_operativo, motivos, alertas
        FROM triage_records
        ORDER BY datetime(fecha_registro) DESC, id DESC
    """, conn)
    conn.close()
    return df


def get_latest_patient_by_folio(folio: str) -> Optional[dict]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT folio, nombre_paciente, edad, sexo, motivo_consulta, fecha_hora_ingreso,
               frecuencia_cardiaca, frecuencia_respiratoria, presion_sistolica, presion_diastolica,
               temperatura, saturacion_oxigeno, glucosa_capilar, dolor_eva, estado_conciencia,
               dolor_toracico, dificultad_respiratoria, fiebre, sangrado_activo, convulsiones,
               alteracion_mental, debilidad_unilateral, alteracion_habla, asimetria_facial,
               inicio_subito, sincope, palidez_diaforesis, trauma_reciente,
               antecedente_hipertension, antecedente_diabetes, puede_caminar
        FROM triage_records
        WHERE folio = ?
        ORDER BY id DESC
        LIMIT 1
    """, (folio,))
    row = cur.fetchone()
    conn.close()

    if not row:
        return None

    keys = [
        "folio", "nombre_paciente", "edad", "sexo", "motivo_consulta", "fecha_hora_ingreso",
        "frecuencia_cardiaca", "frecuencia_respiratoria", "presion_sistolica", "presion_diastolica",
        "temperatura", "saturacion_oxigeno", "glucosa_capilar", "dolor_eva", "estado_conciencia",
        "dolor_toracico", "dificultad_respiratoria", "fiebre", "sangrado_activo", "convulsiones",
        "alteracion_mental", "debilidad_unilateral", "alteracion_habla", "asimetria_facial",
        "inicio_subito", "sincope", "palidez_diaforesis", "trauma_reciente",
        "antecedente_hipertension", "antecedente_diabetes", "puede_caminar"
    ]
    patient = dict(zip(keys, row))

    bool_fields = [
        "dolor_toracico", "dificultad_respiratoria", "fiebre", "sangrado_activo", "convulsiones",
        "alteracion_mental", "debilidad_unilateral", "alteracion_habla", "asimetria_facial",
        "inicio_subito", "sincope", "palidez_diaforesis", "trauma_reciente",
        "antecedente_hipertension", "antecedente_diabetes", "puede_caminar"
    ]
    for field in bool_fields:
        patient[field] = bool(patient[field])

    return patient


def update_operational_status(record_id: int, estado_operativo: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        UPDATE triage_records
        SET estado_operativo = ?
        WHERE id = ?
    """, (estado_operativo, record_id))
    conn.commit()
    conn.close()


def calculate_wait_minutes(fecha_registro_value) -> Optional[int]:
    if pd.isna(fecha_registro_value):
        return None
    dt = pd.to_datetime(fecha_registro_value, errors="coerce")
    if pd.isna(dt):
        return None
    delta = datetime.now() - dt.to_pydatetime()
    return max(int(delta.total_seconds() // 60), 0)


def expected_reassessment_minutes(semaforo: str) -> int:
    if semaforo == "NARANJA":
        return 0
    if semaforo == "AMARILLO":
        return 30
    return 60


def color_badge(semaforo: str) -> str:
    if semaforo == "NARANJA":
        return '<span class="pill-orange">NARANJA</span>'
    if semaforo == "AMARILLO":
        return '<span class="pill-yellow">AMARILLO</span>'
    return '<span class="pill-green">VERDE</span>'


def dataframe_to_excel_bytes(df: pd.DataFrame) -> bytes:
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Triage")
    return output.getvalue()


def build_printable_html(record: pd.Series) -> str:
    return f"""
    <html>
    <head>
        <title>Hoja de Triage</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 24px; }}
            h1, h2 {{ margin-bottom: 8px; }}
            .section {{ margin-top: 16px; padding: 12px; border: 1px solid #ccc; border-radius: 8px; }}
            .label {{ font-weight: bold; }}
            .print-btn {{ margin-bottom: 20px; }}
        </style>
    </head>
    <body>
        <button class="print-btn" onclick="window.print()">Imprimir hoja de triage</button>
        <h1>Hoja de Triage</h1>
        <div class="section">
            <p><span class="label">Folio:</span> {record.get('folio', '')}</p>
            <p><span class="label">Nombre:</span> {record.get('nombre_paciente', '')}</p>
            <p><span class="label">Edad:</span> {record.get('edad', '')}</p>
            <p><span class="label">Sexo:</span> {record.get('sexo', '')}</p>
            <p><span class="label">Motivo de consulta:</span> {record.get('motivo_consulta', '')}</p>
            <p><span class="label">Fecha de registro:</span> {record.get('fecha_registro', '')}</p>
            <p><span class="label">Usuario capturista:</span> {record.get('usuario_captura', '')}</p>
        </div>

        <div class="section">
            <h2>Signos vitales</h2>
            <p><span class="label">FC:</span> {record.get('frecuencia_cardiaca', '')}</p>
            <p><span class="label">FR:</span> {record.get('frecuencia_respiratoria', '')}</p>
            <p><span class="label">TA:</span> {record.get('presion_sistolica', '')}/{record.get('presion_diastolica', '')}</p>
            <p><span class="label">Temperatura:</span> {record.get('temperatura', '')}</p>
            <p><span class="label">SpO2:</span> {record.get('saturacion_oxigeno', '')}</p>
            <p><span class="label">Glucosa:</span> {record.get('glucosa_capilar', '')}</p>
            <p><span class="label">Dolor EVA:</span> {record.get('dolor_eva', '')}</p>
            <p><span class="label">Estado de conciencia:</span> {record.get('estado_conciencia', '')}</p>
        </div>

        <div class="section">
            <h2>Resultado</h2>
            <p><span class="label">Semáforo:</span> {record.get('semaforo', '')}</p>
            <p><span class="label">Acción sugerida:</span> {record.get('accion_sugerida', '')}</p>
            <p><span class="label">Motivos:</span> {record.get('motivos', '')}</p>
            <p><span class="label">Alertas:</span> {record.get('alertas', '')}</p>
            <p><span class="label">Tipo de registro:</span> {record.get('tipo_registro', '')}</p>
            <p><span class="label">Estado operativo:</span> {record.get('estado_operativo', '')}</p>
        </div>
    </body>
    </html>
    """


def logout():
    st.session_state.logged_in = False
    st.session_state.user = None
    st.rerun()


if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "user" not in st.session_state:
    st.session_state.user = None


if not st.session_state.logged_in:
    st.title("🔐 Login - TRIAGE IA HOSPITAL V4")

    with st.form("login_form"):
        username = st.text_input("Usuario")
        password = st.text_input("Contraseña", type="password")
        login_btn = st.form_submit_button("Entrar")

    if login_btn:
        user = authenticate_user(username, password)
        if user:
            st.session_state.logged_in = True
            st.session_state.user = user
            st.success("Acceso correcto")
            st.rerun()
        else:
            st.error("Usuario o contraseña incorrectos")

    st.info("Usuario inicial: admin | Contraseña inicial: Admin1234")

else:
    user = st.session_state.user

    st.sidebar.success(f"Sesión activa: {user['full_name']}")
    st.sidebar.write(f"Rol: {user['role']}")
    if st.sidebar.button("Cerrar sesión"):
        logout()

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "Triage Inicial",
        "Revaloración",
        "Bandeja Operativa",
        "Dashboard",
        "Usuarios"
    ])

    with tab1:
        st.title("🏥 TRIAGE INICIAL")

        with st.form("triage_form"):
            st.subheader("1. Datos del paciente")
            col1, col2, col3 = st.columns(3)

            with col1:
                folio = st.text_input("Folio", value="P001")
                nombre_paciente = st.text_input("Nombre del paciente")
                edad = st.number_input("Edad", min_value=0, max_value=120, value=45)

            with col2:
                sexo = st.selectbox("Sexo", ["Femenino", "Masculino", "Otro"])
                motivo_consulta = st.text_input("Motivo principal de consulta")
                st.text_input("Personal que realiza el triage", value=user["full_name"], disabled=True)

            with col3:
                fecha_hora_ingreso = st.text_input(
                    "Fecha y hora de ingreso",
                    value=datetime.now().strftime("%Y-%m-%d %H:%M")
                )

            st.subheader("2. Signos vitales")
            c1, c2, c3, c4 = st.columns(4)

            with c1:
                frecuencia_cardiaca = st.number_input("Frecuencia cardiaca", 0, 300, 80, key="ini_fc")
                presion_sistolica = st.number_input("TA sistólica", 0, 300, 120, key="ini_pas")

            with c2:
                frecuencia_respiratoria = st.number_input("Frecuencia respiratoria", 0, 80, 18, key="ini_fr")
                presion_diastolica = st.number_input("TA diastólica", 0, 200, 80, key="ini_pad")

            with c3:
                temperatura = st.number_input("Temperatura °C", 30.0, 45.0, 36.5, step=0.1, key="ini_temp")
                saturacion_oxigeno = st.number_input("Saturación de oxígeno %", 0, 100, 98, key="ini_spo2")

            with c4:
                glucosa_capilar = st.number_input("Glucosa capilar mg/dL", 0, 1000, 100, key="ini_glu")
                dolor_eva = st.slider("Dolor EVA", 0, 10, 0, key="ini_dolor")
                estado_conciencia = st.selectbox(
                    "Estado de conciencia",
                    ["alerta", "somnoliento", "confuso", "inconsciente"],
                    key="ini_estado"
                )

            st.subheader("3. Preguntas de alarma")
            p1, p2, p3, p4 = st.columns(4)

            with p1:
                dolor_toracico = st.checkbox("Dolor torácico", key="ini_dt")
                dificultad_respiratoria = st.checkbox("Dificultad respiratoria", key="ini_dr")
                fiebre = st.checkbox("Fiebre", key="ini_fiebre")
                sangrado_activo = st.checkbox("Sangrado activo", key="ini_sangrado")

            with p2:
                convulsiones = st.checkbox("Convulsiones", key="ini_conv")
                alteracion_mental = st.checkbox("Alteración mental", key="ini_altm")
                debilidad_unilateral = st.checkbox("Debilidad unilateral", key="ini_deb")
                alteracion_habla = st.checkbox("Alteración del habla", key="ini_habla")

            with p3:
                asimetria_facial = st.checkbox("Asimetría facial", key="ini_cara")
                inicio_subito = st.checkbox("Inicio súbito", key="ini_inicio")
                sincope = st.checkbox("Síncope", key="ini_sincope")
                palidez_diaforesis = st.checkbox("Palidez o diaforesis", key="ini_palidez")

            with p4:
                trauma_reciente = st.checkbox("Trauma reciente", key="ini_trauma")
                antecedente_hipertension = st.checkbox("Antecedente de hipertensión", key="ini_hta")
                antecedente_diabetes = st.checkbox("Antecedente de diabetes", key="ini_dm")
                puede_caminar = st.checkbox("Puede caminar por sí mismo", value=True, key="ini_camina")

            submitted = st.form_submit_button("Clasificar paciente")

        if submitted:
            data = TriageInput(
                folio=folio,
                nombre_paciente=nombre_paciente,
                edad=int(edad),
                sexo=sexo,
                motivo_consulta=motivo_consulta,
                usuario_captura=user["full_name"],
                rol_usuario=user["role"],
                fecha_hora_ingreso=fecha_hora_ingreso,
                frecuencia_cardiaca=int(frecuencia_cardiaca),
                frecuencia_respiratoria=int(frecuencia_respiratoria),
                presion_sistolica=int(presion_sistolica),
                presion_diastolica=int(presion_diastolica),
                temperatura=float(temperatura),
                saturacion_oxigeno=int(saturacion_oxigeno),
                glucosa_capilar=int(glucosa_capilar),
                dolor_eva=int(dolor_eva),
                estado_conciencia=estado_conciencia,
                dolor_toracico=bool(dolor_toracico),
                dificultad_respiratoria=bool(dificultad_respiratoria),
                fiebre=bool(fiebre),
                sangrado_activo=bool(sangrado_activo),
                convulsiones=bool(convulsiones),
                alteracion_mental=bool(alteracion_mental),
                debilidad_unilateral=bool(debilidad_unilateral),
                alteracion_habla=bool(alteracion_habla),
                asimetria_facial=bool(asimetria_facial),
                inicio_subito=bool(inicio_subito),
                sincope=bool(sincope),
                palidez_diaforesis=bool(palidez_diaforesis),
                trauma_reciente=bool(trauma_reciente),
                antecedente_hipertension=bool(antecedente_hipertension),
                antecedente_diabetes=bool(antecedente_diabetes),
                puede_caminar=bool(puede_caminar),
            )

            res = evaluar_triage(data)
            save_triage(data, res, tipo_registro="Inicial")

            st.subheader("Resultado del triage")
            if res["semaforo"] == "NARANJA":
                st.markdown(
                    f"""<div class="orange-box"><h2>🟠 {res["semaforo"]}</h2><p><strong>Acción sugerida:</strong> {res["accion_sugerida"]}</p></div>""",
                    unsafe_allow_html=True,
                )
            elif res["semaforo"] == "AMARILLO":
                st.markdown(
                    f"""<div class="yellow-box"><h2>🟡 {res["semaforo"]}</h2><p><strong>Acción sugerida:</strong> {res["accion_sugerida"]}</p></div>""",
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f"""<div class="green-box"><h2>🟢 {res["semaforo"]}</h2><p><strong>Acción sugerida:</strong> {res["accion_sugerida"]}</p></div>""",
                    unsafe_allow_html=True,
                )

            st.markdown("**Motivos de clasificación**")
            for motivo in res["motivos"]:
                st.write(f"- {motivo}")

            st.markdown("**Alertas activadas**")
            if res["alertas"]:
                for alerta in res["alertas"]:
                    st.write(f"- {alerta}")
            else:
                st.write("- Sin alertas específicas")

            st.caption(res["aviso_legal"])
            st.success("Paciente guardado en la base de datos")

    with tab2:
        st.title("🔁 REVALORACIÓN DEL PACIENTE")

        folio_reval = st.text_input("Buscar folio para revaloración")

        patient = None
        if folio_reval.strip():
            patient = get_latest_patient_by_folio(folio_reval.strip())
            if patient:
                st.success("Paciente encontrado")
            else:
                st.warning("No se encontró ese folio")

        if patient:
            with st.form("revaloracion_form"):
                st.subheader("Datos del paciente")
                col1, col2, col3 = st.columns(3)

                with col1:
                    st.text_input("Folio", value=patient["folio"], disabled=True)
                    rv_nombre = st.text_input("Nombre", value=patient["nombre_paciente"])
                    rv_edad = st.number_input("Edad", min_value=0, max_value=120, value=int(patient["edad"]))

                with col2:
                    sexos = ["Femenino", "Masculino", "Otro"]
                    rv_sexo = st.selectbox(
                        "Sexo",
                        sexos,
                        index=sexos.index(patient["sexo"]) if patient["sexo"] in sexos else 0
                    )
                    rv_motivo = st.text_input("Motivo de consulta", value=patient["motivo_consulta"])
                    st.text_input("Revalorado por", value=user["full_name"], disabled=True)

                with col3:
                    rv_fecha_hora_ingreso = st.text_input("Fecha y hora de ingreso", value=patient["fecha_hora_ingreso"])

                st.subheader("Signos vitales")
                c1, c2, c3, c4 = st.columns(4)

                with c1:
                    rv_fc = st.number_input("Frecuencia cardiaca", 0, 300, int(patient["frecuencia_cardiaca"]), key="rv_fc")
                    rv_pas = st.number_input("TA sistólica", 0, 300, int(patient["presion_sistolica"]), key="rv_pas")
                with c2:
                    rv_fr = st.number_input("Frecuencia respiratoria", 0, 80, int(patient["frecuencia_respiratoria"]), key="rv_fr")
                    rv_pad = st.number_input("TA diastólica", 0, 200, int(patient["presion_diastolica"]), key="rv_pad")
                with c3:
                    rv_temp = st.number_input("Temperatura °C", 30.0, 45.0, float(patient["temperatura"]), step=0.1, key="rv_temp")
                    rv_spo2 = st.number_input("Saturación de oxígeno %", 0, 100, int(patient["saturacion_oxigeno"]), key="rv_spo2")
                with c4:
                    rv_glu = st.number_input("Glucosa capilar mg/dL", 0, 1000, int(patient["glucosa_capilar"]), key="rv_glu")
                    rv_dolor = st.slider("Dolor EVA", 0, 10, int(patient["dolor_eva"]), key="rv_dolor")
                    estados = ["alerta", "somnoliento", "confuso", "inconsciente"]
                    rv_estado = st.selectbox("Estado de conciencia", estados, index=estados.index(patient["estado_conciencia"]) if patient["estado_conciencia"] in estados else 0)

                st.subheader("Preguntas de alarma")
                p1, p2, p3, p4 = st.columns(4)

                with p1:
                    rv_dt = st.checkbox("Dolor torácico", value=patient["dolor_toracico"], key="rv_dt")
                    rv_dr = st.checkbox("Dificultad respiratoria", value=patient["dificultad_respiratoria"], key="rv_dr")
                    rv_fiebre = st.checkbox("Fiebre", value=patient["fiebre"], key="rv_fiebre")
                    rv_sangrado = st.checkbox("Sangrado activo", value=patient["sangrado_activo"], key="rv_sangrado")
                with p2:
                    rv_conv = st.checkbox("Convulsiones", value=patient["convulsiones"], key="rv_conv")
                    rv_altm = st.checkbox("Alteración mental", value=patient["alteracion_mental"], key="rv_altm")
                    rv_deb = st.checkbox("Debilidad unilateral", value=patient["debilidad_unilateral"], key="rv_deb")
                    rv_habla = st.checkbox("Alteración del habla", value=patient["alteracion_habla"], key="rv_habla")
                with p3:
                    rv_cara = st.checkbox("Asimetría facial", value=patient["asimetria_facial"], key="rv_cara")
                    rv_inicio = st.checkbox("Inicio súbito", value=patient["inicio_subito"], key="rv_inicio")
                    rv_sincope = st.checkbox("Síncope", value=patient["sincope"], key="rv_sincope")
                    rv_palidez = st.checkbox("Palidez o diaforesis", value=patient["palidez_diaforesis"], key="rv_palidez")
                with p4:
                    rv_trauma = st.checkbox("Trauma reciente", value=patient["trauma_reciente"], key="rv_trauma")
                    rv_hta = st.checkbox("Antecedente de hipertensión", value=patient["antecedente_hipertension"], key="rv_hta")
                    rv_dm = st.checkbox("Antecedente de diabetes", value=patient["antecedente_diabetes"], key="rv_dm")
                    rv_camina = st.checkbox("Puede caminar por sí mismo", value=patient["puede_caminar"], key="rv_camina")

                rv_submit = st.form_submit_button("Guardar revaloración")

            if rv_submit:
                rv_data = TriageInput(
                    folio=patient["folio"],
                    nombre_paciente=rv_nombre,
                    edad=int(rv_edad),
                    sexo=rv_sexo,
                    motivo_consulta=rv_motivo,
                    usuario_captura=user["full_name"],
                    rol_usuario=user["role"],
                    fecha_hora_ingreso=rv_fecha_hora_ingreso,
                    frecuencia_cardiaca=int(rv_fc),
                    frecuencia_respiratoria=int(rv_fr),
                    presion_sistolica=int(rv_pas),
                    presion_diastolica=int(rv_pad),
                    temperatura=float(rv_temp),
                    saturacion_oxigeno=int(rv_spo2),
                    glucosa_capilar=int(rv_glu),
                    dolor_eva=int(rv_dolor),
                    estado_conciencia=rv_estado,
                    dolor_toracico=bool(rv_dt),
                    dificultad_respiratoria=bool(rv_dr),
                    fiebre=bool(rv_fiebre),
                    sangrado_activo=bool(rv_sangrado),
                    convulsiones=bool(rv_conv),
                    alteracion_mental=bool(rv_altm),
                    debilidad_unilateral=bool(rv_deb),
                    alteracion_habla=bool(rv_habla),
                    asimetria_facial=bool(rv_cara),
                    inicio_subito=bool(rv_inicio),
                    sincope=bool(rv_sincope),
                    palidez_diaforesis=bool(rv_palidez),
                    trauma_reciente=bool(rv_trauma),
                    antecedente_hipertension=bool(rv_hta),
                    antecedente_diabetes=bool(rv_dm),
                    puede_caminar=bool(rv_camina),
                )

                rv_res = evaluar_triage(rv_data)
                save_triage(rv_data, rv_res, tipo_registro="Revaloración")

                st.subheader("Resultado de revaloración")
                if rv_res["semaforo"] == "NARANJA":
                    st.markdown(f"""<div class="orange-box"><h2>🟠 {rv_res["semaforo"]}</h2><p><strong>Acción sugerida:</strong> {rv_res["accion_sugerida"]}</p></div>""", unsafe_allow_html=True)
                elif rv_res["semaforo"] == "AMARILLO":
                    st.markdown(f"""<div class="yellow-box"><h2>🟡 {rv_res["semaforo"]}</h2><p><strong>Acción sugerida:</strong> {rv_res["accion_sugerida"]}</p></div>""", unsafe_allow_html=True)
                else:
                    st.markdown(f"""<div class="green-box"><h2>🟢 {rv_res["semaforo"]}</h2><p><strong>Acción sugerida:</strong> {rv_res["accion_sugerida"]}</p></div>""", unsafe_allow_html=True)

                st.success("Revaloración guardada correctamente")

    with tab3:
        st.title("🧭 BANDEJA OPERATIVA")
        st.caption("Vista en tiempo real de pacientes registrados y revalorados.")

        oper_df = load_operational_df()

        if oper_df.empty:
            st.warning("No hay registros operativos.")
        else:
            oper_df["fecha_registro"] = pd.to_datetime(oper_df["fecha_registro"], errors="coerce")
            oper_df["minutos_espera"] = oper_df["fecha_registro"].apply(calculate_wait_minutes)
            oper_df["meta_revaloracion_min"] = oper_df["semaforo"].apply(expected_reassessment_minutes)

            col1, col2, col3 = st.columns(3)
            with col1:
                semaforo_oper = st.selectbox("Filtrar por semáforo", ["Todos", "NARANJA", "AMARILLO", "VERDE"])
            with col2:
                estado_oper = st.selectbox("Filtrar por estado", ["Todos", "Pendiente", "Atendido", "Revaloración"])
            with col3:
                folio_oper = st.text_input("Buscar folio")

            oper_filtrado = oper_df.copy()

            if semaforo_oper != "Todos":
                oper_filtrado = oper_filtrado[oper_filtrado["semaforo"] == semaforo_oper]

            if estado_oper != "Todos":
                oper_filtrado = oper_filtrado[oper_filtrado["estado_operativo"] == estado_oper]

            if folio_oper.strip():
                oper_filtrado = oper_filtrado[
                    oper_filtrado["folio"].astype(str).str.contains(folio_oper.strip(), case=False, na=False)
                ]

            st.subheader("Resumen visual")
            for _, row in oper_filtrado.head(20).iterrows():
                wait = row["minutos_espera"]
                meta = row["meta_revaloracion_min"]
                excedido = "Sí" if meta > 0 and wait is not None and wait > meta else "No"
                c1, c2, c3, c4, c5, c6 = st.columns([1.2, 1.8, 1.3, 1.2, 1.2, 2.3])
                with c1:
                    st.markdown(color_badge(row["semaforo"]), unsafe_allow_html=True)
                with c2:
                    st.write(f"**{row['folio']}**")
                    st.caption(str(row["nombre_paciente"]))
                with c3:
                    st.write(row["tipo_registro"])
                with c4:
                    st.write(f"{wait} min" if wait is not None else "-")
                with c5:
                    st.write(row["estado_operativo"])
                with c6:
                    st.write(f"Meta: {meta} min | Excedido: {excedido}")

            st.subheader("Tabla operativa")
            st.dataframe(
                oper_filtrado[[
                    "id", "fecha_registro", "tipo_registro", "folio", "nombre_paciente",
                    "semaforo", "estado_operativo", "usuario_captura", "minutos_espera",
                    "meta_revaloracion_min", "accion_sugerida"
                ]],
                use_container_width=True
            )

            st.subheader("Actualizar estado operativo")
            ids_disponibles = oper_filtrado["id"].tolist()

            if ids_disponibles:
                c1, c2 = st.columns(2)
                with c1:
                    selected_id = st.selectbox("Selecciona ID de registro", ids_disponibles)
                with c2:
                    nuevo_estado = st.selectbox("Nuevo estado", ["Pendiente", "Atendido", "Revaloración"])

                if st.button("Actualizar estado operativo"):
                    update_operational_status(int(selected_id), nuevo_estado)
                    st.success("Estado actualizado")
                    st.rerun()
            else:
                st.info("No hay registros para actualizar con los filtros actuales.")

    with tab4:
        st.title("📊 DASHBOARD")

        df = load_triage_df()

        if df.empty:
            st.warning("No hay registros en la base de datos.")
        else:
            df["fecha_registro"] = pd.to_datetime(df["fecha_registro"], errors="coerce")
            df["minutos_espera"] = df["fecha_registro"].apply(calculate_wait_minutes)

            c1, c2, c3, c4, c5, c6 = st.columns(6)

            fecha_min = df["fecha_registro"].min().date()
            fecha_max = df["fecha_registro"].max().date()

            with c1:
                fecha_inicio = st.date_input("Fecha inicio", value=fecha_min)
            with c2:
                fecha_fin = st.date_input("Fecha fin", value=fecha_max)
            with c3:
                usuarios = ["Todos"] + sorted(df["usuario_captura"].dropna().astype(str).unique().tolist())
                usuario_filtro = st.selectbox("Usuario capturista", usuarios)
            with c4:
                semaforos = ["Todos", "NARANJA", "AMARILLO", "VERDE"]
                semaforo_filtro = st.selectbox("Semáforo", semaforos)
            with c5:
                folio_filtro = st.text_input("Buscar por folio")
            with c6:
                nombre_filtro = st.text_input("Buscar por nombre")

            filtrado = df[
                (df["fecha_registro"].dt.date >= fecha_inicio) &
                (df["fecha_registro"].dt.date <= fecha_fin)
            ]

            if usuario_filtro != "Todos":
                filtrado = filtrado[filtrado["usuario_captura"] == usuario_filtro]

            if semaforo_filtro != "Todos":
                filtrado = filtrado[filtrado["semaforo"] == semaforo_filtro]

            if folio_filtro.strip():
                filtrado = filtrado[
                    filtrado["folio"].astype(str).str.contains(folio_filtro.strip(), case=False, na=False)
                ]

            if nombre_filtro.strip():
                filtrado = filtrado[
                    filtrado["nombre_paciente"].astype(str).str.contains(nombre_filtro.strip(), case=False, na=False)
                ]

            m1, m2, m3, m4, m5, m6 = st.columns(6)
            m1.metric("Total", int(len(filtrado)))
            m2.metric("🟠 Naranja", int((filtrado["semaforo"] == "NARANJA").sum()))
            m3.metric("🟡 Amarillo", int((filtrado["semaforo"] == "AMARILLO").sum()))
            m4.metric("🟢 Verde", int((filtrado["semaforo"] == "VERDE").sum()))
            m5.metric("🔁 Revaloraciones", int((filtrado["tipo_registro"] == "Revaloración").sum()))
            m6.metric("⏱ Espera prom. min", round(float(filtrado["minutos_espera"].dropna().mean()), 1) if not filtrado.empty else 0)

            if not filtrado.empty:
                st.subheader("Distribución por semáforo")
                st.bar_chart(filtrado["semaforo"].value_counts())

                st.subheader("Distribución por tipo de registro")
                st.bar_chart(filtrado["tipo_registro"].value_counts())

                st.subheader("Resultados")
                st.dataframe(filtrado, use_container_width=True)

                csv_data = filtrado.to_csv(index=False).encode("utf-8")
                st.download_button(
                    "Descargar resultados filtrados en CSV",
                    data=csv_data,
                    file_name="triage_filtrado_v4.csv",
                    mime="text/csv",
                )

                excel_bytes = dataframe_to_excel_bytes(filtrado)
                st.download_button(
                    "Descargar resultados filtrados en Excel",
                    data=excel_bytes,
                    file_name="triage_filtrado_v4.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )

                st.subheader("Impresión de hoja de triage")
                opciones_impresion = filtrado.apply(
                    lambda row: f"{row['id']} - {row['folio']} - {row['nombre_paciente']}",
                    axis=1
                ).tolist()
                selected_print = st.selectbox("Selecciona registro para imprimir", opciones_impresion)
                selected_print_id = int(selected_print.split(" - ")[0])
                selected_record = filtrado[filtrado["id"] == selected_print_id].iloc[0]

                html_content = build_printable_html(selected_record)
                st.download_button(
                    "Descargar hoja de triage en HTML",
                    data=html_content.encode("utf-8"),
                    file_name=f"hoja_triage_{selected_record['folio']}.html",
                    mime="text/html",
                )
            else:
                st.info("No hay registros con esos filtros.")

    with tab5:
        if user["role"] != "Administrador":
            st.warning("Solo el Administrador puede gestionar usuarios.")
        else:
            st.title("👥 GESTIÓN DE USUARIOS")

            users_df = load_users_df()
            st.dataframe(users_df, use_container_width=True)

            st.subheader("Crear nuevo usuario")
            with st.form("create_user_form"):
                new_username = st.text_input("Nuevo usuario")
                new_full_name = st.text_input("Nombre completo")
                new_role = st.selectbox("Rol", ["Enfermería", "Médico", "Supervisor", "Administrador"])
                new_password = st.text_input("Contraseña", type="password")
                create_user_btn = st.form_submit_button("Crear usuario")

            if create_user_btn:
                try:
                    create_user(new_username, new_full_name, new_role, new_password)
                    st.success("Usuario creado correctamente")
                    st.rerun()
                except sqlite3.IntegrityError:
                    st.error("Ese usuario ya existe")
                except Exception as e:
                    st.error(f"Error al crear usuario: {e}")

            st.subheader("Editar o desactivar usuario")
            users_df = load_users_df()
            if not users_df.empty:
                user_options = users_df.apply(
                    lambda row: f"{row['id']} - {row['username']} - {row['full_name']}",
                    axis=1
                ).tolist()

                selected_user_label = st.selectbox("Selecciona usuario", user_options)
                selected_user_id = int(selected_user_label.split(" - ")[0])

                selected_row = users_df[users_df["id"] == selected_user_id].iloc[0]

                with st.form("edit_user_form"):
                    edit_full_name = st.text_input("Nombre completo", value=selected_row["full_name"])
                    edit_role = st.selectbox(
                        "Rol",
                        ["Enfermería", "Médico", "Supervisor", "Administrador"],
                        index=["Enfermería", "Médico", "Supervisor", "Administrador"].index(selected_row["role"])
                        if selected_row["role"] in ["Enfermería", "Médico", "Supervisor", "Administrador"] else 0
                    )
                    edit_active = st.selectbox(
                        "Estado",
                        ["Activo", "Inactivo"],
                        index=0 if int(selected_row["is_active"]) == 1 else 1
                    )

                    update_user_btn = st.form_submit_button("Guardar cambios")

                if update_user_btn:
                    update_user(
                        user_id=selected_user_id,
                        full_name=edit_full_name,
                        role=edit_role,
                        is_active=1 if edit_active == "Activo" else 0
                    )
                    st.success("Usuario actualizado correctamente")
                    st.rerun()