"""Consola de sustentación U6 y predicción individual para Grupo 3."""

from __future__ import annotations

import csv
import io
import json
import os
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path
from statistics import median
from typing import Any

import requests
import streamlit as st


SCRIPTS_DIR = Path(
    os.getenv(
        "U6_MONITORING_DIR",
        str(Path(__file__).resolve().parent / "u6-g03-scripts-20260924"),
    )
)

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from monitoring import DataQualityError, analyze_records, build_payload  # noqa: E402
try:
    from delivery import legacy_threshold_scenarios, summarize_delivery  # noqa: E402
except ModuleNotFoundError as exc:
    if exc.name != "delivery":
        raise

    # Cloud Shell admite subir solo este .py: allí monitoring.py ya forma parte
    # del DAG y los CSV de referencia se recuperan del bucket del Grupo 3.
    def legacy_threshold_scenarios(
        quality: list[dict[str, Any]], original: float = 0.30
    ) -> list[dict[str, Any]]:
        if not 0 < original <= 0.5:
            raise ValueError("El umbral anterior debe estar en (0, 0.5].")
        scenarios = []
        for label, threshold in (
            ("Mitad del anterior", original / 2),
            ("Anterior", original),
            ("Doble del anterior", original * 2),
        ):
            dates = sorted(
                str(item["fecha_lote"])
                for item in quality
                if float(item["tasa_rechazo"]) > threshold
            )
            scenarios.append(
                {
                    "label": label,
                    "threshold": threshold,
                    "alert_dates": dates,
                    "alert_count": len(dates),
                }
            )
        return scenarios

    def _accepted_numeric_profile(
        records: list[dict[str, Any]],
    ) -> dict[str, float | int] | None:
        payloads = []
        for record in records:
            try:
                payloads.append(build_payload(record))
            except DataQualityError:
                continue
        if not payloads:
            return None
        return {
            "n": len(payloads),
            "tenure_median": float(median(item["tenure"] for item in payloads)),
            "monthly_charges_median": float(
                median(item["monthly_charges"] for item in payloads)
            ),
        }

    def summarize_delivery(
        report: dict[str, Any],
        rows: list[dict[str, Any]],
        *,
        production_reference_rows: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        quality = sorted(report.get("quality", []), key=lambda item: str(item["fecha_lote"]))
        drift = report.get("drift", [])
        field_counts: Counter[str] = Counter()
        for item in quality:
            field_counts.update(item.get("errores_por_campo", {}))

        invalid_payment_values: Counter[str] = Counter()
        for row in rows:
            try:
                build_payload(row)
            except DataQualityError as error:
                if "PaymentMethod" in error.fields:
                    raw = str(row.get("PaymentMethod") or "").strip() or "(vacío)"
                    invalid_payment_values[raw] += 1

        bank_dates = [
            str(item["fecha_lote"])
            for item in quality
            if int(item.get("banco_no_vacio", 0)) > 0
        ]
        first_bank_date = min(bank_dates) if bank_dates else None
        post_bank = [
            item for item in quality
            if first_bank_date and str(item["fecha_lote"]) >= first_bank_date
        ]
        bank_post_total = sum(int(item["total"]) for item in post_bank)
        bank_post_filled = sum(int(item.get("banco_no_vacio", 0)) for item in post_bank)

        production_drift = sorted(
            (item for item in drift if item.get("referencia") == "primeras_semanas_produccion"),
            key=lambda item: str(item["fecha_lote"]),
        )
        first_production_alert: dict[str, str] = {}
        latest_production_psi: dict[str, dict[str, Any]] = {}
        for item in production_drift:
            variable = str(item["variable"])
            date = str(item["fecha_lote"])
            if item.get("alerta") and variable not in first_production_alert:
                first_production_alert[variable] = date
            latest_production_psi[variable] = {
                "fecha_lote": date,
                "psi": float(item["psi"]),
                "umbral_psi": float(item["umbral_psi"]),
                "alerta": bool(item["alerta"]),
            }

        first_date = str(quality[0]["fecha_lote"]) if quality else None
        latest_date = str(quality[-1]["fecha_lote"]) if quality else None
        baseline_dates = set(str(date) for date in report.get("production_reference_dates", []))
        reference_rows = production_reference_rows if production_reference_rows is not None else rows
        baseline_profile = _accepted_numeric_profile(
            [row for row in reference_rows if str(row.get("fecha_lote")) in baseline_dates]
        )
        latest_profile = _accepted_numeric_profile(
            [row for row in rows if str(row.get("fecha_lote")) == latest_date]
        )
        training_alerts_on_first_date = sum(
            bool(item.get("alerta"))
            for item in drift
            if item.get("referencia") == "entrenamiento_telco_churn"
            and str(item.get("fecha_lote")) == first_date
        )

        return {
            "total": sum(int(item["total"]) for item in quality),
            "accepted": sum(int(item["aceptados"]) for item in quality),
            "rejected": sum(int(item["rechazados"]) for item in quality),
            "quality_alert_dates": [
                str(item["fecha_lote"]) for item in quality if item.get("alerta_calidad")
            ],
            "quarantine_fields": dict(sorted(field_counts.items())),
            "quarantine_by_date": {
                str(item["fecha_lote"]): dict(sorted(item.get("errores_por_campo", {}).items()))
                for item in quality
            },
            "invalid_payment_values": dict(sorted(invalid_payment_values.items())),
            "first_bank_date": first_bank_date,
            "bank_post_total": bank_post_total,
            "bank_post_filled": bank_post_filled,
            "bank_unknown": sum(int(item.get("banco_desconocido", 0)) for item in post_bank),
            "bank_coverage": bank_post_filled / bank_post_total if bank_post_total else 0.0,
            "first_production_alert": first_production_alert,
            "latest_production_psi": latest_production_psi,
            "baseline_profile": baseline_profile,
            "latest_profile": latest_profile,
            "training_alerts_on_first_date": training_alerts_on_first_date,
            "legacy_threshold_scenarios": legacy_threshold_scenarios(quality),
        }


API_URL = os.getenv("U6_CHURN_API_URL", "").strip()
DEFAULT_DATA = Path(__file__).with_name("u6-g03-lotes-retencion-20260924.csv")
TRAINING_DATA = Path(__file__).resolve().parent.parent / "telco_churn.csv"
TRAINING_DATA_U6 = Path(__file__).with_name("u6-g03-telco-churn-20260924.csv")
TEAM_MEMBERS = [
    "Ricardo Chamorro Martinez",
    "Oscar Stiven Muñoz Ramirez",
    "Juan Camilo Muñoz Barco",
    "Sebastian Erazo Ochoa",
]


def get_identity_token() -> str:
    executable = shutil.which("gcloud") or shutil.which("gcloud.cmd")
    if executable is None and os.name == "nt":
        candidate = Path(
            r"C:\Program Files (x86)\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd"
        )
        executable = str(candidate) if candidate.exists() else None
    executable = executable or "gcloud"
    if os.name == "nt" and executable.lower().endswith(".cmd"):
        command = f'"{executable}" auth print-identity-token'
        return subprocess.check_output(command, shell=True, text=True).strip()
    return subprocess.check_output(
        [executable, "auth", "print-identity-token"], text=True
    ).strip()


def predict(payload: dict) -> tuple[int, dict]:
    if not API_URL:
        return 0, {"detail": "Configure la variable U6_CHURN_API_URL con la URL /predict."}
    headers = {
        "Authorization": f"Bearer {get_identity_token()}",
        "Content-Type": "application/json",
    }
    response = requests.post(API_URL, json=payload, headers=headers, timeout=30)
    try:
        body = response.json()
    except ValueError:
        body = {"detail": response.text[:2000]}
    return response.status_code, body


@st.cache_data(show_spinner=False)
def parse_csv(csv_bytes: bytes) -> list[dict[str, str]]:
    content = csv_bytes.decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(content)))


