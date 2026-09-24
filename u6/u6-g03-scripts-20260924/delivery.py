"""Resumen reproducible para la sustentación y la app de Unidad 6."""

from __future__ import annotations

from collections import Counter
from statistics import median
from typing import Any

from monitoring import DataQualityError, build_payload


PRODUCTION_REFERENCE = "primeras_semanas_produccion"
TRAINING_REFERENCE = "entrenamiento_telco_churn"


def _accepted_numeric_profile(rows: list[dict[str, Any]]) -> dict[str, float | int] | None:
    payloads = []
    for row in rows:
        try:
            payloads.append(build_payload(row))
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


def legacy_threshold_scenarios(
    quality: list[dict[str, Any]], original: float = 0.30
) -> list[dict[str, Any]]:
    """Compara el umbral anterior y sus contrafactuales, sin cambiar el DAG."""
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


def summarize_delivery(
    report: dict[str, Any],
    rows: list[dict[str, Any]],
    *,
    production_reference_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Extrae hechos de los lotes; deja las hipótesis como interpretación humana."""
    quality = sorted(report.get("quality", []), key=lambda item: str(item["fecha_lote"]))
    drift = report.get("drift", [])
    field_counts: Counter[str] = Counter()
    for item in quality:
        field_counts.update(item.get("errores_por_campo", {}))

    invalid_payment_values: Counter[str] = Counter()
    for row in rows:
        try:
            build_payload(row)
        except DataQualityError as exc:
            if "PaymentMethod" in exc.fields:
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
        (item for item in drift if item.get("referencia") == PRODUCTION_REFERENCE),
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
        if item.get("referencia") == TRAINING_REFERENCE
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
