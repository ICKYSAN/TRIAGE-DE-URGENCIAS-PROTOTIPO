import json
import os
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any, Dict, List

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

st.set_page_config(
    page_title="TRIAGE IA APP",
    page_icon="🏥",
    layout="wide",
)

st.markdown(
    """
    <style>
    .orange-box {background-color: #fff7ed; border-left: 8px solid #f97316; padding: 1rem; border-radius: 0.8rem;}
    .yellow-box {background-color: #fefce8; border-left: 8px solid #eab308; padding: 1rem; border-radius: 0.8rem;}
    .green-box {background-color: #f0fdf4; border-left: 8px solid #22c55e; padding: 1rem; border-radius: 0.8rem;}
    </style>
    """,
    unsafe_allow_html=True,
)

CSV_FILE = "pacientes_triage.csv"


@dataclass
class TriageInput:
    folio: str
    nombre_paciente: str
    edad: int
    sexo: str
    motivo_consulta: str
    usuario_captura: str
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

    # PRIORIDAD NARANJA
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

    # PRIORIDAD AMARILLO
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

    # PRIORIDAD VERDE
    motivos.append("Paciente estable, sin datos de alarma mayores")
    return resultado("VERDE", "Atención diferida", motivos, alertas, data)


def export_filename(folio: str) -> str:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"triage_{folio}_{stamp}.json"


def guardar_en_csv(data: TriageInput, res: Dict[str, Any]) -> None:
    fila = {
        "fecha_registro": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "folio": data.folio,
        "nombre_paciente": data.nombre_paciente,
        "edad": data.edad,
        "sexo": data.sexo,
        "motivo_consulta": data.motivo_consulta,
        "usuario_captura": data.usuario_captura,
        "fecha_hora_ingreso": data.fecha_hora_ingreso,
        "frecuencia_cardiaca": data.frecuencia_cardiaca,
        "frecuencia_respiratoria": data.frecuencia_respiratoria,
        "presion_sistolica": data.presion_sistolica,
        "presion_diastolica": data.presion_diastolica,
        "temperatura": data.temperatura,
        "saturacion_oxigeno": data.saturacion_oxigeno,
        "glucosa_capilar": data.glucosa_capilar,
        "dolor_eva": data.dolor_eva,
        "estado_conciencia": data.estado_conciencia,
        "semaforo": res["semaforo"],
        "accion_sugerida": res["accion_sugerida"],
        "motivos": " | ".join(res["motivos"]),
        "alertas": " | ".join(res["alertas"]) if res["alertas"] else "",
    }

    df_nuevo = pd.DataFrame([fila])

    if os.path.exists(CSV_FILE):
        df_existente = pd.read_csv(CSV_FILE)
        df_final = pd.concat([df_existente, df_nuevo], ignore_index=True)
    else:
        df_final = df_nuevo

    df_final.to_csv(CSV_FILE, index=False)


def cargar_historial() -> pd.DataFrame:
    if os.path.exists(CSV_FILE):
        return pd.read_csv(CSV_FILE)
    return pd.DataFrame()


tab1, tab2 = st.tabs(["Triage", "Dashboard"])


