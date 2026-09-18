# Guía del Laboratorio — Unidad 5 (shell- MV)
### De modelo entrenado a servicio en producción

> Prerrequisito: modelo corregido de U4 (Arquitectura B) ya registrado en Model Registry. Tienes 4 archivos listos: `schemas.py`, `main.py`, `requirements.txt`, `Dockerfile`.

---

## Paso 1 — Organizar los archivos en Cloud Shell

```bash
mkdir -p u5_lab/app
```
> Crea la carpeta del proyecto. `app/` es obligatoria — `main.py` importa `schemas.py` como `app.schemas`.

Sube los 4 archivos (botón de tres puntos → Subir), luego muévelos a su lugar:

```bash
mv Dockerfile requirements.txt u5_lab/
mv schemas.py main.py u5_lab/app/
cd u5_lab
```

---

## Paso 2 — Crear el repositorio de imágenes (una sola vez, los nombres deben seguir la nomenclatura)

```bash
gcloud artifacts repositories create churn-api-repo \
  --repository-format=docker --location=us-central1
```


```bash
gcloud auth configure-docker us-central1-docker.pkg.dev
```


---

## Paso 3 — Construir la imagen (tener a la mano el porjectid)

```bash
docker build -t us-central1-docker.pkg.dev/PROJECT_ID/churn-api-repo/churn-api:v1 .
```


---

## Paso 4 — Subir la imagen

```bash
docker push us-central1-docker.pkg.dev/PROJECT_ID/churn-api-repo/churn-api:v1
```
aveces falla por conectividad.. intentar otra vez, si persiste entonces:
```bash
gcloud auth configure-docker us-central1-docker.pkg.dev
docker push us-central1-docker.pkg.dev/PROJECT_ID/churn-api-repo/churn-api:v1
```
---

## Paso 5 — Desplegar a Cloud Run

```bash
gcloud run deploy churn-api \
  --image=us-central1-docker.pkg.dev/PROJECT_ID/churn-api-repo/churn-api:v1 \
  --region=us-central1 \
  --no-allow-unauthenticated \
  --min-instances=0 --max-instances=1 \
  --memory=512Mi --port=8080
```

Para tener en cuenta :
* --no-allow-unauthenticated` = servicio cerrado, sin acceso público. `--min-instances=0` = no cobra si nadie lo usa. `--max-instances=1` = techo de costo.
* Guarda la **Service URL** que devuelve — la vas a necesitar en todos los pasos siguientes.

---

## Paso 6 — Probar `/health`

```bash
curl -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  https://TU_SERVICE_URL/health
```
los status deben ser 200
* ten cuidad el service url es sin el http://

---

## Paso 7 — Probar `/predict`

```bash
curl -X POST \
  -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  -H "Content-Type: application/json" \
  -d '{
    "customer_id": "TEST-001",
    "senior_citizen": false,
    "partner": true,
    "dependents": false,
    "tenure": 12,
    "monthly_charges": 70.5,
    "contract": "Month-to-month",
    "payment_method": "Electronic check"
  }' \
  https://TU_SERVICE_URL/predict
```


---

## Paso 8 — Seguridad: service account dedicada
recuerden que el bucket se creo en la unidad 4 (se borro unicamente la instancia). por nomenclatura era: {tu proyecto}-u4-class-mdl-{fecha de la clase de U4}. en mi caso es: computacionnube20261-u4-class-mdl-20260904

Regla mnemotécnica:

```bash
gcloud iam service-accounts create churn-api-sa
```
Crea una identidad propia para el servicio, en vez de usar la cuenta genérica del proyecto.

```bash
gcloud storage buckets add-iam-policy-binding gs://TU_BUCKET \
  --member="serviceAccount:churn-api-sa@PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/storage.objectViewer"
