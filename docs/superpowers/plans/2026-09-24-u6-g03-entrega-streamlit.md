# U6 G03 Streamlit Delivery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Neither execution skill is installed here, so the requested implementation runs inline with test checkpoints.

**Goal:** Complete the Unit 6 Group 3 Streamlit submission and make every client directive defensible from observed evidence.

**Architecture:** Keep the Airflow and BigQuery pipeline unchanged. Add small, testable presentation helpers for the historical-threshold counterfactual and evidence summary; render their results alongside the existing quality, quarantine, drift, bank, and individual-prediction views. Package the app with its required local data and Python module for the INTU submission.

**Tech Stack:** Python 3.12, Streamlit, unittest, existing CSV fixtures and BigQuery evidence.

**Spec:** `u6/UNIDAD6_Lab_Paso_a_Paso (1).md` and `C:/Users/Usuario/Downloads/Monitoreo_pipeline_retencion.md`.

## Global Constraints

- Project `computacionnube20263`; U6 Group 3 resources and file names keep the `u6-g03` prefix.
- The client instruction says no written report; the formal INTU submission is a testable Streamlit application with all team members named.
- Do not change the scoring API contract, Airflow gate, or cloud resources merely to turn expected monitoring alerts green.
- Keep the private Cloud Run API private and never package credentials or tokens.
- Do not claim that the model or campaigns worsened without observed outcomes and campaign records.
- Preserve the user's existing modified and untracked work; do not commit or delete it.

---

### Task 1: Historical threshold counterfactual

**Files:**
- Create: `u6/u6-g03-scripts-20260924/delivery.py`
- Create: `u6/u6-g03-scripts-20260924/tests/test_delivery.py`
- Modify: `u6/streamlit_churn_u6.py`

**Interfaces:**
- Consumes: `report["quality"]`, each row with `fecha_lote` and `tasa_rechazo`.
- Produces: `legacy_threshold_scenarios(quality: list[dict], original: float = 0.30) -> list[dict]`; each result contains `label`, `threshold`, `alert_dates`, and `alert_count`.

- [x] **Step 1: Write a failing test** for 18.68% and 43.94% rejection: 15% alerts twice, 30% once, 60% never; equality to a threshold does not alert.
- [x] **Step 2: Run** `python -m unittest discover -s u6/u6-g03-scripts-20260924/tests -p test_delivery.py -v` and confirm the test initially fails because the helper is absent.
- [x] **Step 3: Implement** `legacy_threshold_scenarios` with comparisons `rate > threshold` for the exact original, half, and double; avoid reusing the existing fields that halve/double the calibrated limit.
- [x] **Step 4: Render** the three scenarios and their detected dates in the quality tab with a short explanation of the 24 August detection advantage.
- [x] **Step 5: Re-run** the focused and existing monitoring tests; leave the user's work uncommitted.

### Task 2: Client answer and bank decision in the app

**Files:**
- Modify: `u6/u6-g03-scripts-20260924/delivery.py`
- Modify: `u6/u6-g03-scripts-20260924/tests/test_delivery.py`
- Modify: `u6/streamlit_churn_u6.py`

**Interfaces:**
- Consumes: `report` from `analyze_records` and the selected input CSV rows.
- Produces: `summarize_delivery(report: dict, rows: list[dict]) -> dict`, with weekly alert dates, first numerical drift versus production, quarantine field counts, bank start/coverage/unknown counts, and explicit reference distinctions.

- [x] **Step 1: Write a failing test** against the supplied ten-week CSV for 703 total, 50 locally quarantined, 27 `PaymentMethod` field errors, drift starting on 10 August for `tenure`, dual numerical alerts from 17 August, 444 bank values after introduction, and six unknown bank categories.
- [x] **Step 2: Run** the focused test and confirm missing summary behavior.
- [x] **Step 3: Implement** the summary using existing validation and normalization functions rather than hardcoding the final values.
- [x] **Step 4: Add** a client-response tab showing: observed changes with dates and magnitudes; a labeled business hypothesis and confirming CRM/campaign data; an interim scoring recommendation; a conditional retraining recommendation requiring labels; and explicit uncertainty about model/campaign performance.
- [x] **Step 5: Fix** the app's data path so uploads use the packaged ten-week CSV as the immutable production reference rather than recalibrating from each uploaded CSV; reject a missing reference file clearly.
- [x] **Step 6: Re-run** tests and inspect the app's data path and default-file behavior.

### Task 3: Runnable INTU package and verification

**Files:**
- Create: `u6/u6-g03-streamlit-requirements-20260924.txt`
- Modify: `u6/u6-g03-ejecucion-20260924.md`
- Create: `u6/u6-g03-streamlit-entrega-20260924.zip` using a packaging command after source verification.

**Interfaces:**
- Consumes: updated app, `monitoring.py`, `delivery.py`, ten-week input and training CSVs.
- Produces: a source package that preserves relative imports and launches with `streamlit run streamlit_churn_u6.py` after installing the small Streamlit dependency list.

- [x] **Step 1: Document** the exact INTU package contents, launch command, required private-API environment variable, and distinction between observed BigQuery evidence and offline dashboard recalculation.
- [x] **Step 2: Validate** Python syntax and run all U6 unit tests.
- [x] **Step 3: Smoke-test** the Streamlit app locally if dependencies are available; otherwise report the precise missing runtime dependency, without claiming live API verification.
- [x] **Step 4: Build** the ZIP with only the five needed source/data files plus the small requirements and handoff instructions, not credentials, Airflow metadata, or unrelated repository edits.
- [x] **Step 5: Inspect** ZIP entry names and sizes; report which live Cloud Shell and INTU checks still require the user's own session.

## Self-Review

- [x] Confirm every directive D1–D6 has visible evidence or an explicit, defensible limitation in Streamlit.
- [x] Confirm the original 30% counterfactual uses 15% and 60%, while the calibrated-size limit remains unchanged.
- [x] Confirm neither the app nor the handoff claims model performance or campaign causality without labels.
- [x] Confirm the ZIP runs from its own root and contains no credentials.

Local verification: 9 unit tests passed; Streamlit AppTest loaded the extracted ZIP with six tabs, no exceptions, and the 703/653/50 summary. The client response contrasts accepted-row medians in the baseline (tenure 32.0; monthly charges 65.93) and the final lot (70.0; 116.92), and the quarantine view breaks field errors down by week. Live Cloud Run invocation from the evaluator's identity and submission to INTU remain outside this local verification.