with tab1:
    st.title("🏥 TRIAGE IA APP")
    st.write("Clasificación clínica de urgencias para adultos: NARANJA, AMARILLO y VERDE.")

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
            usuario_captura = st.text_input("Personal que realiza el triage")

        with col3:
            fecha_hora_ingreso = st.text_input(
                "Fecha y hora de ingreso",
                value=datetime.now().strftime("%Y-%m-%d %H:%M")
            )

        st.subheader("2. Signos vitales")
        c1, c2, c3, c4 = st.columns(4)

        with c1:
            frecuencia_cardiaca = st.number_input("Frecuencia cardiaca", 0, 300, 80)
            presion_sistolica = st.number_input("TA sistólica", 0, 300, 120)

        with c2:
            frecuencia_respiratoria = st.number_input("Frecuencia respiratoria", 0, 80, 18)
            presion_diastolica = st.number_input("TA diastólica", 0, 200, 80)

        with c3:
            temperatura = st.number_input("Temperatura °C", 30.0, 45.0, 36.5, step=0.1)
            saturacion_oxigeno = st.number_input("Saturación de oxígeno %", 0, 100, 98)

        with c4:
            glucosa_capilar = st.number_input("Glucosa capilar mg/dL", 0, 1000, 100)
            dolor_eva = st.slider("Dolor EVA", 0, 10, 0)
            estado_conciencia = st.selectbox(
                "Estado de conciencia",
                ["alerta", "somnoliento", "confuso", "inconsciente"]
            )

        st.subheader("3. Preguntas de alarma")
        p1, p2, p3, p4 = st.columns(4)

        with p1:
            dolor_toracico = st.checkbox("Dolor torácico")
            dificultad_respiratoria = st.checkbox("Dificultad respiratoria")
            fiebre = st.checkbox("Fiebre")
            sangrado_activo = st.checkbox("Sangrado activo")

        with p2:
            convulsiones = st.checkbox("Convulsiones")
            alteracion_mental = st.checkbox("Alteración mental")
            debilidad_unilateral = st.checkbox("Debilidad unilateral")
            alteracion_habla = st.checkbox("Alteración del habla")

        with p3:
            asimetria_facial = st.checkbox("Asimetría facial")
            inicio_subito = st.checkbox("Inicio súbito")
            sincope = st.checkbox("Síncope")
            palidez_diaforesis = st.checkbox("Palidez o diaforesis")

        with p4:
            trauma_reciente = st.checkbox("Trauma reciente")
            antecedente_hipertension = st.checkbox("Antecedente de hipertensión")
            antecedente_diabetes = st.checkbox("Antecedente de diabetes")
            puede_caminar = st.checkbox("Puede caminar por sí mismo", value=True)

        submitted = st.form_submit_button("Clasificar paciente")

    if submitted:
        data = TriageInput(
            folio=folio,
            nombre_paciente=nombre_paciente,
            edad=int(edad),
            sexo=sexo,
            motivo_consulta=motivo_consulta,
            usuario_captura=usuario_captura,
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
        guardar_en_csv(data, res)

        st.subheader("4. Resultado del triage")

        if res["semaforo"] == "NARANJA":
            st.markdown(
                f"""
                <div class="orange-box">
                    <h2>🟠 {res["semaforo"]}</h2>
                    <p><strong>Acción sugerida:</strong> {res["accion_sugerida"]}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
        elif res["semaforo"] == "AMARILLO":
            st.markdown(
                f"""
                <div class="yellow-box">
                    <h2>🟡 {res["semaforo"]}</h2>
                    <p><strong>Acción sugerida:</strong> {res["accion_sugerida"]}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f"""
                <div class="green-box">
                    <h2>🟢 {res["semaforo"]}</h2>
                    <p><strong>Acción sugerida:</strong> {res["accion_sugerida"]}</p>
                </div>
                """,
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

        st.markdown("**Aviso legal**")
        st.caption(res["aviso_legal"])

        with st.expander("Ver datos capturados"):
            st.json(res["datos_capturados"])

        json_bytes = json.dumps(res, ensure_ascii=False, indent=2).encode("utf-8")
        st.download_button(
            label="Descargar resultado en JSON",
            data=json_bytes,
            file_name=export_filename(folio if folio else "sin_folio"),
            mime="application/json",
        )

        st.success("Paciente guardado correctamente en el historial.")


with tab2:
    st.title("📊 Dashboard de triage")

    historial = cargar_historial()

    if historial.empty:
        st.warning("Aún no hay pacientes guardados.")
    else:
        historial["fecha_registro"] = pd.to_datetime(historial["fecha_registro"], errors="coerce")

        st.subheader("Filtros")

        f1, f2, f3, f4 = st.columns(4)

        with f1:
            fecha_inicio = st.date_input(
                "Fecha inicio",
                value=historial["fecha_registro"].min().date()
                if historial["fecha_registro"].notna().any()
                else datetime.now().date(),
            )

        with f2:
            fecha_fin = st.date_input(
                "Fecha fin",
                value=historial["fecha_registro"].max().date()
                if historial["fecha_registro"].notna().any()
                else datetime.now().date(),
            )

        with f3:
            lista_usuarios = ["Todos"] + sorted(
                [u for u in historial["usuario_captura"].dropna().astype(str).unique() if u.strip() != ""]
            )
            usuario_filtro = st.selectbox("Usuario capturista", lista_usuarios)

        with f4:
            lista_semaforos = ["Todos", "NARANJA", "AMARILLO", "VERDE"]
            semaforo_filtro = st.selectbox("Semáforo", lista_semaforos)

        historial_filtrado = historial.copy()

        historial_filtrado = historial_filtrado[
            (historial_filtrado["fecha_registro"].dt.date >= fecha_inicio) &
            (historial_filtrado["fecha_registro"].dt.date <= fecha_fin)
        ]

        if usuario_filtro != "Todos":
            historial_filtrado = historial_filtrado[
                historial_filtrado["usuario_captura"].astype(str) == usuario_filtro
            ]

        if semaforo_filtro != "Todos":
            historial_filtrado = historial_filtrado[
                historial_filtrado["semaforo"] == semaforo_filtro
            ]

        total = len(historial_filtrado)
        total_naranja = (historial_filtrado["semaforo"] == "NARANJA").sum()
        total_amarillo = (historial_filtrado["semaforo"] == "AMARILLO").sum()
        total_verde = (historial_filtrado["semaforo"] == "VERDE").sum()

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total pacientes", int(total))
        m2.metric("🟠 Naranja", int(total_naranja))
        m3.metric("🟡 Amarillo", int(total_amarillo))
        m4.metric("🟢 Verde", int(total_verde))

        st.subheader("Distribución por semáforo")
        if not historial_filtrado.empty:
            conteo = historial_filtrado["semaforo"].value_counts()
            st.bar_chart(conteo)
        else:
            st.info("No hay registros con esos filtros.")

        st.subheader("Historial filtrado")
        st.dataframe(historial_filtrado, use_container_width=True)

        csv_descarga = historial_filtrado.to_csv(index=False).encode("utf-8")
        st.download_button(
            "Descargar historial filtrado en CSV",
            data=csv_descarga,
            file_name="historial_filtrado_triage.csv",
            mime="text/csv",
        )