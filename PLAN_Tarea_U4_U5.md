# Plan — Tarea "modelo a servicio en producción" (Unidad 4 + 5)

> ⚠️ **Este documento es el resumen de contexto y decisiones.** El plan de ejecución
> paso a paso (el que debe seguir quien implemente) está en
> **[`docs/superpowers/plans/2026-09-18-u4-u5-modelo-a-servicio.md`](./docs/superpowers/plans/2026-09-18-u4-u5-modelo-a-servicio.md)** —
> 8 tareas con comandos exactos, código completo, tests y criterios de verificación.
> Si los dos documentos se contradicen, **gana el plan de ejecución**.

**Apertura:** sábado 12 de septiembre de 2026 · **Cierre:** sábado 19 de septiembre de 2026, 06:00

## 0. Hallazgo crítico antes de empezar — leer esto primero

El notebook `UNIDAD4_LAB_clase.ipynb` que tienen es la **plantilla genérica de la profesora** (8 features, variable protegida = `SeniorCitizen`). El enunciado de la tarea pide explícitamente:

- *"Las features son las que ya seleccionaron y justificaron [en Tarea 1], no se agregan nuevas sin justificación adicional."*
- *"La variable protegida es la de género."*

Su propio trabajo de Unidad 3 (`u3-g03-nb-20260901.ipynb`, sección 10) ya resuelve esto: el **modelo ampliado de 13 columnas** —

```
gender, SeniorCitizen, Partner, Dependents, tenure, Contract, PaymentMethod,
MonthlyCharges, InternetService, OnlineSecurity, TechSupport, PaperlessBilling
```

— con `gender_Male` como atributo protegido, mitigado por reweighting. **Ese es el punto de partida real de esta tarea, no la plantilla de 8 columnas.**

También ya existen en el repo `main.py`, `schemas.py`, `Dockerfile`, `requirements.txt` y `Guia_Lab_Unidad5.md` — pero están escritos para el modelo viejo (9 columnas, protegida `SeniorCitizen`, arquitectura B de la plantilla de clase). **Van a reescribirse**, no a reutilizarse tal cual — mantengan la estructura general (lifespan que carga el modelo una vez, `FEATURE_ORDER` explícito, logging estructurado) pero con las 13 columnas y `gender` como protegida.

---

## 0.1 Referencia de g02 — qué tomar y qué no

g02 (`docReference/`) entregó un U4 metodológicamente más sofisticado que la plantilla: 4 arquitecturas (XGBoost, LightGBM, LogReg, MLP), Optuna optimizando **`business_cost` directamente** (no AUC), calibración isotonic post-selección, y threshold tuning por bisección. Es defendible académicamente, pero **su scorecard no trae las columnas que pide la plantilla de la profesora** (`Costo_equidad_ratio`, comparación explícita base-vs-mitigado) — optimiza distinto y por lo tanto no es directamente comparable/reutilizable para lo que pide la rúbrica de clase. También quitaron `SeniorCitizen` del feature set (nosotros no, sin justificación adicional no se toca).

**Qué SÍ tomamos de g02** (ya aplicado en el notebook de g03):
- Competencia con **arquitecturas de familias distintas** (no solo dos configuraciones del mismo XGBoost).
- Separación código en carpeta `service/app/` con `schemas.py` + `main.py`, lifespan async, logging estructurado por `json_fields`, service account dedicada, guía de despliegue paso a paso con nomenclatura del grupo.
- Handler de `RequestValidationError` que loguea los 422 (útil para "trazabilidad" que pide el enunciado).

**Qué NO copiamos** (para no perder puntos por desviarnos de la rúbrica, y por ser g03 no g02):
- Optimizar `business_cost` en vez de AUC en la búsqueda Optuna — la plantilla pide el patrón base-vs-mitigado con `Costo_equidad_ratio`, que requiere entrenar con AUC como criterio de búsqueda y aplicar `sample_weight` aparte.
- Calibración isotonic + threshold tuning — mejora real pero no la pide el enunciado; agregarla es trabajo extra sin beneficio en la nota y con riesgo de introducir bugs antes de la entrega.
- Quitar `SeniorCitizen` — g03 no tiene esa justificación documentada.