@st.cache_data(show_spinner="Calculando límites calibrados y PSI por lote…")
def analyze_cached(
    csv_bytes: bytes,
    training_bytes: bytes | None,
    production_reference_bytes: bytes,
) -> dict:
    rows = parse_csv(csv_bytes)
    training_rows = parse_csv(training_bytes) if training_bytes else []
    return analyze_records(
        rows,
        training_rows,
        production_reference_rows=parse_csv(production_reference_bytes),
    )


def default_csv_bytes() -> bytes | None:
    if DEFAULT_DATA.exists():
        return DEFAULT_DATA.read_bytes()
    return None


def training_csv_bytes() -> bytes | None:
    if TRAINING_DATA_U6.exists():
        return TRAINING_DATA_U6.read_bytes()
    if TRAINING_DATA.exists():
        return TRAINING_DATA.read_bytes()
    return None


def render_quality(report: dict) -> None:
    quality = report["quality"]
    if not quality:
        st.info("El archivo no contiene lotes para resumir.")
        return
    st.caption(
        "El límite de rechazo usa una predictiva Beta-binomial al 95%, calibrada "
        f"con las semanas {', '.join(report['production_reference_dates'])}. "
        "La referencia permanece fija aunque se cargue otro CSV."
    )
    st.dataframe(
        [
            {
                "Fecha": item["fecha_lote"],
                "Registros": item["total"],
                "Aceptados": item["aceptados"],
                "En cuarentena": item["rechazados"],
                "Rechazo": f"{item['tasa_rechazo']:.1%}",
                "Umbral calibrado": f"{item['umbral_rechazo']:.1%}",
                "Umbral previo 30%": "Alerta" if item["alerta_umbral_actual"] else "No alerta",
                "Estado calibrado": "Alerta" if item["alerta_calidad"] else "En límite",
            }
            for item in quality
        ],
        width="stretch",
        hide_index=True,
    )
    st.line_chart(
        {
            "Fecha": [item["fecha_lote"] for item in quality],
            "Rechazo (%)": [100 * item["tasa_rechazo"] for item in quality],
            "Umbral calibrado (%)": [100 * item["umbral_rechazo"] for item in quality],
            "Umbral previo (30%)": [30.0 for _ in quality],
        },
        x="Fecha",
        y=["Rechazo (%)", "Umbral calibrado (%)", "Umbral previo (30%)"],
    )
    latest = quality[-1]
    columns = st.columns(4)
    columns[0].metric("Último lote", latest["fecha_lote"])
    columns[1].metric("Registros", latest["total"])
    columns[2].metric("Rechazo", f"{latest['tasa_rechazo']:.1%}")
    columns[3].metric("Banco informado", f"{latest['banco_completitud']:.1%}")
    st.subheader("¿Qué habría pasado con el umbral anterior?")
    st.caption(
        "El laboratorio usaba 30% para detenerse. Se compara ese valor con "
        "su mitad (15%) y su doble (60%); ninguno sustituye al límite calibrado."
    )
    st.dataframe(
        [
            {
                "Escenario": item["label"],
                "Umbral": f"{item['threshold']:.0%}",
                "Semanas con alerta": item["alert_count"],
                "Fechas detectadas": ", ".join(item["alert_dates"]) or "Ninguna",
            }
            for item in legacy_threshold_scenarios(quality)
        ],
        width="stretch",
        hide_index=True,
    )


