"""Validación de entrada y monitoreo explicable para Unidad 6, Grupo 3."""

from __future__ import annotations

import csv
import json
import math
import random
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Any, Iterable
import unicodedata


FEATURES = (
    "gender",
    "SeniorCitizen",
    "Partner",
    "Dependents",
    "tenure",
    "Contract",
    "PaymentMethod",
    "MonthlyCharges",
    "InternetService",
    "OnlineSecurity",
    "TechSupport",
    "PaperlessBilling",
)
NUMERIC_FEATURES = {"tenure", "MonthlyCharges"}
BASELINE_WEEKS = 4
BOOTSTRAP_ITERATIONS = 200

DOMAINS = {
    "gender": {"Female", "Male"},
    "Contract": {"Month-to-month", "One year", "Two year"},
    "PaymentMethod": {
        "Bank transfer (automatic)",
        "Credit card (automatic)",
        "Electronic check",
        "Mailed check",
    },
    "InternetService": {"DSL", "Fiber optic", "No"},
    "OnlineSecurity": {"Yes", "No", "No internet service"},
    "TechSupport": {"Yes", "No", "No internet service"},
}
BOOLEAN_FIELDS = {"Partner", "Dependents", "PaperlessBilling"}


class DataQualityError(ValueError):
    """Error de contrato local, con el campo que permite explicar el rechazo."""

    def __init__(
        self,
        field: str,
        message: str,
        code: str = "LOCAL_VALIDATION",
        fields: Iterable[str] | None = None,
    ) -> None:
        super().__init__(message)
        self.field = field
        self.code = code
        self.fields = sorted(set(fields or [field]))


