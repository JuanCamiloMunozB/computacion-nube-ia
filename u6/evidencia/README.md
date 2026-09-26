# Evidencia visual — Unidad 6

Esta carpeta contiene capturas de los comandos ejecutados en Cloud Shell para verificar el laboratorio de la Unidad 6.

## Archivos

- `01-airflow-dag-registrado.png`: comando que confirma que `pipeline_mlops_churn` está registrado en Airflow.
- `02-airflow-estados-tareas.png`: comando y estados de las tareas de una ejecución histórica del DAG.
- `03-bigquery-calidad-lotes.png`: consulta de calidad por lote, con alertas el 24 y 31 de agosto.
- `04-bigquery-alertas-drift.png`: consulta de alertas PSI para `tenure` y `MonthlyCharges` frente a las primeras semanas de producción.
- `05-cloud-run-health.png`: consulta de la URL de Cloud Run y respuesta satisfactoria del endpoint privado `/health`.

Las capturas se tomaron el 25 de septiembre de 2026. Los comandos de consulta son de solo lectura; no vuelven a ejecutar el DAG ni modifican las tablas.
