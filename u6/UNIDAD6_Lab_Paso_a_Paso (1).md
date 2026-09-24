# UNIDAD 6 — Paso a paso del laboratorio

Proyecto: `computacionnube20261`

&nbsp;· Región: `us-central1`&nbsp;

API: `https://churn-api-rcifbswykq-uc.a.run.app/predict`

(obtenida de lo que se hizo en la unidad 5\)

## ANTES DE EMPEZAR — qué NO se borra

El modelo viaja dentro del contenedor, y Cloud Run con `min-instances=0` no cobra mientras nadie lo llame. La regla ya no es "borra todo", es **borra lo que cobra por existir, deja lo que cobra por usarse.**

Se quedan arriba: el servicio , la imagen, la service account, el modelo y lo que se hizo en la unidad 5

&nbsp;

### Si alguien ya borró `churn-api`

No hay que reconstruir nada, la imagen sigue guardada:

```
gcloud run deploy churn-api \
  --image=us-central1-docker.pkg.dev/PROYECTO/REPO/IMAGEN:VERSION \
  --region=us-central1 --service-account=churn-api-sa \
  --no-allow-unauthenticated --min-instances=0 --max-instances=2 \
  --memory=512Mi --port=8080
```

&nbsp;

## 1\. Confirmar dónde estamos parados

&nbsp;

```
gcloud config get-value project
```

Debe responder EL PORYECTO ASIGNADO .&nbsp;

Si no: gcloud config set project EL PORYECTO ASIGNADO

## 2\. Verificar que la API sigue viva

&nbsp;

```
gcloud run services describe IMAGEN --region=us-central1 \
  --format="value(status.url, status.latestReadyRevisionName)"
```

Debe devolver una URL y la revisión churn-api-00003-s9t.

Si algo sale distinto: verificar con `gcloud run services list`.&nbsp;

Si devuelve otra revisión, corre una imagen vieja y hay que redesplegar&nbsp;

Si falla con error de credenciales: `gcloud auth login`.

&nbsp;

## 3\. Probar la API a mano antes de automatizar

&nbsp;

&nbsp;

```
API_URL=$(gcloud run services describe IMAGEN --region=us-central1 --format="value(status.url)")/predict
echo $API_URL
```

Una predicción suelta:

```
curl -s -X POST "$API_URL" \
  -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  -H "Content-Type: application/json" \
  -d '{"customer_id":"TEST-001","senior_citizen":false,"partner":true,"dependents":false,"tenure":12,"monthly_charges":70.5,"contract":"Month-to-month","payment_method":"Electronic check"}'
```

&nbsp;

## 4\. Preparar la carpeta de trabajo

U5 es el código que *construyó* la API; U6 solo la *consume*. Asì que tengan cuidado en mezclarlas

```
mkdir -p ~/u6_lab && cd ~/u6_lab
```

Aquí van los cuatro CSV, el DDL, el DAG y el Streamlit.

## 5\. Crear el bucket y subir los datos

los nombres de bucket son **globales**, no por proyecto. Si alguien en el mundo ya usó ese nombre, lo rechaza; ahí hay que agregar un sufijo propio y usarlo consistentemente después, incluyendo la constante `GCS_BUCKET` del DAG.

&nbsp;

&nbsp;

```
gcloud storage buckets create gs://NOMBREBUCKETU6 \
  --location=us-central1 --uniform-bucket-level-access
```

&nbsp;

```
gcloud storage cp churn_batch_*.csv gs://mlops-churn-u6/input/
```

&nbsp;

```
gcloud storage ls gs://NOMBREBUCKETU6/input/
```

&nbsp;

## 6\. Crear el dataset y las tablas

El DDL crea el dataset y las dos tablas.

```
bq query --use_legacy_sql=false --location=us-central1 < bigquery_ddl.sql
```

Cuidado con  la región. Siempre poner \--location=us-central1

```
bq ls NOMBREBUCKETU6
```

Deben aparecer `resultados` y `cuarentena`, vacías.

## 7\. Instalar Airflow

&nbsp;

```
pip install "apache-airflow==3.3.2" --break-system-packages
```

