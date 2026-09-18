# Comandos de evidencia — U5 Grupo 3

```bash
export PROJECT_ID=computacionnube20263
export REGION=us-central1
export SERVICE=u5-g03-cr-20260918
export SERVICE_URL=$(gcloud run services describe "$SERVICE" \
  --project="$PROJECT_ID" --region="$REGION" --format='value(status.url)')
export TOKEN=$(gcloud auth print-identity-token)
echo "$SERVICE_URL"
```

## Servicio activo y privado

```bash
gcloud run services list --project="$PROJECT_ID" --region="$REGION"
gcloud run services get-iam-policy "$SERVICE" --project="$PROJECT_ID" --region="$REGION"
```

La política no debe mostrar `allUsers`.

## Health — esperado HTTP 200

```bash
curl -sS -w "\nHTTP %{http_code}\n" \
  -H "Authorization: Bearer $TOKEN" "$SERVICE_URL/health"
```

Respuesta esperada: `status=ok`, `model_loaded=true` y `HTTP 200`.

## Predicción válida — esperado HTTP 200

```bash
curl -sS -w "\nHTTP %{http_code}\n" -X POST \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"customer_id":"TEST-VALID-001","gender":"Female","senior_citizen":false,"partner":true,"dependents":false,"tenure":12,"monthly_charges":89.5,"contract":"Month-to-month","payment_method":"Electronic check","internet_service":"Fiber optic","online_security":"No","tech_support":"No","paperless_billing":true}' \
  "$SERVICE_URL/predict"
```

## Validaciones 422

### Campo faltante (`monthly_charges`)

```bash
curl -sS -w "\nHTTP %{http_code}\n" -X POST \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"customer_id":"TEST-422-MISSING","gender":"Female","senior_citizen":false,"partner":true,"dependents":false,"tenure":12,"contract":"Month-to-month","payment_method":"Electronic check","internet_service":"Fiber optic","online_security":"No","tech_support":"No","paperless_billing":true}' \
  "$SERVICE_URL/predict"
```

### Enum inválido (`contract=Perpetuo`)

```bash
curl -sS -w "\nHTTP %{http_code}\n" -X POST \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"customer_id":"TEST-422-ENUM","gender":"Female","senior_citizen":false,"partner":true,"dependents":false,"tenure":12,"monthly_charges":89.5,"contract":"Perpetuo","payment_method":"Electronic check","internet_service":"Fiber optic","online_security":"No","tech_support":"No","paperless_billing":true}' \
  "$SERVICE_URL/predict"
```

### Tipo inválido (`tenure=veinte`)

```bash
curl -sS -w "\nHTTP %{http_code}\n" -X POST \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"customer_id":"TEST-422-TYPE","gender":"Female","senior_citizen":false,"partner":true,"dependents":false,"tenure":"veinte","monthly_charges":89.5,"contract":"Month-to-month","payment_method":"Electronic check","internet_service":"Fiber optic","online_security":"No","tech_support":"No","paperless_billing":true}' \
  "$SERVICE_URL/predict"
```

## Logging estructurado

En Cloud Logging usa estos filtros:

```text
resource.type="cloud_run_revision"
resource.labels.service_name="u5-g03-cr-20260918"
jsonPayload.message="predict_ok"
```

Repite cambiando `predict_ok` por `predict_422`. Captura las respuestas en `evidencias/` antes de eliminar el servicio.
