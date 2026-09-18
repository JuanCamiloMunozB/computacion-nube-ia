# Skills recomendadas — Tarea Unidad 4/5 (modelo → servicio en producción)

> Guardado para el equipo: qué instalar, por qué, y en qué fase de la tarea se usa cada una.

## Ya instaladas (confirmado en `skills-lock.json`)

- `fastapi-expert` (jeffallan/claude-skills)
- `pydantic` (pydantic/skills)
- `evaluate-ml-pipeline` (probabl-ai/skills)
- `mlops-engineer` + `machine-learning-ops-ml-pipeline` (sickn33/agentic-awesome-skills)

## Pendientes de instalar

El paquete principal de Google **no aparece en el lock file todavía** — instálenlo antes de tocar BigQuery o Cloud Run:

```bash
npx skills add google/skills --skill cloud-run-basics,bigquery-bigframes
```

Y si van a tocar el `Dockerfile` (ya hay uno en el repo, pero conviene revisarlo con la skill antes de reconstruir imagen):

```bash
npx skills add alirezarezvani/claude-skills --skill docker-development
```

## Mapa skill → fase de la tarea

| Skill | Fase | Para qué exactamente |
|---|---|---|
| `bigquery-bigframes` | Entrenamiento (U4) | Confirmar que la query a `u3_master.telco_churn_raw` trae las 13 columnas correctas (no las 8 de la plantilla) |
| `evaluate-ml-pipeline` | Entrenamiento (U4) | Scorecard: 2 arquitecturas × Optuna, AUC/Recall/DPD/EOD/costo, leaderboard 360 |
| `mlops-engineer` / `machine-learning-ops-ml-pipeline` | Entrenamiento (U4) | Trazabilidad del registro en Model Registry, labels de ganador |
| `pydantic` | Contrato (U5) | Reescribir `schemas.py`: `FEATURE_ORDER` de 13 columnas, enums de `Contract`/`PaymentMethod`/`InternetService`, validar que un campo faltante o mal tipado dispare 422 real |
| `fastapi-expert` | Servicio (U5) | Reescribir `main.py`: `/health`, `/predict`, logging estructurado desde el lifespan, manejo de errores 4xx vs 5xx |
| `docker-development` | Empaquetado (U5) | Revisar `Dockerfile` (ya existe, base slim + libgomp1 para XGBoost) antes de reconstruir con el modelo nuevo |
| `cloud-run-basics` | Despliegue (U5) | `gcloud run deploy` con `--no-allow-unauthenticated`, service account dedicada, evidencia con `gcloud run services list` |

## Nota

No prioricen skills de Vertex AI genéricas — están orientadas a Gemini/LLMs. La entrega usa un modelo tabular `.pkl/.joblib` servido desde FastAPI, así que la combinación útil sigue siendo: **BigQuery + evaluate-ml-pipeline (entrenamiento) → Pydantic + FastAPI + Docker + Cloud Run (servicio)**.
