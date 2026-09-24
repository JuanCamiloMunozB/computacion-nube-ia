-- Infraestructura aislada de Unidad 6, Grupo 3.
-- Proyecto: computacionnube20263. Región: us-central1.
-- Dataset y tablas usan guion bajo según la convención de BigQuery.
CREATE SCHEMA IF NOT EXISTS `computacionnube20263.u6_g03_data_20260924`
OPTIONS (location = 'us-central1');

CREATE TABLE IF NOT EXISTS `computacionnube20263.u6_g03_data_20260924.u6_g03_resultados_20260924` (
  customer_id STRING NOT NULL,
  fecha_lote DATE,
  gender STRING,
  senior_citizen BOOL,
  partner BOOL,
  dependents BOOL,
  tenure INT64,
  monthly_charges FLOAT64,
  contract STRING,
  payment_method STRING,
  internet_service STRING,
  online_security STRING,
  tech_support STRING,
  paperless_billing BOOL,
  banco_pago_raw STRING,
  banco_pago_normalizado STRING,
  customer_risk_score FLOAT64,
  model_version STRING,
  predicted_at TIMESTAMP,
  requested_by STRING,
  source STRING,
  input_file STRING,
  dag_run_id STRING
)
OPTIONS (description = 'Predicciones aceptadas de U6 grupo 3');

CREATE TABLE IF NOT EXISTS `computacionnube20263.u6_g03_data_20260924.u6_g03_cuarentena_20260924` (
  customer_id STRING,
  fecha_lote DATE,
  datos_originales STRING,
  codigo_error STRING,
  campos_error STRING,
  error_detalle STRING,
  http_status INT64,
  archivo_origen STRING,
  dag_run_id STRING,
  usuario STRING,
  fecha_proceso TIMESTAMP
)
OPTIONS (description = 'Filas rechazadas con la causa y campos identificados');

CREATE TABLE IF NOT EXISTS `computacionnube20263.u6_g03_data_20260924.u6_g03_monitoreo_lotes_20260924` (
  fecha_lote DATE NOT NULL,
  archivo_origen STRING,
  dag_run_id STRING,
  total_registros INT64,
  aceptados INT64,
  rechazados INT64,
  tasa_rechazo FLOAT64,
  limite_rechazos INT64,
  umbral_rechazo FLOAT64,
  umbral_mitad FLOAT64,
  umbral_doble FLOAT64,
  umbral_actual FLOAT64,
  alerta_calidad BOOL,
  alerta_umbral_actual BOOL,
  alerta_drift BOOL,
  cantidad_alertas_drift INT64,
  tasa_rechazo_referencia FLOAT64,
  n_referencia_produccion INT64,
  fechas_referencia_produccion ARRAY<DATE>,
  n_referencia_entrenamiento INT64,
  banco_no_vacio INT64,
  banco_completitud FLOAT64,
  banco_desconocido INT64,
  banco_categorias JSON,
  errores_por_campo JSON,
  created_at TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS `computacionnube20263.u6_g03_data_20260924.u6_g03_drift_lotes_20260924` (
  fecha_lote DATE NOT NULL,
  variable STRING NOT NULL,
  referencia STRING NOT NULL,
  psi FLOAT64,
  umbral_psi FLOAT64,
  alerta BOOL,
  n_referencia INT64,
  n_lote INT64,
  dag_run_id STRING,
  created_at TIMESTAMP NOT NULL
);