---

## 1. Entrenamiento (Bloque GCP — Workbench) — ✅ notebook ya generado

**Estado:** el notebook **`u4-g03-nb-20260918.ipynb`** (en la raíz del repo) ya está escrito, validado sintácticamente, y listo para subir a Workbench y correr. No hace falta reescribirlo desde cero — el trabajo de otro agente en esta fase es **ejecutarlo y depurar según los resultados reales**, no rediseñarlo.

Resumen de lo que hace (28 celdas):
- Sección 1: carga las **13 columnas de Tarea 1** (`gender, SeniorCitizen, Partner, Dependents, tenure, Contract, PaymentMethod, MonthlyCharges, InternetService, OnlineSecurity, TechSupport, PaperlessBilling, Churn`) desde `u3_master.telco_churn_raw`.
- Sección 2: one-hot encoding (mismo criterio que `u3-g03-nb-20260901.ipynb`), split 80/20 estratificado, `random_state=42`.
- Sección 3: `sample_weight` sobre `gender_Male × Churn` (protegida = género, **no** `SeniorCitizen`).
- Sección 4: **3 arquitecturas reales** — XGBoost, LightGBM, Logistic Regression — cada una con su propia búsqueda Optuna (20 trials, 5-fold CV, multi-objetivo AUC↑/std↓, mismo criterio de selección que la plantilla).
- Sección 5: cada arquitectura entrenada **base** (sin peso) y **mitigada** (con peso) → scorecard con exactamente las columnas obligatorias: `AUC, Precision, Recall, DPD, EOD, AUC_base, EOD_base, Costo_equidad_ratio, Costo_negocio_USD, Score_final` (`Score_final = AUC` si `EOD ≤ 0.2`, si no `-1`).
- Sección 6: log a Vertex AI Experiments por arquitectura.
- Sección 7: sube los 3 modelos a GCS y los registra en Model Registry, marca la ganadora con `labels={"ganador": "true"}`.

### 1.1 Qué falta hacer (para el agente que ejecute en Workbench)
1. Llenar `Integrantes` en la celda de título.
2. Confirmar `PROJECT_ID = "computacionnube20261"` contra el proyecto real asignado hoy 2026-09-18 (puede haber cambiado de instancia de curso — verificar en la consola antes de correr).
3. Levantar Workbench: `gcloud workbench instances create u4-g03 --project=<PROJECT_ID> --location=us-central1-a --machine-type=e2-standard-2 --metadata=idle-timeout-seconds=2700`.
4. Subir el notebook, correr celda por celda (no "Run All" ciego — revisar el leaderboard de la Sección 5 antes de continuar a registro).
5. **Punto de atención real:** en Sección 7, `SERVING_CONTAINERS` trae contenedores prediseñados de Vertex AI marcados con `# revisar version` — LightGBM y LogReg no tienen contenedor prediseñado oficial garantizado; si falla el `Model.upload`, no es bloqueante (no se crea Endpoint en U4), pero anotarlo como limitación conocida.
6. Al terminar, copiar del output de Sección 5/7: **el nombre de la arquitectura ganadora**, el `GCS_MODEL_PATH` exacto, y `list(X_train.columns)` (el `FEATURE_ORDER` real, con los nombres limpiados por regex) — eso alimenta directamente `schemas.py` de U5.
7. Costos de negocio: el notebook usa los supuestos de la plantilla (`FN=$150`, `FP=1 mes de MonthlyCharges`). Si la Tarea 1 de g03 definió otros valores, ajustar `COSTO_DESCONEXION_USD`/`MESES_OFERTA_RETENCION` en la celda de configuración antes de correr.

---

## 2. Contrato y servicio (Bloque local/Cloud Shell)

**Objetivo:** el modelo ganador de 1.4 se convierte en API con contrato, logging, Docker y Cloud Run.

