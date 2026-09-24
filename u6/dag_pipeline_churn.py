"""Pipeline batch U6: GCS → FastAPI → BigQuery → alertas de calidad y drift."""

from __future__ import annotations

import csv
import io
import json
import os
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import requests
from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator
from google.cloud import bigquery, storage


SCRIPTS_DIR = Path(__file__).resolve().parent / "u6-g03-scripts-20260924"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from monitoring import (  # noqa: E402
    DataQualityError,
    analyze_records,
    api_error_fields,
    build_payload,
    error_record,
    normalize_bank,
)


PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", "computacionnube20263")
GCS_BUCKET = os.getenv("U6_GCS_BUCKET", "u6-g03-data-20260924-computacionnube20263")
API_URL = os.getenv("U6_CHURN_API_URL", "").strip()
BASELINE_FILE = os.getenv("U6_BASELINE_FILE", "u6-g03-lotes-retencion-20260924.csv")
TRAINING_FILE = os.getenv("U6_TRAINING_FILE", "u6-g03-telco-churn-20260924.csv")
BQ_DATASET = "u6_g03_data_20260924"
BQ_TABLE_OK = "u6_g03_resultados_20260924"
BQ_TABLE_DLQ = "u6_g03_cuarentena_20260924"
BQ_TABLE_MONITOR = "u6_g03_monitoreo_lotes_20260924"
BQ_TABLE_DRIFT = "u6_g03_drift_lotes_20260924"
LEGACY_REJECTION_THRESHOLD = 0.30
USER = os.getenv("USER") or os.getenv("USERNAME", "visitante")


def _obtener_id_token() -> str:
    result = subprocess.run(
        ["gcloud", "auth", "print-identity-token"],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _filename(value: str) -> str:
    name = Path(value).name
    if name != value or not name.lower().endswith(".csv"):
        raise ValueError("El nombre de entrada debe ser un archivo CSV sin ruta")
    return name


def _read_gcs_csv(bucket: storage.Bucket, name: str) -> list[dict[str, str]]:
    text = bucket.blob(name).download_as_text(encoding="utf-8")
    return list(csv.DictReader(io.StringIO(text)))


def leer_csv_de_gcs(**context) -> None:
    """Confirma que el lote de entrada existe y contiene registros."""
    conf = context["dag_run"].conf or {}
    filename = _filename(str(conf.get("archivo", BASELINE_FILE)))
    client = storage.Client(project=PROJECT_ID)
    bucket = client.bucket(GCS_BUCKET)
    current_rows = _read_gcs_csv(bucket, f"input/{filename}")
    if not current_rows:
        raise ValueError(f"El archivo {filename} está vacío o no tiene filas de datos")

    ti = context["ti"]
    ti.xcom_push(key="archivo", value=filename)
    ti.xcom_push(key="total_registros", value=len(current_rows))
    print(f"Archivo {filename}: {len(current_rows)} registros.")


def enviar_a_api_y_clasificar(**context) -> None:
    """Valida filas, llama a la API y separa datos inválidos de fallos técnicos."""
    if not API_URL:
        raise ValueError("Configure U6_CHURN_API_URL con la URL /predict de Cloud Run")

    ti = context["ti"]
    filename = ti.xcom_pull(key="archivo", task_ids="leer_csv_de_gcs")
    gcs = storage.Client(project=PROJECT_ID).bucket(GCS_BUCKET)
    rows = _read_gcs_csv(gcs, f"input/{filename}")
    production_reference = _read_gcs_csv(gcs, f"reference/{BASELINE_FILE}")
    training_reference = _read_gcs_csv(gcs, f"reference/{TRAINING_FILE}")

    run_id = context["dag_run"].run_id
    processed_at = datetime.now(timezone.utc).isoformat()
    token = _obtener_id_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "X-Source": "batch_job",
        "X-Input-File": filename,
    }
    results: list[dict[str, object]] = []
    quarantine: list[dict[str, object]] = []
    local_errors: dict[int, DataQualityError] = {}
    for index, row in enumerate(rows):
        try:
            build_payload(row)
        except DataQualityError as exc:
            local_errors[index] = exc
            quarantine.append(
                error_record(
                    row,
                    code=exc.code,
                    message=str(exc),
                    fields=exc.fields,
                    filename=filename,
                    dag_run_id=run_id,
                    user=USER,
                    processed_at=processed_at,
                )
            )

    with requests.Session() as session:
        for index, row in enumerate(rows):
            if index in local_errors:
                continue
            payload = build_payload(row)
            try:
                response = session.post(API_URL, json=payload, headers=headers, timeout=30)
            except requests.RequestException as exc:
                raise RuntimeError(
                    f"Fallo técnico llamando a churn-api para {payload['customer_id']}: {exc}"
                ) from exc

            if response.status_code == 200:
                prediction = response.json()
                batch_date = str(row.get("fecha_lote") or datetime.now().date().isoformat())[:10]
                result = {
                    "customer_id": prediction["customer_id"],
                    "fecha_lote": batch_date,
                    "gender": payload["gender"],
                    "senior_citizen": payload["senior_citizen"],
                    "partner": payload["partner"],
                    "dependents": payload["dependents"],
                    "tenure": payload["tenure"],
                    "monthly_charges": payload["monthly_charges"],
                    "contract": payload["contract"],
                    "payment_method": payload["payment_method"],
                    "internet_service": payload["internet_service"],
                    "online_security": payload["online_security"],
                    "tech_support": payload["tech_support"],
                    "paperless_billing": payload["paperless_billing"],
                    "banco_pago_raw": str(row.get("BancoPago") or "").strip() or None,
                    "banco_pago_normalizado": normalize_bank(row.get("BancoPago")),
                    "customer_risk_score": prediction["customer_risk_score"],
                    "model_version": prediction["model_version"],
                    "predicted_at": prediction["predicted_at"],
                    "requested_by": prediction["requested_by"],
                    "source": prediction["source"],
                    "input_file": prediction["input_file"],
                    "dag_run_id": run_id,
                    "_insert_id": f"{run_id}:{filename}:{index}:ok",
                }
                results.append(result)
                continue

            if response.status_code == 422:
                try:
                    detail = response.json()
                except ValueError:
                    detail = {"detail": response.text[:2000]}
                fields = api_error_fields(detail)
                quarantine.append(
                    error_record(
                        row,
                        code="API_422",
                        message=json.dumps(detail, ensure_ascii=False, default=str),
                        fields=fields,
                        filename=filename,
                        dag_run_id=run_id,
                        user=USER,
                        processed_at=processed_at,
                        http_status=response.status_code,
                    )
                )
                continue

            raise RuntimeError(
                f"churn-api devolvió HTTP {response.status_code} para "
                f"{payload['customer_id']}: {response.text[:1000]}"
            )

    analysis = analyze_records(
        rows,
        training_reference,
        production_reference_rows=production_reference,
    )
    actual_by_date: dict[str, int] = {}
    for result in results:
        batch = str(result["fecha_lote"])
        actual_by_date[batch] = actual_by_date.get(batch, 0) + 1
    for summary in analysis["quality"]:
        total = int(summary["total"])
        accepted = actual_by_date.get(str(summary["fecha_lote"]), 0)
        rejected = total - accepted
        limit_count = int(summary["limite_rechazos"])
        summary["aceptados"] = accepted
        summary["rechazados"] = rejected
        summary["tasa_rechazo"] = rejected / total if total else 0.0
        summary["alerta_calidad"] = rejected > limit_count
        summary["alerta_umbral_actual"] = summary["tasa_rechazo"] > 0.30

    ti.xcom_push(key="resultados_ok", value=results)
    ti.xcom_push(key="resultados_dlq", value=quarantine)
    ti.xcom_push(key="monitoreo", value=analysis)
    print(
        f"Procesamiento terminado: {len(results)} aceptados, "
        f"{len(quarantine)} en cuarentena; drift calculado para "
        f"{len(analysis['drift'])} comparaciones."
    )


