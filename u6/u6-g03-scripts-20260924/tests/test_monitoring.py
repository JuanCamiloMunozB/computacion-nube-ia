from __future__ import annotations

import sys
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_DIR))

from monitoring import (  # noqa: E402
    DataQualityError,
    analyze_records,
    beta_binomial_limit,
    build_payload,
    normalize_bank,
    read_csv,
)


U6_DIR = Path(__file__).resolve().parents[2]
PRODUCTION_FILE = U6_DIR / "u6-g03-lotes-retencion-20260924.csv"


class MonitoringTests(unittest.TestCase):
    def test_build_payload_matches_all_api_features(self) -> None:
        row = read_csv(PRODUCTION_FILE)[1]
        payload = build_payload(row)
        self.assertEqual(
            set(payload),
            {
                "customer_id",
                "gender",
                "senior_citizen",
                "partner",
                "dependents",
                "tenure",
                "monthly_charges",
                "contract",
                "payment_method",
                "internet_service",
                "online_security",
                "tech_support",
                "paperless_billing",
            },
        )
        self.assertNotIn("BancoPago", payload)
        self.assertTrue(payload["senior_citizen"])

    def test_rejection_reports_all_invalid_fields(self) -> None:
        row = read_csv(PRODUCTION_FILE)[1]
        row["tenure"] = "150"
        row["PaymentMethod"] = "PSE"
        with self.assertRaises(DataQualityError) as raised:
            build_payload(row)
        self.assertEqual(raised.exception.fields, ["PaymentMethod", "tenure"])

    def test_bank_normalization_keeps_unknowns_visible(self) -> None:
        self.assertEqual(normalize_bank("  bancolombia "), "Bancolombia")
        self.assertEqual(normalize_bank("BCO BOGOTA"), "Banco de Bogotá")
        self.assertEqual(normalize_bank("007"), "Desconocido")
        self.assertIsNone(normalize_bank("  "))

    def test_threshold_uses_sample_size(self) -> None:
        small = beta_binomial_limit(20, rejected=1, total=237)
        large = beta_binomial_limit(100, rejected=1, total=237)
        self.assertGreaterEqual(small, 0)
        self.assertLessEqual(small, 20)
        self.assertGreaterEqual(large, small)
        self.assertLessEqual(large, 100)

    def test_real_batches_reconcile_to_contract(self) -> None:
        rows = read_csv(PRODUCTION_FILE)
        report = analyze_records(rows, bootstrap_iterations=2)
        self.assertEqual(len(rows), 703)
        self.assertEqual(sum(item["aceptados"] for item in report["quality"]), 653)
        self.assertEqual(sum(item["rechazados"] for item in report["quality"]), 50)
        self.assertEqual(report["production_reference_dates"], [
            "2026-06-29",
            "2026-07-06",
            "2026-07-13",
            "2026-07-20",
        ])
        self.assertEqual(report["production_reference_n"], 236)
        by_date = {item["fecha_lote"]: item for item in report["quality"]}
        self.assertEqual(by_date["2026-08-24"]["rechazados"], 17)
        self.assertEqual(by_date["2026-08-31"]["rechazados"], 29)
        self.assertEqual(by_date["2026-08-31"]["banco_desconocido"], 1)


if __name__ == "__main__":
    unittest.main()
