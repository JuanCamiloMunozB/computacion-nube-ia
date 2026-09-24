from __future__ import annotations

import sys
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_DIR))

from delivery import legacy_threshold_scenarios, summarize_delivery  # noqa: E402
from monitoring import analyze_records, read_csv  # noqa: E402


U6_DIR = Path(__file__).resolve().parents[2]
PRODUCTION_FILE = U6_DIR / "u6-g03-lotes-retencion-20260924.csv"


class DeliveryTests(unittest.TestCase):
    def test_legacy_thresholds_are_based_on_original_thirty_percent(self) -> None:
        quality = [
            {"fecha_lote": "2026-08-24", "tasa_rechazo": 17 / 91},
            {"fecha_lote": "2026-08-31", "tasa_rechazo": 29 / 66},
            {"fecha_lote": "equal", "tasa_rechazo": 0.15},
        ]
        scenarios = legacy_threshold_scenarios(quality)
        self.assertEqual([item["threshold"] for item in scenarios], [0.15, 0.30, 0.60])
        self.assertEqual(scenarios[0]["alert_dates"], ["2026-08-24", "2026-08-31"])
        self.assertEqual(scenarios[1]["alert_dates"], ["2026-08-31"])
        self.assertEqual(scenarios[2]["alert_dates"], [])
        self.assertEqual([item["alert_count"] for item in scenarios], [2, 1, 0])

    def test_real_csv_summary_preserves_field_overlaps_and_bank_history(self) -> None:
        rows = read_csv(PRODUCTION_FILE)
        report = analyze_records(rows, bootstrap_iterations=2)
        summary = summarize_delivery(report, rows)
        self.assertEqual(summary["total"], 703)
        self.assertEqual(summary["accepted"], 653)
        self.assertEqual(summary["rejected"], 50)
        self.assertEqual(summary["quality_alert_dates"], ["2026-08-24", "2026-08-31"])
        self.assertEqual(summary["quarantine_fields"], {
            "MonthlyCharges": 7,
            "PaymentMethod": 27,
            "tenure": 21,
        })
        self.assertEqual(sum(summary["quarantine_fields"].values()), 55)
        self.assertEqual(summary["quarantine_by_date"]["2026-06-29"], {
            "MonthlyCharges": 1,
        })
        self.assertEqual(summary["quarantine_by_date"]["2026-08-24"], {
            "MonthlyCharges": 2,
            "PaymentMethod": 10,
            "tenure": 6,
        })
        self.assertEqual(summary["quarantine_by_date"]["2026-08-31"], {
            "MonthlyCharges": 2,
            "PaymentMethod": 17,
            "tenure": 14,
        })
        self.assertEqual(summary["invalid_payment_values"], {
            "Corporate billing": 6,
            "Credit card (manual)": 3,
            "Digital wallet": 5,
            "PayPal": 7,
            "PSE": 6,
        })
        self.assertEqual(summary["first_bank_date"], "2026-07-27")
        self.assertEqual(summary["bank_post_total"], 466)
        self.assertEqual(summary["bank_post_filled"], 444)
        self.assertEqual(summary["bank_unknown"], 6)
        self.assertAlmostEqual(summary["bank_coverage"], 444 / 466)
        self.assertEqual(summary["baseline_profile"], {
            "n": 236,
            "tenure_median": 32.0,
            "monthly_charges_median": 65.93,
        })
        self.assertEqual(summary["latest_profile"], {
            "n": 37,
            "tenure_median": 70.0,
            "monthly_charges_median": 116.92,
        })

    def test_summary_distinguishes_training_and_production_references(self) -> None:
        report = {
            "quality": [{
                "fecha_lote": "2026-06-29", "total": 1, "aceptados": 1,
                "rechazados": 0, "tasa_rechazo": 0.0, "alerta_calidad": False,
                "errores_por_campo": {}, "banco_no_vacio": 0,
                "banco_desconocido": 0,
            }, {
                "fecha_lote": "2026-08-17", "total": 1, "aceptados": 1,
                "rechazados": 0, "tasa_rechazo": 0.0, "alerta_calidad": False,
                "errores_por_campo": {}, "banco_no_vacio": 1,
                "banco_desconocido": 0,
            }],
            "drift": [
                {"fecha_lote": "2026-06-29", "referencia": "entrenamiento_telco_churn",
                 "variable": "tenure", "psi": 2.0, "umbral_psi": 0.3, "alerta": True},
                {"fecha_lote": "2026-06-29", "referencia": "primeras_semanas_produccion",
                 "variable": "tenure", "psi": 0.1, "umbral_psi": 0.3, "alerta": False},
                {"fecha_lote": "2026-08-17", "referencia": "primeras_semanas_produccion",
                 "variable": "tenure", "psi": 1.2, "umbral_psi": 0.4, "alerta": True},
            ],
        }
        summary = summarize_delivery(report, [])
        self.assertEqual(summary["first_production_alert"]["tenure"], "2026-08-17")
        self.assertEqual(summary["training_alerts_on_first_date"], 1)
        self.assertEqual(summary["latest_production_psi"]["tenure"]["psi"], 1.2)

    def test_uploaded_csv_can_be_analyzed_against_fixed_production_reference(self) -> None:
        reference = read_csv(PRODUCTION_FILE)
        uploaded = read_csv(U6_DIR / "churn_batch_ok.csv")
        report = analyze_records(
            uploaded,
            production_reference_rows=reference,
            bootstrap_iterations=2,
        )
        self.assertEqual(report["production_reference_dates"], [
            "2026-06-29", "2026-07-06", "2026-07-13", "2026-07-20",
        ])
        self.assertEqual(report["production_reference_n"], 236)


if __name__ == "__main__":
    unittest.main()