def _insert_rows(table: str, rows: list[dict[str, object]]) -> None:
    if not rows:
        return
    row_ids = [str(row.pop("_insert_id")) for row in rows]
    client = bigquery.Client(project=PROJECT_ID)
    table_ref = client.get_table(f"{PROJECT_ID}.{BQ_DATASET}.{table}")
    errors = client.insert_rows(table_ref, rows, row_ids=row_ids)
    if errors:
        raise RuntimeError(f"BigQuery rechazó filas para {table}: {errors}")


def guardar_en_bigquery(**context) -> None:
    """Guarda predicciones, cuarentena, métricas y drift antes de alertar."""
    ti = context["ti"]
    results = ti.xcom_pull(key="resultados_ok", task_ids="enviar_a_api_y_clasificar") or []
    quarantine = ti.xcom_pull(key="resultados_dlq", task_ids="enviar_a_api_y_clasificar") or []
    analysis = ti.xcom_pull(key="monitoreo", task_ids="enviar_a_api_y_clasificar") or {}
    filename = ti.xcom_pull(key="archivo", task_ids="leer_csv_de_gcs")
    run_id = context["dag_run"].run_id
    created_at = datetime.now(timezone.utc).isoformat()

    for index, row in enumerate(quarantine):
        row["_insert_id"] = f"{run_id}:{filename}:{index}:dlq"
    _insert_rows(BQ_TABLE_OK, results)
    _insert_rows(BQ_TABLE_DLQ, quarantine)

    drift_by_date: dict[str, list[dict[str, object]]] = defaultdict(list)
    for item in analysis.get("drift", []):
        drift_by_date[str(item["fecha_lote"])].append(item)
    monitor_rows = []
    for summary in analysis.get("quality", []):
        batch = str(summary["fecha_lote"])
        drift_alerts = [item for item in drift_by_date.get(batch, []) if item["alerta"]]
        monitor_rows.append(
            {
                "fecha_lote": batch,
                "archivo_origen": filename,
                "dag_run_id": run_id,
                "total_registros": summary["total"],
                "aceptados": summary["aceptados"],
                "rechazados": summary["rechazados"],
                "tasa_rechazo": summary["tasa_rechazo"],
                "limite_rechazos": summary["limite_rechazos"],
                "umbral_rechazo": summary["umbral_rechazo"],
                "umbral_mitad": summary["umbral_mitad"],
                "umbral_doble": summary["umbral_doble"],
                "umbral_actual": summary["umbral_actual"],
                "alerta_calidad": summary["alerta_calidad"],
                "alerta_umbral_actual": summary["alerta_umbral_actual"],
                "alerta_drift": bool(drift_alerts),
                "cantidad_alertas_drift": len(drift_alerts),
                "tasa_rechazo_referencia": (
                    analysis["production_reference_rejected"]
                    / analysis["production_reference_total"]
                    if analysis["production_reference_total"]
                    else 0.0
                ),
                "n_referencia_produccion": analysis["production_reference_n"],
                "fechas_referencia_produccion": analysis["production_reference_dates"],
                "n_referencia_entrenamiento": analysis["training_reference_n"],
                "banco_no_vacio": summary["banco_no_vacio"],
                "banco_completitud": summary["banco_completitud"],
                "banco_desconocido": summary["banco_desconocido"],
                "banco_categorias": summary["banco_categorias"],
                "errores_por_campo": summary["errores_por_campo"],
                "created_at": created_at,
                "_insert_id": f"{run_id}:{batch}:monitor",
            }
        )
    drift_rows = [
        {
            **item,
            "fecha_lote": str(item["fecha_lote"]),
            "dag_run_id": run_id,
            "created_at": created_at,
            "_insert_id": (
                f"{run_id}:{item['fecha_lote']}:{item['referencia']}:{item['variable']}"
            ),
        }
        for item in analysis.get("drift", [])
    ]
    _insert_rows(BQ_TABLE_MONITOR, monitor_rows)
    _insert_rows(BQ_TABLE_DRIFT, drift_rows)
    print(
        f"BigQuery actualizado: {len(results)} resultados, {len(quarantine)} cuarentenas, "
        f"{len(monitor_rows)} lotes y {len(drift_rows)} métricas PSI."
    )