def read_csv(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


def _required(record: dict[str, Any], name: str) -> str:
    value = record.get(name)
    if value is None or not str(value).strip():
        raise DataQualityError(name, f"Campo requerido vacío: {name}")
    return str(value).strip()


def _yes_no(record: dict[str, Any], name: str) -> bool:
    value = _required(record, name).casefold()
    if value == "yes":
        return True
    if value == "no":
        return False
    raise DataQualityError(name, f"Valor no permitido en {name}: {record.get(name)!r}")


def _enum(record: dict[str, Any], name: str) -> str:
    value = _required(record, name)
    if value not in DOMAINS[name]:
        raise DataQualityError(name, f"Valor fuera del contrato en {name}: {value!r}")
    return value


def build_payload(record: dict[str, Any]) -> dict[str, Any]:
    """Valida y transforma una fila CRM al esquema ClienteInput de FastAPI."""
    errors: list[DataQualityError] = []

    def checked(field: str, operation: Any, fallback: Any = None) -> Any:
        try:
            return operation()
        except DataQualityError as exc:
            errors.append(exc)
        except (TypeError, ValueError) as exc:
            errors.append(DataQualityError(field, str(exc)))
        return fallback

    customer_id = checked("customerID", lambda: _required(record, "customerID"), "")
    if customer_id and len(customer_id) > 64:
        errors.append(DataQualityError("customerID", "customerID supera 64 caracteres"))

    def senior_value() -> bool:
        raw = _required(record, "SeniorCitizen")
        if raw not in {"0", "1"}:
            raise DataQualityError("SeniorCitizen", f"Valor fuera de rango: {raw!r}")
        return raw == "1"

    def tenure_value() -> int:
        raw = _required(record, "tenure")
        try:
            value = int(raw)
        except (TypeError, ValueError) as exc:
            raise DataQualityError("tenure", f"No es un entero: {raw!r}") from exc
        if not 0 <= value <= 100:
            raise DataQualityError("tenure", f"Fuera del rango 0–100: {value}")
        return value

    def charges_value() -> float:
        raw = _required(record, "MonthlyCharges")
        try:
            value = float(raw)
        except (TypeError, ValueError) as exc:
            raise DataQualityError("MonthlyCharges", f"No es numérico: {raw!r}") from exc
        if not math.isfinite(value) or not 0 < value <= 200:
            raise DataQualityError("MonthlyCharges", f"Fuera del rango (0, 200]: {raw!r}")
        return value

    payload = {
        "customer_id": customer_id,
        "gender": checked("gender", lambda: _enum(record, "gender"), ""),
        "senior_citizen": checked("SeniorCitizen", senior_value, False),
        "partner": checked("Partner", lambda: _yes_no(record, "Partner"), False),
        "dependents": checked("Dependents", lambda: _yes_no(record, "Dependents"), False),
        "tenure": checked("tenure", tenure_value, 0),
        "monthly_charges": checked("MonthlyCharges", charges_value, 0.0),
        "contract": checked("Contract", lambda: _enum(record, "Contract"), ""),
        "payment_method": checked("PaymentMethod", lambda: _enum(record, "PaymentMethod"), ""),
        "internet_service": checked("InternetService", lambda: _enum(record, "InternetService"), ""),
        "online_security": checked("OnlineSecurity", lambda: _enum(record, "OnlineSecurity"), ""),
        "tech_support": checked("TechSupport", lambda: _enum(record, "TechSupport"), ""),
        "paperless_billing": checked(
            "PaperlessBilling", lambda: _yes_no(record, "PaperlessBilling"), False
        ),
    }
    if errors:
        fields = sorted({error.field for error in errors})
        details = "; ".join(str(error) for error in errors)
        raise DataQualityError(fields[0], details, fields=fields)
    return payload


def api_error_fields(detail: Any) -> list[str]:
    """Extrae campos de errores Pydantic 422 sin perder el detalle original."""
    fields: set[str] = set()
    if isinstance(detail, dict):
        detail = detail.get("detail", detail)
    if isinstance(detail, list):
        for item in detail:
            if not isinstance(item, dict):
                continue
            location = item.get("loc", ())
            for part in location:
                if part in {"body", "query", "path"}:
                    continue
                fields.add(str(part))
    return sorted(fields) or ["contrato"]


def error_record(
    raw: dict[str, Any],
    *,
    code: str,
    message: str,
    fields: Iterable[str],
    filename: str,
    dag_run_id: str,
    user: str,
    processed_at: str,
    http_status: int | None = None,
) -> dict[str, Any]:
    return {
        "customer_id": str(raw.get("customerID") or "") or None,
        "fecha_lote": _batch_date(raw),
        "datos_originales": json.dumps(raw, ensure_ascii=False, default=str),
        "codigo_error": code,
        "campos_error": json.dumps(sorted(set(fields)), ensure_ascii=False),
        "error_detalle": str(message)[:2000],
        "http_status": http_status,
        "archivo_origen": filename,
        "dag_run_id": dag_run_id,
        "usuario": user,
        "fecha_proceso": processed_at,
    }


def _batch_date(row: dict[str, Any]) -> str:
    raw_date = str(row.get("fecha_lote") or "").strip()
    if raw_date:
        try:
            return date.fromisoformat(raw_date[:10]).isoformat()
        except ValueError:
            pass
    return date.today().isoformat()


def beta_binomial_limit(
    sample_size: int,
    rejected: int,
    total: int,
    confidence: float = 0.95,
) -> int:
    """Límite predictivo superior Beta-binomial (prior uniforme Beta(1,1))."""
    if sample_size <= 0 or total <= 0:
        return 0
    alpha = 1.0 + rejected
    beta = 1.0 + max(0, total - rejected)
    base = math.lgamma(alpha + beta) - math.lgamma(alpha) - math.lgamma(beta)
    cumulative = 0.0
    for k in range(sample_size + 1):
        log_probability = (
            math.lgamma(sample_size + 1)
            - math.lgamma(k + 1)
            - math.lgamma(sample_size - k + 1)
            + math.lgamma(alpha + k)
            + math.lgamma(beta + sample_size - k)
            - math.lgamma(alpha + beta + sample_size)
            + base
        )
        cumulative += math.exp(log_probability)
        if cumulative >= confidence:
            return k
    return sample_size


def _normal_form(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(char for char in text if not unicodedata.combining(char)).strip().casefold()


def normalize_bank(value: Any) -> str | None:
    normalized = _normal_form(value)
    if not normalized:
        return None
    aliases = {
        "bancolombia": "Bancolombia",
        "bancolombia s.a.": "Bancolombia",
        "banco de bogota": "Banco de Bogotá",
        "bco bogota": "Banco de Bogotá",
        "bbva": "BBVA",
        "davivienda": "Davivienda",
        "scotiabank": "Scotiabank",
    }
    return aliases.get(normalized, "Desconocido")


def _value(row: dict[str, Any], feature: str) -> Any:
    source_name = {
        "senior_citizen": "SeniorCitizen",
        "partner": "Partner",
        "dependents": "Dependents",
        "paperless_billing": "PaperlessBilling",
        "monthly_charges": "MonthlyCharges",
    }.get(feature, feature)
    value = row.get(source_name)
    if feature == "tenure" or feature == "MonthlyCharges":
        try:
            number = float(value)
            return number if math.isfinite(number) else None
        except (TypeError, ValueError):
            return None
    if feature in {"SeniorCitizen", "senior_citizen"}:
        return "Yes" if str(value).strip() == "1" else "No"
    if feature in BOOLEAN_FIELDS or feature in {"Partner", "Dependents", "PaperlessBilling"}:
        return str(value).strip().title() if str(value or "").strip() else None
    text = str(value or "").strip()
    return text or None


def _numeric_edges(reference: list[float]) -> list[float]:
    ordered = sorted(reference)
    if len(ordered) < 2:
        return []
    edges = []
    for decile in range(1, 10):
        index = min(len(ordered) - 1, math.ceil(decile * len(ordered) / 10) - 1)
        edge = ordered[index]
        if not edges or edge > edges[-1]:
            edges.append(edge)
    return edges


def _bin(value: Any, feature: str, edges: list[float]) -> str:
    if feature in NUMERIC_FEATURES:
        number = float(value)
        index = 0
        while index < len(edges) and number > edges[index]:
            index += 1
        return f"bin_{index}"
    return str(value)


def _psi(reference: list[Any], current: list[Any], feature: str, edges: list[float]) -> float:
    if not reference or not current:
        return 0.0
    reference_bins = [_bin(value, feature, edges) for value in reference]
    current_bins = [_bin(value, feature, edges) for value in current]
    categories = sorted(set(reference_bins) | set(current_bins))
    smoothing = 0.5
    ref_counts = Counter(reference_bins)
    cur_counts = Counter(current_bins)
    ref_denominator = len(reference_bins) + smoothing * len(categories)
    cur_denominator = len(current_bins) + smoothing * len(categories)
    score = 0.0
    for category in categories:
        p = (ref_counts[category] + smoothing) / ref_denominator
        q = (cur_counts[category] + smoothing) / cur_denominator
        score += (q - p) * math.log(q / p)
    return score


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    values.sort()
    index = max(0, min(len(values) - 1, math.ceil(percentile * len(values)) - 1))
    return values[index]


def psi_with_bootstrap(
    reference_rows: list[dict[str, Any]],
    current_rows: list[dict[str, Any]],
    feature: str,
    *,
    iterations: int = BOOTSTRAP_ITERATIONS,
    seed: int = 42,
) -> dict[str, float | int | bool]:
    reference = [value for row in reference_rows if (value := _value(row, feature)) is not None]
    current = [value for row in current_rows if (value := _value(row, feature)) is not None]
    if not reference or not current:
        return {
            "psi": 0.0,
            "umbral_psi": 0.0,
            "alerta": False,
            "n_referencia": len(reference),
            "n_lote": len(current),
        }
    edges = _numeric_edges([float(value) for value in reference]) if feature in NUMERIC_FEATURES else []
    observed = _psi(reference, current, feature, edges)
    rng = random.Random(f"{seed}:{feature}:{len(current)}:{len(reference)}")
    distribution = [
        _psi(
            [rng.choice(reference) for _ in range(len(current))],
            [rng.choice(reference) for _ in range(len(current))],
            feature,
            edges,
        )
        for _ in range(iterations)
    ]
    threshold = _percentile(distribution, 0.95)
    return {
        "psi": observed,
        "umbral_psi": threshold,
        "alerta": observed > threshold,
        "n_referencia": len(reference),
        "n_lote": len(current),
    }


def analyze_records(
    rows: list[dict[str, Any]],
    training_rows: list[dict[str, Any]] | None = None,
    *,
    production_reference_rows: list[dict[str, Any]] | None = None,
    bootstrap_iterations: int = BOOTSTRAP_ITERATIONS,
) -> dict[str, Any]:
    """Resume calidad, cuarentena, BancoPago y drift contra dos referencias."""
    batches: dict[str, list[dict[str, Any]]] = defaultdict(list)
    accepted_by_batch: dict[str, list[dict[str, Any]]] = defaultdict(list)
    errors_by_batch: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        batch = _batch_date(row)
        batches[batch].append(row)
        try:
            build_payload(row)
            accepted_by_batch[batch].append(row)
        except DataQualityError as exc:
            for field in exc.fields:
                errors_by_batch[batch][field] += 1

    dates = sorted(batches)
    baseline_source = production_reference_rows if production_reference_rows is not None else rows
    baseline_batches: dict[str, list[dict[str, Any]]] = defaultdict(list)
    baseline_accepted: list[dict[str, Any]] = []
    baseline_rejected = 0
    for row in baseline_source:
        baseline_batches[_batch_date(row)].append(row)
    baseline_dates = sorted(baseline_batches)[:BASELINE_WEEKS]
    baseline_total = sum(len(baseline_batches[batch]) for batch in baseline_dates)
    for batch in baseline_dates:
        for row in baseline_batches[batch]:
            try:
                build_payload(row)
                baseline_accepted.append(row)
            except DataQualityError:
                baseline_rejected += 1
    production_reference = baseline_accepted

    quality = []
    drift = []
    for batch in dates:
        total = len(batches[batch])
        accepted = len(accepted_by_batch[batch])
        rejected = total - accepted
        limit_count = beta_binomial_limit(total, baseline_rejected, baseline_total)
        limit_rate = limit_count / total if total else 0.0
        batch_quality = {
            "fecha_lote": batch,
            "total": total,
            "aceptados": accepted,
            "rechazados": rejected,
            "tasa_rechazo": rejected / total if total else 0.0,
            "limite_rechazos": limit_count,
            "umbral_rechazo": limit_rate,
            "umbral_mitad": limit_rate / 2,
            "umbral_doble": min(1.0, limit_rate * 2),
            "umbral_actual": 0.30,
            "alerta_umbral_actual": rejected / total > 0.30 if total else False,
            "alerta_calidad": rejected > limit_count,
            "errores_por_campo": dict(errors_by_batch[batch]),
        }
        bank_values = [normalize_bank(row.get("BancoPago")) for row in batches[batch]]
        bank_filled = [value for value in bank_values if value is not None]
        batch_quality.update(
            {
                "banco_no_vacio": len(bank_filled),
                "banco_completitud": len(bank_filled) / total if total else 0.0,
                "banco_desconocido": sum(value == "Desconocido" for value in bank_filled),
                "banco_categorias": dict(Counter(bank_filled)),
            }
        )
        quality.append(batch_quality)

        current_rows = accepted_by_batch[batch]
        if production_reference and current_rows:
            for feature in FEATURES:
                result = psi_with_bootstrap(
                    production_reference,
                    current_rows,
                    feature,
                    iterations=bootstrap_iterations,
                )
                drift.append(
                    {
                        "fecha_lote": batch,
                        "variable": feature,
                        "referencia": "primeras_semanas_produccion",
                        **result,
                    }
                )
        if training_rows and current_rows:
            for feature in FEATURES:
                result = psi_with_bootstrap(
                    training_rows,
                    current_rows,
                    feature,
                    iterations=bootstrap_iterations,
                    seed=73,
                )
                drift.append(
                    {
                        "fecha_lote": batch,
                        "variable": feature,
                        "referencia": "entrenamiento_telco_churn",
                        **result,
                    }
                )

    return {
        "quality": quality,
        "drift": drift,
        "production_reference_dates": baseline_dates,
        "production_reference_n": len(production_reference),
        "production_reference_rejected": baseline_rejected,
        "production_reference_total": baseline_total,
        "training_reference_n": len(training_rows or []),
    }