def render_bank(report: dict, summary: dict) -> None:
    quality = report["quality"]
    st.subheader("Campo BancoPago")
    st.caption(
        "Se normalizan variantes conocidas para monitoreo. El banco no alimenta "
        "el modelo ni se imputa. Categorías desconocidas quedan identificadas."
    )
    if summary["first_bank_date"]:
        st.write(
            f"La captura empieza el {summary['first_bank_date']}. Desde entonces, "
            f"el campo viene informado en {summary['bank_post_filled']} de "
            f"{summary['bank_post_total']} filas "
            f"({summary['bank_coverage']:.1%}); "
            f"{summary['bank_unknown']} valores quedan como desconocidos."
        )
    else:
        st.info("El archivo seleccionado no contiene valores de BancoPago.")
    st.dataframe(
        [
            {
                "Fecha": item["fecha_lote"],
                "Completitud": f"{item['banco_completitud']:.1%}",
                "Desconocidos": item["banco_desconocido"],
                "Categorías normalizadas": json.dumps(
                    item["banco_categorias"], ensure_ascii=False
                ),
            }
            for item in quality
        ],
        width="stretch",
        hide_index=True,
    )
    st.info(
        "Decisión: conservar valor original y normalizado para análisis operativo; "
        "no imputar semanas anteriores ni incorporar BancoPago al modelo actual. "
        "Pedir al CRM el catálogo de códigos desconocidos y vigilar su cobertura."
    )


