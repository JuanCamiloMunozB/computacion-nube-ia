# Evidencia de Airflow — Unidad 6

Esta carpeta contiene la evidencia reproducible de la ejecución inspeccionada del DAG `pipeline_mlops_churn`.

## Qué ocurrió

La ejecución inspeccionada fue:

`manual__2026-09-24T16:17:27.980813+00:00`

Los estados registrados por Airflow fueron:

- `leer_csv_de_gcs`: `success`
- `enviar_a_api_y_clasificar`: `failed`
- `guardar_en_bigquery`: `upstream_failed`
- `verificar_drift`: `upstream_failed`

## Interpretación temporal

Estos estados pertenecen a la ejecución del DAG realizada durante el laboratorio, con fecha/hora lógica `2026-09-24T16:17:26.779384+00:00`. No fueron provocados por tomar las capturas: las capturas únicamente consultaron el estado existente mediante comandos de lectura (`airflow tasks states-for-dag-run` y `airflow dags list`).

`upstream_failed` significa que la tarea no se ejecutó porque su dependencia anterior (`enviar_a_api_y_clasificar`) falló. Por tanto, no implica por sí solo que BigQuery o el monitoreo estén dañados.

## Conclusión para la entrega

Esta ejecución puntual no completó el pipeline: debe considerarse una ejecución fallida en la etapa de API y no como una validación exitosa de extremo a extremo. Sin embargo, no invalida los hallazgos ya persistidos en ejecuciones anteriores que sí llegaron a BigQuery y generaron las alertas de calidad/drift esperadas. Antes de cerrar la entrega conviene repetir al menos un escenario con la API operativa y conservar la evidencia de los escenarios de alerta.

## Evidencia visual

Las capturas visuales exportadas para la entrega son:

- `airflow_task_states_capture.png`: Cloud Shell con los estados de tareas y el registro del DAG.
- `streamlit_preview_capture.png`: vista de Streamlit con integrantes, proyecto, pestañas de monitoreo y alertas de drift.

Las imágenes corresponden a observaciones de solo lectura; no ejecutan nuevamente el DAG.