def verificar_drift(**context) -> None:
    """Falla tras guardar evidencia si un lote supera calidad o drift calibrados."""
    ti = context["ti"]
    analysis = ti.xcom_pull(key="monitoreo", task_ids="enviar_a_api_y_clasificar") or {}
    quality_alerts = [
        item for item in analysis.get("quality", []) if item["alerta_calidad"]
    ]
    drift_alerts = [item for item in analysis.get("drift", []) if item["alerta"]]
    for item in analysis.get("quality", []):
        print(
            f"{item['fecha_lote']}: {item['aceptados']}/{item['total']} aceptados, "
            f"rechazo={item['tasa_rechazo']:.1%}, umbral_calibrado="
            f"{item['umbral_rechazo']:.1%}, umbral_anterior=30%, "
            f"mitad={item['umbral_mitad']:.1%}, doble={item['umbral_doble']:.1%}; "
            f"banco_completo={item['banco_completitud']:.1%}."
        )
    if quality_alerts or drift_alerts:
        quality_dates = sorted({str(item["fecha_lote"]) for item in quality_alerts})
        drift_summary = Counter(
            f"{item['fecha_lote']}:{item['referencia']}"
            for item in drift_alerts
        )
        raise RuntimeError(
            "ALERTA DE MONITOREO. Evidencia guardada en BigQuery. "
            f"Lotes con calidad sobre límite: {quality_dates or 'ninguno'}. "
            f"Comparaciones PSI fuera del límite bootstrap: {dict(drift_summary)}."
        )
    print("Estado: sin alertas sobre los límites calibrados.")


with DAG(
    dag_id="pipeline_mlops_churn",
    default_args={"owner": "u6-g03", "retries": 0},
    description="Pipeline U6: GCS → churn-api → BigQuery con cuarentena y monitoreo PSI",
    schedule=None,
    start_date=datetime(2026, 9, 1),
    catchup=False,
    tags=["u6", "g03", "retencion", "monitoreo"],
) as dag:
    leer = PythonOperator(task_id="leer_csv_de_gcs", python_callable=leer_csv_de_gcs)
    procesar = PythonOperator(
        task_id="enviar_a_api_y_clasificar", python_callable=enviar_a_api_y_clasificar
    )
    guardar = PythonOperator(task_id="guardar_en_bigquery", python_callable=guardar_en_bigquery)
    alerta = PythonOperator(task_id="verificar_drift", python_callable=verificar_drift)
    leer >> procesar >> guardar >> alerta