```
 Le da SOLO permiso de lectura sobre el bucket del modelo — nada más.


---

## Paso 9 — Observabilidad: agregar logging estructurado a main.py

Con el servicio ya seguro (Paso 8), ahora lo hacemos observable — que cada predicción deje rastro. Esto se edita a mano en `app/main.py`(con `nano app/main.py` ).

**9.1 — Busca el `return` final de la función `predict()`:**

```python
    return PrediccionOutput(
        customer_id=cliente.customer_id,
        customer_risk_score=round(float(proba), 4),
        model_version=MODEL_VERSION,
        predicted_at=datetime.now(timezone.utc),
        requested_by="pendiente-auth-iam",
        source="api_single",
        input_file=None,
    )
```

**9.2 — Reemplázalo por esto** (arma la respuesta primero, loguea, y devuelve al final):

```python
    resultado = PrediccionOutput(
        customer_id=cliente.customer_id,
        customer_risk_score=round(float(proba), 4),
        model_version=MODEL_VERSION,
        predicted_at=datetime.now(timezone.utc),
        requested_by="pendiente-auth-iam",
        source="api_single",
        input_file=None,
    )

    logger.info(
        "predict_ok",
        extra={"json_fields": {
            "input": cliente.model_dump(),
            "output": resultado.model_dump(mode="json"),
        }},
    )

    return resultado
```
> `logger.info(...)` registra el input completo del cliente junto con el output completo, en un formato que Cloud Logging interpreta como campos buscables. Es lo que da trazabilidad real: poder reconstruir después qué datos produjeron qué predicción.

**Nota importante:** `requested_by` se queda como el texto fijo 

**9.3 — Verifica la sintaxis antes de reconstruir:**
en shell:
```bash
python3 -c "import ast; ast.parse(open('app/main.py').read()); print('OK')"
```

**9.4 — Reconstruye con un tag nuevo (no sobreescribas `:v1`, así queda historial):**

```bash
docker build -t us-central1-docker.pkg.dev/PROJECT_ID/churn-api-repo/churn-api:v2 .
docker push us-central1-docker.pkg.dev/PROJECT_ID/churn-api-repo/churn-api:v2
```

**9.5 — Redespliega con la imagen `:v2`** (mismo comando del Paso 8, solo cambia el tag):

```bash
gcloud run deploy churn-api \
  --image=us-central1-docker.pkg.dev/PROJECT_ID/churn-api-repo/churn-api:v2 \
  --region=us-central1 --no-allow-unauthenticated \
  --min-instances=0 --max-instances=2 --memory=512Mi --port=8080 \
  --service-account=churn-api-sa@PROJECT_ID.iam.gserviceaccount.com
```

**9.6 — Repite el Paso 7 (`/predict`)**, y confirma en Cloud Logging (consola de GCP → Logging → Explorador de registros, filtra por el servicio `churn-api`) que aparece la fila con el input y output completos.

---


## Paso 10 — Limpieza (al terminar)

```bash
gcloud run services delete churn-api --region=us-central1 --quiet
gcloud artifacts repositories delete churn-api-repo --location=us-central1 --quiet
```
Cloud Run con `min-instances=0` ya casi no cuesta nada estando desplegado, pero si no lo vas a seguir usando, bórralo para no dejar nada corriendo.

---

## Troubleshooting rápido

| Síntoma | Causa probable |
|---|---|
| `403` al llamar la API | Falta el token, o tu cuenta no tiene `roles/run.invoker` sobre el servicio |
| `422` al llamar `/predict` | Algún campo no coincide con el contrato (revisa `contract`/`payment_method` exactos) |
| `503` en `/health` | El modelo todavía no terminó de cargar — espera unos segundos |
| `docker push` falla con `connection refused` | Problema de red momentáneo — reintenta el mismo comando |
| `PERMISSION_DENIED: artifactregistry.repositories.create` | El rol correcto es `roles/artifactregistry.admin`, no `.repoAdmin` — ese último no incluye crear repositorios nuevos |
| Error dice literalmente `PROJECT_ID` o `TU_BUCKET` en el mensaje | Olvidaste reemplazar el placeholder por el valor real antes de correr el comando |
| Cloud Shell se desconectó | Los archivos en `$HOME` persisten, pero hay que reconstruir la imagen Docker desde cero (el motor de Docker no persiste) |