### 2.1 `schemas.py` — reescribir, no reusar el actual
- `FEATURE_ORDER` con las 13 columnas post-encoding (incluye `gender_Male` — la variable protegida SÍ es una feature del modelo, solo cambia qué mide fairlearn, no qué recibe el modelo).
- `ClienteInput`: un campo por variable de negocio + enums para `Contract`, `PaymentMethod`, `InternetService`, `OnlineSecurity`, `TechSupport`, `PaperlessBilling` — valores idénticos a los de BigQuery (fuente: diccionario de datos `.xlsx`).
- Usar la skill `pydantic` para: (a) que un campo faltante o un enum inválido dispare 422 automáticamente, (b) revisar que los `Field(..., ge=/gt=)` reflejen los rangos reales del dataset.
- `PrediccionOutput` puede mantener la forma actual (customer_id, risk_score, model_version, predicted_at, requested_by, source) — esa parte del contrato ya está bien pensada.

### 2.2 `main.py` — reescribir apuntando al modelo nuevo
- `MODEL_GCS_PATH` → la ruta real del modelo ganador (paso 1.4), no la de la plantilla.
- Mantener el patrón de lifespan (carga una sola vez) y logging estructurado **desde el principio**, no como agregado — el enunciado lo exige explícitamente.
- Usar la skill `fastapi-expert` para revisar `/health` (503 si el modelo no cargó) y `/predict` (422 vs 500 bien diferenciados).

### 2.3 Docker
- Revisar el `Dockerfile` existente con la skill `docker-development` (ya tiene `libgomp1` para XGBoost).
- **Si la arquitectura ganadora es LightGBM**, agregar también `libgomp1` (mismo requisito de OpenMP) y `lightgbm` a `requirements.txt` — si ganó XGBoost o LogReg, no hace falta.
- Build + push a Artifact Registry (`churn-api-repo`, nomenclatura del grupo).

### 2.4 Cloud Run
- Usar la skill `cloud-run-basics` para el despliegue:
  - `--no-allow-unauthenticated` (sin acceso público — restricción explícita del enunciado)
  - Service account dedicada (`churn-api-sa`) con **solo** `roles/storage.objectViewer` sobre el bucket del modelo — nada más.
  - `--min-instances=0` para no dejar costo corriendo.
- Seguir `Guia_Lab_Unidad5.md` pasos 1–9 (ya escrita y probada), ajustando solo las rutas/nombres al modelo nuevo.

### 2.5 Evidencia (los 4 casos + capturas)
1. `curl /health` → 200
2. `curl /predict` con payload **válido** → 200 con predicción
3. `curl /predict` con un campo faltante → 422
4. `curl /predict` con un enum inválido (ej. `contract: "otro"`) → 422
5. Captura de `gcloud run services list` mostrando el servicio activo

### 2.6 Cierre
- Apagar/borrar la instancia de Workbench.
- **NO borrar** el bucket, ni Model Registry, ni los demás artefactos de U4.
- Puede bajarse el servicio de Cloud Run después de tomar la evidencia (el enunciado lo permite explícitamente).

---

## 3. Entregables finales
- [ ] `schemas.py` (reescrito, 13 features, protegida = género)
- [ ] `main.py` (reescrito, logging estructurado desde el inicio)
- [ ] Captura `gcloud run services list`
- [ ] Captura `curl /health`
- [ ] Captura `curl /predict` caso válido
- [ ] Captura `curl /predict` caso(s) 422

## 4. Orden sugerido de trabajo
1. Confirmar features + valores exactos de categorías desde el diccionario de datos y `u3-g03-nb-20260901.ipynb`.
2. Adaptar el notebook de U4 (2 arquitecturas × Optuna × base/mitigado) → leaderboard → registrar ganador.
3. Reescribir `schemas.py` y `main.py` en paralelo con el registro (ya se sabe el `FEATURE_ORDER`).
4. Build → push → deploy → 4 pruebas → capturas.
5. Apagar instancia, bajar servicio si se desea, dejar bucket/registry intactos.

Ver también [`SKILLS_RECOMENDADAS.md`](./SKILLS_RECOMENDADAS.md) para qué skill usar en cada fase.