def render_quarantine(rows: list[dict[str, str]], summary: dict) -> None:
    rejected = []
    counts: dict[str, int] = {}
    for row in rows:
        try:
            build_payload(row)
        except DataQualityError as exc:
            for field in exc.fields:
                counts[field] = counts.get(field, 0) + 1
            rejected.append(
                {
                    "Fecha": row.get("fecha_lote", "Sin fecha"),
                    "Cliente": row.get("customerID", "Sin ID"),
                    "Campos": ", ".join(exc.fields),
                    "Detalle": str(exc),
                    "Registro original": json.dumps(row, ensure_ascii=False),
                }
            )
    if counts:
        st.bar_chart(counts)
        st.dataframe(
            [{"Campo": field, "Errores": count} for field, count in sorted(counts.items())],
            width="stretch",
            hide_index=True,
        )
        st.subheader("Evolución de causas por lote")
        st.caption("Se cuentan campos inválidos; una misma fila puede aparecer en varios campos.")
        st.dataframe(
            [
                {"Fecha": date, **{field: field_counts.get(field, 0) for field in sorted(counts)}}
                for date, field_counts in summary["quarantine_by_date"].items()
            ],
            width="stretch",
            hide_index=True,
        )
    if rejected:
        st.dataframe(rejected, width="stretch", hide_index=True)
    else:
        st.success("No hay registros en cuarentena en el archivo seleccionado.")
    with st.expander("Diseño de la cuarentena"):
        st.write(
            "BigQuery conserva el JSON original y agrega `codigo_error`, `campos_error`, "
            "`http_status`, lote, archivo y `dag_run_id`. Así se pueden consultar causas "
            "sin depender de inspeccionar manualmente una cadena JSON."
        )