Tarda unos minutos, arrastra muchas dependencias.

> #### **`⚠️ ATENCIÓN — el comando NO se llama airflow`**

**`En Airflow 3.3.2 el ejecutable se llama apache-airflow.`**

&nbsp;

Verificar:

```
apache-airflow version
```

## 8\. Inicializar Airflow

&nbsp;`AIRFLOW_HOME` define la carpeta.&nbsp;

`AIRFLOW__CORE__LOAD_EXAMPLES=False` apaga los DAGs de ejemplo que trae de fábrica `db migrate` crea la base de metadatos.&nbsp;

```
export AIRFLOW_HOME=~/airflow
export AIRFLOW__CORE__LOAD_EXAMPLES=False
apache-airflow db migrate
```

## 9\. Instalar el DAG

&nbsp;

Recuperar la URL:

```
echo $API_URL
```

Editar `~/u6_lab/dag_pipeline_churn.py` y reemplazar:

```
API_URL = "https://TU_SERVICE_URL/predict"
```

por la real, en el caso de la clase:

```
API_URL = "https://churn-api-rcifbswykq-uc.a.run.app/predict"
```

Copiar y registrar:

```
mkdir -p ~/airflow/dags
cp ~/u6_lab/dag_pipeline_churn.py ~/airflow/dags/
```

&nbsp;

Airflow revisa esa carpeta cada cierto tiempoy necesitamos que la revise para que identifique los DAGs. Eso es lo que hace `reserialize`.

&nbsp;

&nbsp;

```
apache-airflow dags reserialize
```

&nbsp;

```
apache-airflow dags list
```

Debe aparecer el dag\_id, en el caso de la clase: `pipeline_mlops_churn` y nada más.

&nbsp;Si no aparece, ahora sí `apache-airflow dags list-import-errors` dirá qué pasa&nbsp;

## 10\. Correr los cuatro escenarios

disparar un DAG desde la terminal en modo test

```
apache-airflow dags test pipeline_mlops_churn --conf '{"archivo": "churn_batch_ok.csv"}'
```

&nbsp;

```
apache-airflow dags test pipeline_mlops_churn --conf '{"archivo": "churn_batch_mix.csv"}'
```

&nbsp;

```
apache-airflow dags test pipeline_mlops_churn --conf '{"archivo": "churn_batch_esquema.csv"}'
```

&nbsp;

```
apache-airflow dags test pipeline_mlops_churn --conf '{"archivo": "churn_batch_drift.csv"}'
```

Resultados verificados:

```
ok        20 total   20 OK    0 rechazados    0.0%   success   (~26 seg)
mix       20 total   15 OK    5 rechazados   25.0%   success
esquema   20 total   17 OK    3 rechazados   15.0%   success
drift     20 total    5 OK   15 rechazados   75.0%   FAILED
```

&nbsp;

## 11\. Streamlit: el otro canal

&nbsp;

**1\. Subir el archivo a su Cloud Shell:** botón de los tres puntos arriba a la derecha → "Subir archivo".

**2\. Instalar Streamlit:**

```
pip install streamlit --break-system-packages
```

**3\. Correrlo:**

```
streamlit run streamlit_churn_u6.py --server.port 8501 \
  --server.enableCORS=false --server.enableXsrfProtection=false
```

**4\. Abrirlo:** Web Preview (ícono arriba a la derecha) → Cambiar puerto → 8501\.

&nbsp;

&nbsp;

## 14\. Limpieza (SOLO después de la clase)

```
bq rm -r -f -d computacionnube20261:mlops_churn
gcloud storage rm -r gs://mlops-churn-u6
rm -rf ~/airflow
```

**El servicio `churn-api` NO se borra** (ver la sección inicial).

Si se quiere empezar la clase con las tablas vacías, sin borrar nada:

```
bq query --use_legacy_sql=false --location=us-central1 \
  'TRUNCATE TABLE `computacionnube20261.mlops_churn.resultados`; TRUNCATE TABLE `computacionnube20261.mlops_churn.cuarentena`'
```

&nbsp;

&nbsp;

&nbsp;