def render_drift(report: dict) -> None:
    drift = report["drift"]
    if not drift:
        st.info("No hay filas válidas suficientes para calcular PSI.")
        return
    production_alerts = sum(
        bool(item["alerta"])
        for item in drift
        if item["referencia"] == "primeras_semanas_produccion"
    )
    training_alerts = sum(
        bool(item["alerta"])
        for item in drift
        if item["referencia"] == "entrenamiento_telco_churn"
    )
    left, right = st.columns(2)
    left.metric("Alertas vs. primeras semanas", production_alerts)
    right.metric("Alertas vs. fuente U4 (proxy)", training_alerts)
    st.caption(
        "Cada límite PSI es el percentil 95 de una distribución bootstrap bajo la "
        "referencia y con el tamaño de muestra del lote. PSI compara distribución; "
        "no mide desempeño ni demuestra causalidad."
    )
    production = {
        (str(item["fecha_lote"]), str(item["variable"])): item
        for item in drift
        if item["referencia"] == "primeras_semanas_produccion"
        and item["variable"] in {"tenure", "MonthlyCharges"}
    }
    dates = sorted({date for date, _ in production})
    if dates:
        trend = {"Fecha": dates}
        for feature in ("tenure", "MonthlyCharges"):
            trend[f"PSI {feature}"] = [
                production[(date, feature)]["psi"] if (date, feature) in production else None
                for date in dates
            ]
            trend[f"Límite {feature}"] = [
                production[(date, feature)]["umbral_psi"]
                if (date, feature) in production else None
                for date in dates
            ]
        st.subheader("Cambio numérico frente a las primeras semanas")
        st.line_chart(trend, x="Fecha", y=[key for key in trend if key != "Fecha"])
    st.info(
        "Las alertas frente al CSV fuente de U4 pueden existir desde el primer lote; "
        "las alertas frente a producción indican un cambio posterior respecto a "
        "las primeras semanas. Las semanas usadas para construir la referencia "
        "no constituyen una validación independiente."
    )
    st.dataframe(
        [
            {
                "Fecha": item["fecha_lote"],
                "Variable": item["variable"],
                "Referencia": (
                    "Fuente U4 (proxy de entrenamiento)"
                    if item["referencia"] == "entrenamiento_telco_churn"
                    else "Primeras semanas de producción"
                ),
                "PSI": round(item["psi"], 4),
                "Umbral bootstrap": round(item["umbral_psi"], 4),
                "Registros referencia": item["n_referencia"],
                "Registros lote": item["n_lote"],
                "Alerta": "Sí" if item["alerta"] else "No",
            }
            for item in drift
        ],
        width="stretch",
        hide_index=True,
    )


def render_client_answer(report: dict, summary: dict, uploaded_file: bool) -> None:
    if uploaded_file:
        st.warning(
            "Esta respuesta se recalcula para el CSV cargado. Use el consolidado "
            "real de diez semanas para responder al cliente."
        )
    st.subheader("Qué pasó")
    total = summary["total"]
    rejected = summary["rejected"]
    if total:
        st.write(
            f"Se procesaron {total} registros; {summary['accepted']} cumplieron "
            f"el contrato y {rejected} quedaron en cuarentena ({rejected / total:.1%})."
        )
    alerts = [item for item in report["quality"] if item["alerta_calidad"]]
    if alerts:
        st.write(
            "El rechazo superó el límite calibrado en "
            + "; ".join(
                f"{item['fecha_lote']} ({item['rechazados']}/{item['total']}, "
                f"{item['tasa_rechazo']:.1%})"
                for item in alerts
            )
            + "."
        )
    fields = summary["quarantine_fields"]
    if fields:
        st.write(
            "Campos implicados en cuarentena: "
            + ", ".join(f"{field}: {count}" for field, count in fields.items())
            + ". Una fila puede tener más de un campo inválido."
        )
        if not uploaded_file:
            by_date = summary["quarantine_by_date"]
            early_counts: dict[str, int] = {}
            for date in report["production_reference_dates"]:
                for field, count in by_date.get(date, {}).items():
                    early_counts[field] = early_counts.get(field, 0) + count
            latest_date = report["quality"][-1]["fecha_lote"]
            latest_counts = by_date.get(latest_date, {})
            early_text = ", ".join(
                f"{field}: {count}" for field, count in sorted(early_counts.items())
            ) or "ninguno"
            latest_text = ", ".join(
                f"{field}: {count}" for field, count in sorted(latest_counts.items())
            ) or "ninguno"
            st.write(
                f"En las primeras semanas, los errores por campo fueron {early_text}; "
                f"en el último lote ({latest_date}) fueron {latest_text}."
            )
    payment_values = summary["invalid_payment_values"]
    if payment_values:
        st.write(
            "Valores de PaymentMethod fuera del contrato: "
            + ", ".join(f"{value} ({count})" for value, count in payment_values.items())
            + "."
        )
    baseline_profile = summary["baseline_profile"]
    latest_profile = summary["latest_profile"]
    if baseline_profile and latest_profile:
        baseline_dates = report["production_reference_dates"]
        latest_date = report["quality"][-1]["fecha_lote"]
        st.write(
            f"Entre la referencia de las primeras semanas "
            f"({baseline_dates[0]} a {baseline_dates[-1]}, "
            f"{baseline_profile['n']} registros aceptados) y el lote del "
            f"{latest_date} ({latest_profile['n']} aceptados), la mediana de "
            f"antigüedad pasó de {baseline_profile['tenure_median']:.1f} a "
            f"{latest_profile['tenure_median']:.1f} meses y la de cargo mensual "
            f"de {baseline_profile['monthly_charges_median']:.2f} a "
            f"{latest_profile['monthly_charges_median']:.2f}."
        )
    first = summary["first_production_alert"]
    latest = summary["latest_production_psi"]
    for feature in ("tenure", "MonthlyCharges"):
        if feature in first and feature in latest:
            item = latest[feature]
            st.write(
                f"{feature} supera por primera vez su límite PSI frente a "
                f"producción el {first[feature]}; en el último lote "
                f"({item['fecha_lote']}) registra PSI {item['psi']:.3f} "
                f"frente a {item['umbral_psi']:.3f}."
            )
    if summary["training_alerts_on_first_date"]:
        st.caption(
            "La comparación con el CSV fuente de U4 (proxy de entrenamiento) ya da "
            "alertas en la primera semana; "
            "no debe confundirse ese desajuste inicial con el cambio posterior "
            "frente a producción."
        )

    st.subheader("Qué podría significar")
    st.write(
        "Hipótesis por comprobar: el CRM empezó a seleccionar clientes más antiguos "
        "y de mayor cargo mensual, cambió su catálogo de medios de pago, o ambas cosas. "
        "La coincidencia temporal no demuestra cuál de estos mecanismos explica el "
        "resultado de las campañas."
    )
    st.write(
        "Pedir al cliente las fechas de cambios del CRM y del catálogo de pagos, "
        "la regla de selección de clientes por semana, y por cliente: acción de campaña, "
        "fecha de contacto, resultado de retención y etiqueta posterior de churn."
    )

    st.subheader("Qué recomendamos")
    st.write(
        "Mientras se verifican esos datos, mantener el scoring únicamente para "
        "registros aceptados que cumplen el contrato, con monitoreo y revisión humana "
        "de las alertas. Conservar las filas rechazadas para corregirlas; no forzar "
        "medios nuevos a una categoría antigua. Confirmar con negocio si antigüedades "
        "superiores a 100 meses son válidas antes de cambiar ese límite."
    )
    st.write(
        "Evaluar un reentrenamiento solo cuando existan datos recientes etiquetados "
        "y representativos, y comparar desempeño, calibración y costo de negocio "
        "contra el modelo actual antes de desplegarlo."
    )
    st.warning(
        "Estos lotes no incluyen churn observado ni resultados de campañas: no se "
        "puede afirmar aún que el modelo perdió precisión o causó el deterioro."
    )


def render_prediction() -> None:
    st.caption(
        "Predicción individual con el mismo contrato que consume Airflow. "
        "La puntuación es riesgo estimado, no churn observado."
    )
    with st.form("prediction_form"):
        left, right = st.columns(2)
        with left:
            customer_id = st.text_input("ID del cliente", "U6-G03-9001")
            gender = st.selectbox("Género", ["Female", "Male"])
            senior_citizen = st.selectbox("Adulto mayor", [False, True], format_func=lambda x: "Sí" if x else "No")
            partner = st.selectbox("Tiene pareja", [False, True], format_func=lambda x: "Sí" if x else "No")
            dependents = st.selectbox("Tiene dependientes", [False, True], format_func=lambda x: "Sí" if x else "No")
            tenure = st.slider("Antigüedad (meses)", 0, 100, 12)
            monthly_charges = st.number_input("Cargo mensual", min_value=0.01, max_value=200.0, value=70.5)
        with right:
            contract = st.selectbox("Contrato", ["Month-to-month", "One year", "Two year"])
            payment_method = st.selectbox(
                "Método de pago",
                [
                    "Electronic check",
                    "Mailed check",
                    "Bank transfer (automatic)",
                    "Credit card (automatic)",
                ],
            )
            internet_service = st.selectbox("Servicio de internet", ["DSL", "Fiber optic", "No"])
            online_security = st.selectbox("Seguridad en línea", ["Yes", "No", "No internet service"])
            tech_support = st.selectbox("Soporte técnico", ["Yes", "No", "No internet service"])
            paperless_billing = st.selectbox("Factura electrónica", [False, True], format_func=lambda x: "Sí" if x else "No")
        submitted = st.form_submit_button("Predecir", type="primary")

    if not submitted:
        return
    payload = {
        "customer_id": customer_id.strip(),
        "gender": gender,
        "senior_citizen": senior_citizen,
        "partner": partner,
        "dependents": dependents,
        "tenure": tenure,
        "monthly_charges": monthly_charges,
        "contract": contract,
        "payment_method": payment_method,
        "internet_service": internet_service,
        "online_security": online_security,
        "tech_support": tech_support,
        "paperless_billing": paperless_billing,
    }
    try:
        status, body = predict(payload)
    except (OSError, subprocess.SubprocessError, requests.RequestException) as exc:
        st.error(f"No fue posible llamar a churn-api: {exc}")
        return
    if status == 200:
        st.metric("Riesgo estimado", f"{body['customer_risk_score']:.1%}")
        st.write(
            "Resultado del umbral del modelo:",
            "Churn probable" if body["predicted_churn"] else "Churn no probable",
        )
        st.json(body)
    elif status == 422:
        st.error("La API rechazó el registro por contrato.")
        st.json(body)
    elif status == 403:
        st.error("Cloud Run rechazó el token de identidad.")
        st.json(body)
    elif status == 0:
        st.info(body["detail"])
    else:
        st.error(f"La API devolvió HTTP {status}.")
        st.json(body)


st.set_page_config(page_title="Monitoreo de retención U6", page_icon="📊", layout="wide")
st.title("Monitoreo de retención y churn")
st.caption("Unidad 6 · Grupo 3 · Proyecto computacionnube20263")
st.caption("Integrantes registrados: " + ", ".join(TEAM_MEMBERS))
st.caption(
    "Análisis reproducible del CSV; el resultado operativo de cada corrida "
    "queda en BigQuery (u6_g03_data_20260924). La predicción individual usa "
    "la API privada de Cloud Run. La referencia de U4 usa el CSV fuente "
    "completo, no el subconjunto exacto X_train."
)

uploaded = st.file_uploader("Archivo de lotes CSV", type=["csv"])
reference_bytes = default_csv_bytes()
if reference_bytes is None:
    st.error(
        "Falta u6-g03-lotes-retencion-20260924.csv junto a la aplicación. "
        "Es la referencia fija necesaria para calibrar los límites."
    )
    st.stop()
csv_bytes = uploaded.getvalue() if uploaded else reference_bytes

rows = parse_csv(csv_bytes)
training_bytes = training_csv_bytes()
if training_bytes is None:
    st.error(
        "Falta u6-g03-telco-churn-20260924.csv: sin él no se puede mostrar "
        "la segunda referencia exigida para drift."
    )
    st.stop()
report = analyze_cached(csv_bytes, training_bytes, reference_bytes)
summary = summarize_delivery(report, rows, production_reference_rows=parse_csv(reference_bytes))

quality_tab, quarantine_tab, drift_tab, bank_tab, answer_tab, prediction_tab = st.tabs(
    ["Calidad y umbral", "Cuarentena", "Drift", "BancoPago", "Respuesta al cliente", "Predicción individual"]
)
with quality_tab:
    render_quality(report)
with quarantine_tab:
    render_quarantine(rows, summary)
with drift_tab:
    render_drift(report)
with bank_tab:
    render_bank(report, summary)
with answer_tab:
    render_client_answer(report, summary, uploaded is not None)
with prediction_tab:
    render_prediction()
