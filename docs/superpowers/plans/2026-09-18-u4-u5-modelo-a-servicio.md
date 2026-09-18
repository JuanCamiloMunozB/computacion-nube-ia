# Tarea "Modelo a servicio en producción" (U4 + U5) — Plan de implementación · Grupo 3

> **Para agentes ejecutores:** implementar tarea por tarea, en orden. Los pasos usan checkbox (`- [ ]`) para seguimiento. No saltar tareas: la Tarea 3 depende de un archivo que produce la Tarea 2.

**Goal:** Entrenar y seleccionar con evidencia la arquitectura ganadora sobre las 13 features de Tarea 1 (protegida = `gender`), y convertirla en un servicio FastAPI dockerizado y desplegado en Cloud Run con service account dedicada, sin acceso público y con logging estructurado.

**Architecture:** El notebook de U4 (ya escrito) entrena 3 arquitecturas con Optuna, produce el scorecard obligatorio + leaderboard 360, registra en Model Registry y emite un `handoff_u5_g03_20260918.json` con el contrato exacto. U5 consume ese JSON para construir `schemas.py` (contrato Pydantic + traducción a vector de features) y `main.py` (FastAPI con lifespan, `/health`, `/predict`, logging estructurado). Se prueba **local** primero, luego se dockeriza y despliega.

**Tech Stack:** BigQuery · Vertex AI (Experiments + Model Registry) · Optuna · XGBoost / LightGBM / scikit-learn · fairlearn · FastAPI · Pydantic v2 · Docker · Artifact Registry · Cloud Run

**Spec:** Enunciado "Tarea: modelo a servicio en producción" (INTU, Unidad 5) + `Guia_Lab_Unidad5.md` (guía de la profesora) + `UNIDAD4_LAB_clase.ipynb` (plantilla de métricas obligatorias)

---

## Global Constraints

Estas reglas aplican a **todas** las tareas. Copiadas literal del enunciado:

- **Features:** exactamente las 13 de Tarea 1 (U3 sección 10). *"Las features son las que ya seleccionaron y justificaron, no se agregan nuevas sin justificación adicional."* → `SeniorCitizen` **se queda**.
- **Variable protegida:** `gender`. *"La variable protegida es la de genero."* → NO `SeniorCitizen`.
- **Arquitecturas:** *"al menos dos arquitecturas... con su propia búsqueda de hiperparámetros para cada una, no un solo entrenamiento suelto."*
- **Scorecard obligatorio:** AUC, Recall, DPD, EOD (sobre género), y costo de negocio **en dólares**.
- **Selección:** *"se elige con un leaderboard 360"*.
- **Registro:** *"se registran los mejores en Model Registry"* (plural).
- **Cloud Run:** service account dedicada, **sin acceso público** (`--no-allow-unauthenticated`), y **logging estructurado DESDE el principio, no como agregado de último momento**.
- **Pruebas:** 4 casos — 1 válido que prediga, y varios que disparen **422**.
- **Limpieza:** *"solo apagen y borren la instancia, no borren el bucket, ni el model registry ni los otros artefactos."*
- **Nomenclatura:** `u4_gNN_<tipo>_YYYYMMDD` / `u5-gNN-<tipo>-YYYYMMDD`. Grupo = `g03`, fecha = `20260918`.
- **Deadline:** 2026-09-19 06:00. Quedan **menos de 24 horas** — por eso las Tareas 3 y 4 prueban en local antes de gastar ciclos de build/push/deploy (cada ciclo cuesta ~10 min).

### Valores fijos del proyecto

```
GROUP_NUM   = g03
FECHA       = 20260918
PROJECT_ID  = computacionnube20261     # ← VERIFICAR en consola antes de correr (Tarea 1, Paso 1)
REGION      = us-central1
SOURCE      = computacionnube20261.u3_master.telco_churn_raw
BUCKET      = computacionnube20261-u4-g03-mdl-20260918
```

### Nomenclatura de recursos U5

```
Artifact Registry repo : u5-g03-repo-20260918
Imagen                 : u5-g03-img-20260918
Service account        : u5-g03-sa-20260918
Servicio Cloud Run     : u5-g03-cr-20260918
```

> ⚠️ **Verificar contra el documento oficial de pautas de nomenclatura del curso antes de crear recursos.** No tengo ese documento; estos nombres siguen el patrón `u4_gNN_<tipo>_YYYYMMDD` de la plantilla, adaptado a U5 (guiones porque Cloud Run y Artifact Registry no aceptan guion bajo).

---

## Estructura de archivos

| Archivo | Responsabilidad | Estado |
|---|---|---|
| `u4-g03-nb-20260918.ipynb` | Entrenamiento, scorecard, leaderboard 360, Model Registry, handoff | ✅ escrito, **falta ejecutar** |
| `handoff_u5_g03_20260918.json` | Contrato exacto U4→U5 (feature order, categorías, versiones, smoke test) | lo produce Tarea 1 |
| `service/app/__init__.py` | Hace de `app` un paquete importable | crear (Tarea 2) |
| `service/app/schemas.py` | Contrato Pydantic + traducción a vector de features | crear (Tarea 2) |
| `service/app/main.py` | FastAPI: lifespan, `/health`, `/predict`, logging estructurado | crear (Tarea 3) |
| `service/requirements.txt` | Dependencias con **versiones fijas del notebook** | crear (Tarea 3) |
| `service/Dockerfile` | Imagen del servicio | crear (Tarea 5) |
| `service/tests/test_schemas.py` | Tests locales del contrato (422 + alineación de vector) | crear (Tarea 2) |
| `evidencias/` | Capturas de pantalla de la entrega | ya creada |

> Los archivos `main.py`, `schemas.py`, `Dockerfile`, `requirements.txt` que están **en la raíz** del repo son de una sesión anterior, escritos para el modelo viejo (9 columnas, protegida `SeniorCitizen`). **No se editan: se dejan quietos y se crea `service/` nuevo.** Al final se copian los dos entregables a la raíz (Tarea 8).

---

## Task 1: Ejecutar el notebook de U4 y capturar el handoff

**Files:**
- Ejecutar: `u4-g03-nb-20260918.ipynb` (en Workbench)
- Produce: `handoff_u5_g03_20260918.json`, `leaderboard360_g03_20260918.png`

**Interfaces:**
- Produces: el JSON de handoff con las llaves `feature_order` (lista de strings), `categorias_crudas` (dict), `categoria_base_drop_first` (dict), `model_gcs_uri` (string), `model_version` (string), `versiones` (dict), `smoke_test.features` (dict) y `smoke_test.proba_esperada` (float). Las Tareas 2 y 3 leen exactamente estas llaves.

- [ ] **Paso 1: Verificar el PROJECT_ID real**

En la consola de GCP, click en el selector de proyecto → copiar el ID del popup.
Si **no** es `computacionnube20261`, editar la celda de configuración (celda 5) del notebook antes de correr nada.

- [ ] **Paso 2: Crear la instancia de Workbench**

```bash
gcloud workbench instances create u4-g03 \
  --project=computacionnube20261 \
  --location=us-central1-a \
  --machine-type=e2-standard-2 \
  --metadata=idle-timeout-seconds=2700
```

Esperado: la instancia tarda varios minutos en pasar a `RUNNING`. Cuando lo esté, "Open JupyterLab".

- [ ] **Paso 3: Subir el notebook y completar los integrantes**

Subir `u4-g03-nb-20260918.ipynb` con el botón de subir de JupyterLab. Abrirlo y llenar el campo `**Integrantes:** _(completar)_` de la primera celda.

- [ ] **Paso 4: Correr las celdas 4 a 22 (hasta el leaderboard)**

Celda por celda, **no** "Run All". Las 3 búsquedas de Optuna (celdas 15, 17, 19) tardan ~2-5 min cada una.

Verificación en la celda 9 (feature engineering) — el output debe listar **18 columnas** y contener `gender_Male`.

El conteo esperado: 3 numéricas que pasan directo (`SeniorCitizen`, `tenure`, `MonthlyCharges`) + 15 del one-hot con `drop_first=True` → `gender`(1) + `Partner`(1) + `Dependents`(1) + `PaperlessBilling`(1) + `Contract`(2) + `PaymentMethod`(3) + `InternetService`(2) + `OnlineSecurity`(2) + `TechSupport`(2) = **18 en total**.

Si sale un número distinto, alguna categórica trajo un valor inesperado de BigQuery — inspeccionar con `df[c].unique()` antes de seguir, porque ese conteo tiene que cuadrar con `FEATURE_ORDER` en la Tarea 2.

Si el `assert PROTECTED_VAR_ENC in X_encoded.columns` falla, es que `gender` llegó con otros valores; inspeccionar `df['gender'].unique()`.

- [ ] **Paso 5: Leer el leaderboard antes de seguir**

La celda 22 imprime la tabla con `Score_final`. Verificar:
- Al menos una arquitectura tiene `Score_final > -1` (pasa `EOD ≤ 0.2`).
- `Costo_negocio_USD` no es `0` ni `NaN`.
- `Costo_equidad_ratio` puede salir `None` — eso pasa cuando mitigar **no** costó AUC (mejoró o empató). No es un bug; anotarlo como hallazgo en la justificación.

Si **ninguna** arquitectura pasa el filtro, no continuar al registro: revisar que `sample_weights_train` se esté calculando sobre `gender_Male` y no sobre otra columna.

- [ ] **Paso 6: Correr el leaderboard 360 (celdas 23-24)**

Produce `leaderboard360_g03_20260918.png`. **Esta figura es la justificación visual que pide el enunciado** — guardarla.

- [ ] **Paso 7: Correr Experiments y Model Registry (celdas 25-28)**

Si `aiplatform.Model.upload` falla para LightGBM o LogReg por el `serving_container_image_uri`, **no es bloqueante** (en U4 no se crea Endpoint). Registrar al menos la ganadora. Anotar el fallo como limitación conocida en la entrega.

- [ ] **Paso 8: Correr el handoff (celdas 29-30) y descargar los artefactos**

Descargar de JupyterLab (click derecho → Download):
1. `handoff_u5_g03_20260918.json`
2. `leaderboard360_g03_20260918.png`
3. El notebook ejecutado con outputs

- [ ] **Paso 9: Capturar evidencia de U4**

Screenshot del leaderboard (celda 22) y del radar (celda 24) → guardar en `evidencias/`.

- [ ] **Paso 10: NO borrar nada todavía**

La instancia se borra al final de todo (Tarea 8), no ahora — por si hay que reentrenar.

---

## Task 2: Contrato `schemas.py` con tests locales

**Files:**
- Create: `service/app/__init__.py` (vacío)
- Create: `service/app/schemas.py`
- Create: `service/tests/test_schemas.py`
- Lee: `handoff_u5_g03_20260918.json`

**Interfaces:**
- Consumes: `handoff_u5_g03_20260918.json` de la Tarea 1.
- Produces: `FEATURE_ORDER: list[str]`, `ClienteInput` (Pydantic `BaseModel` con método `to_feature_vector() -> list[float]`), `PrediccionOutput`, `HealthOutput`, y los enums `Gender`, `Contract`, `PaymentMethod`, `InternetService`, `YesNoNoInternet`. La Tarea 3 importa exactamente estos nombres desde `app.schemas`.

> **Por qué esta tarea tiene tests de verdad:** el modelo recibe un **array posicional**. Si el orden o un nombre no coincide, XGBoost/LightGBM **no lanzan error** — predicen mal en silencio. Un test local de 30 segundos evita descubrirlo después de tres ciclos de deploy.

- [x] **Paso 1: Crear la estructura y el paquete**

```bash
mkdir -p service/app service/tests
touch service/app/__init__.py
```

`__init__.py` va **vacío**, pero debe existir: `main.py` importa `from app.schemas import ...` y sin él el import dentro del contenedor es frágil.

- [x] **Paso 2: Leer el handoff y anotar los valores reales**

```bash
python3 -c "
import json
h = json.load(open('handoff_u5_g03_20260918.json'))
print('FEATURE_ORDER:'); [print('   ', c) for c in h['feature_order']]
print('CATEGORIAS:'); [print('   ', k, v) for k, v in h['categorias_crudas'].items()]
print('BASE (drop_first):', h['categoria_base_drop_first'])
print('VERSIONES:', h['versiones'])
"
```

**Regla de oro del one-hot:** `pd.get_dummies(..., drop_first=True)` elimina la **primera categoría en orden alfabético**, y esa categoría queda representada como *todas las columnas de ese grupo en 0*. Valores esperados para este dataset:

| Columna cruda | Categorías | Base eliminada | Columnas que SÍ existen |
|---|---|---|---|
| `gender` | Female, Male | `Female` | `gender_Male` |
| `Partner` | False, True | `False` | `Partner_True` |
| `Dependents` | False, True | `False` | `Dependents_True` |
| `PaperlessBilling` | False, True | `False` | `PaperlessBilling_True` |
| `Contract` | Month-to-month, One year, Two year | `Month-to-month` | `Contract_One_year`, `Contract_Two_year` |
| `PaymentMethod` | Bank transfer (automatic), Credit card (automatic), Electronic check, Mailed check | `Bank transfer (automatic)` | `PaymentMethod_Credit_card__automatic_`, `PaymentMethod_Electronic_check`, `PaymentMethod_Mailed_check` |
| `InternetService` | DSL, Fiber optic, No | `DSL` | `InternetService_Fiber_optic`, `InternetService_No` |
| `OnlineSecurity` | No, No internet service, Yes | `No` | `OnlineSecurity_No_internet_service`, `OnlineSecurity_Yes` |
| `TechSupport` | No, No internet service, Yes | `No` | `TechSupport_No_internet_service`, `TechSupport_Yes` |

Los nombres pasaron por `re.sub(r'[^0-9a-zA-Z_]', '_', col)`: espacios, paréntesis y guiones se vuelven `_`. Por eso `Credit card (automatic)` → `Credit_card__automatic_` (doble `_` donde estaban espacio+paréntesis).

**Si el handoff contradice esta tabla, gana el handoff.**

- [x] **Paso 3: Escribir el test que falla**

Crear `service/tests/test_schemas.py`:

```python
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas import FEATURE_ORDER, ClienteInput

# Los tests corren desde service/, y el handoff vive en la raiz del repo.
HANDOFF = json.loads(Path(__file__).parent.parent.parent.joinpath("handoff_u5_g03_20260918.json").read_text())


def _cliente_valido(**overrides):
    base = {
        "customer_id": "TEST-001",
        "gender": "Female",
        "senior_citizen": False,
        "partner": True,
        "dependents": False,
        "tenure": 12,
        "monthly_charges": 89.5,
        "contract": "Month-to-month",
        "payment_method": "Electronic check",
        "internet_service": "Fiber optic",
        "online_security": "No",
        "tech_support": "No",
        "paperless_billing": True,
    }
    base.update(overrides)
    return base


def test_feature_order_coincide_con_el_modelo_entrenado():
    """El orden de features DEBE ser identico al del notebook, o el modelo predice mal en silencio."""
    assert FEATURE_ORDER == HANDOFF["feature_order"]


def test_vector_tiene_el_largo_correcto():
    cliente = ClienteInput(**_cliente_valido())
    assert len(cliente.to_feature_vector()) == len(FEATURE_ORDER)


def test_categoria_base_produce_ceros():
    """Month-to-month es la categoria base de Contract: ambas columnas Contract_* deben ser 0."""
    cliente = ClienteInput(**_cliente_valido(contract="Month-to-month"))
    vector = dict(zip(FEATURE_ORDER, cliente.to_feature_vector()))
    assert vector["Contract_One_year"] == 0.0
    assert vector["Contract_Two_year"] == 0.0


def test_categoria_no_base_activa_su_columna():
    cliente = ClienteInput(**_cliente_valido(contract="Two year"))
    vector = dict(zip(FEATURE_ORDER, cliente.to_feature_vector()))
    assert vector["Contract_Two_year"] == 1.0
    assert vector["Contract_One_year"] == 0.0


def test_gender_female_es_la_base():
    """Female es la categoria base -> gender_Male = 0."""
    cliente = ClienteInput(**_cliente_valido(gender="Female"))
    vector = dict(zip(FEATURE_ORDER, cliente.to_feature_vector()))
    assert vector["gender_Male"] == 0.0

    cliente = ClienteInput(**_cliente_valido(gender="Male"))
    vector = dict(zip(FEATURE_ORDER, cliente.to_feature_vector()))
    assert vector["gender_Male"] == 1.0


def test_422_campo_faltante():
    datos = _cliente_valido()
    del datos["monthly_charges"]
    with pytest.raises(ValidationError):
        ClienteInput(**datos)


def test_422_enum_invalido():
    with pytest.raises(ValidationError):
        ClienteInput(**_cliente_valido(contract="Perpetuo"))


def test_422_tipo_invalido():
    with pytest.raises(ValidationError):
        ClienteInput(**_cliente_valido(tenure="veinte"))


def test_422_rango_invalido():
    with pytest.raises(ValidationError):
        ClienteInput(**_cliente_valido(monthly_charges=-5.0))
```

- [x] **Paso 4: Correr los tests para verificar que fallan**

```bash
cd service && python3 -m pytest tests/test_schemas.py -v
```

Esperado: `ModuleNotFoundError: No module named 'app.schemas'` (aún no existe).

- [x] **Paso 5: Escribir `service/app/schemas.py`**

```python
"""Contrato de entrada/salida del servicio churn-api (U5) -- Grupo 3.

Refleja las 13 features seleccionadas y justificadas en la Tarea 1 (U3, seccion 10).
Los enums cierran el dominio de las categoricas -> FastAPI devuelve 422
automaticamente cuando un valor cae fuera del dominio esperado.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field

# Orden EXACTO que espera el modelo entrenado en U4.
# Fuente: handoff_u5_g03_20260918.json["feature_order"] -- NO editar a mano.
FEATURE_ORDER = [
    "SeniorCitizen",
    "tenure",
    "MonthlyCharges",
    "gender_Male",
    "Partner_True",
    "Dependents_True",
    "Contract_One_year",
    "Contract_Two_year",
    "PaymentMethod_Credit_card__automatic_",
    "PaymentMethod_Electronic_check",
    "PaymentMethod_Mailed_check",
    "InternetService_Fiber_optic",
    "InternetService_No",
    "OnlineSecurity_No_internet_service",
    "OnlineSecurity_Yes",
    "TechSupport_No_internet_service",
    "TechSupport_Yes",
    "PaperlessBilling_True",
]


class Gender(str, Enum):
    female = "Female"
    male = "Male"


class Contract(str, Enum):
    month_to_month = "Month-to-month"
    one_year = "One year"
    two_year = "Two year"


class PaymentMethod(str, Enum):
    bank_transfer = "Bank transfer (automatic)"
    credit_card = "Credit card (automatic)"
    electronic_check = "Electronic check"
    mailed_check = "Mailed check"


class InternetService(str, Enum):
    dsl = "DSL"
    fiber_optic = "Fiber optic"
    no = "No"


class YesNoNoInternet(str, Enum):
    """OnlineSecurity y TechSupport comparten este dominio."""
    yes = "Yes"
    no = "No"
    no_internet_service = "No internet service"


class ClienteInput(BaseModel):
    """Lo que manda el CRM: datos crudos del cliente, en lenguaje de negocio."""

    customer_id: str = Field(..., min_length=1, max_length=64,
                             description="ID del cliente en el CRM. No entra al modelo, solo trazabilidad.")
    gender: Gender = Field(..., description="Male | Female. Variable protegida de la auditoria de U3.")
    senior_citizen: bool = Field(..., description="Cliente adulto mayor")
    partner: bool = Field(..., description="Tiene pareja registrada")
    dependents: bool = Field(..., description="Tiene dependientes")
    tenure: int = Field(..., ge=0, le=100, description="Meses de antiguedad como cliente")
    monthly_charges: float = Field(..., gt=0.0, le=200.0, description="Cargo mensual en USD")
    contract: Contract
    payment_method: PaymentMethod
    internet_service: InternetService
    online_security: YesNoNoInternet
    tech_support: YesNoNoInternet
    paperless_billing: bool = Field(..., description="Factura electronica")

    def to_feature_vector(self) -> list[float]:
        """Traduce el input de negocio al vector posicional EXACTO que espera el modelo.

        Replica pd.get_dummies(..., drop_first=True) del notebook de U4: la primera
        categoria alfabetica de cada grupo es la BASE y se representa con todas las
        columnas de ese grupo en 0.
        """
        fila = {
            "SeniorCitizen": float(self.senior_citizen),
            "tenure": float(self.tenure),
            "MonthlyCharges": float(self.monthly_charges),
            # base: Female
            "gender_Male": 1.0 if self.gender == Gender.male else 0.0,
            # base: False
            "Partner_True": float(self.partner),
            "Dependents_True": float(self.dependents),
            "PaperlessBilling_True": float(self.paperless_billing),
            # base: Month-to-month
            "Contract_One_year": 1.0 if self.contract == Contract.one_year else 0.0,
            "Contract_Two_year": 1.0 if self.contract == Contract.two_year else 0.0,
            # base: Bank transfer (automatic)
            "PaymentMethod_Credit_card__automatic_": 1.0 if self.payment_method == PaymentMethod.credit_card else 0.0,
            "PaymentMethod_Electronic_check": 1.0 if self.payment_method == PaymentMethod.electronic_check else 0.0,
            "PaymentMethod_Mailed_check": 1.0 if self.payment_method == PaymentMethod.mailed_check else 0.0,
            # base: DSL
            "InternetService_Fiber_optic": 1.0 if self.internet_service == InternetService.fiber_optic else 0.0,
            "InternetService_No": 1.0 if self.internet_service == InternetService.no else 0.0,
            # base: No
            "OnlineSecurity_No_internet_service": 1.0 if self.online_security == YesNoNoInternet.no_internet_service else 0.0,
            "OnlineSecurity_Yes": 1.0 if self.online_security == YesNoNoInternet.yes else 0.0,
            "TechSupport_No_internet_service": 1.0 if self.tech_support == YesNoNoInternet.no_internet_service else 0.0,
            "TechSupport_Yes": 1.0 if self.tech_support == YesNoNoInternet.yes else 0.0,
        }
        # Construir en FEATURE_ORDER explicitamente -- nunca confiar en el orden del dict.
        return [fila[col] for col in FEATURE_ORDER]

    model_config = {
        "json_schema_extra": {
            "example": {
                "customer_id": "TEST-001",
                "gender": "Female",
                "senior_citizen": False,
                "partner": True,
                "dependents": False,
                "tenure": 12,
                "monthly_charges": 89.5,
                "contract": "Month-to-month",
                "payment_method": "Electronic check",
                "internet_service": "Fiber optic",
                "online_security": "No",
                "tech_support": "No",
                "paperless_billing": True,
            }
        }
    }


class PrediccionOutput(BaseModel):
    """Lo que responde la API."""

    customer_id: str = Field(..., description="Trazabilidad: de que cliente es esta prediccion")
    customer_risk_score: float = Field(..., ge=0.0, le=1.0, description="Probabilidad de churn, 0-1")
    predicted_churn: bool = Field(..., description="True si customer_risk_score >= 0.5")
    model_version: str = Field(..., description="Trazabilidad: que modelo genero esta prediccion")
    predicted_at: datetime = Field(..., description="Timestamp UTC de la prediccion")
    requested_by: str = Field(..., description="Identidad que llamo la API (header de Cloud Run)")
    source: Literal["api_single", "api_batch"] = Field(..., description="Origen de la peticion")
    input_file: Optional[str] = Field(None, description="Archivo de origen, solo si source='api_batch'")


class HealthOutput(BaseModel):
    status: Literal["ok", "degraded"] = "ok"
    model_loaded: bool
    model_version: Optional[str] = None
```

> **`FEATURE_ORDER` de arriba es una hipótesis basada en el orden en que pandas genera las columnas.** El Paso 6 lo corrige contra el valor real del handoff. No saltarse el Paso 6.

- [x] **Paso 6: Sincronizar `FEATURE_ORDER` con el handoff real**

```bash
cd service && python3 -c "
import json
h = json.load(open('../handoff_u5_g03_20260918.json'))
print('FEATURE_ORDER = [')
for c in h['feature_order']:
    print(f'    \"{c}\",')
print(']')
"
```

Copiar esa salida y **reemplazar** el bloque `FEATURE_ORDER` de `schemas.py`. Si algún nombre difiere de los usados dentro de `to_feature_vector()`, corregir también las llaves del dict `fila` para que coincidan exactamente.

- [x] **Paso 7: Correr los tests hasta que pasen**

```bash
cd service && python3 -m pytest tests/test_schemas.py -v
```

Esperado: 9 passed. Si `test_feature_order_coincide_con_el_modelo_entrenado` falla, el Paso 6 no se hizo bien — no continuar.

---

## Task 3: Servicio `main.py` con logging estructurado

**Files:**
- Create: `service/app/main.py`
- Create: `service/requirements.txt`

**Interfaces:**
- Consumes: `FEATURE_ORDER`, `ClienteInput`, `PrediccionOutput`, `HealthOutput` de `app.schemas` (Tarea 2).
- Produces: objeto FastAPI `app` con `GET /health` y `POST /predict`. La Tarea 4 lo levanta con `uvicorn app.main:app`.

> El enunciado exige logging estructurado **desde el principio**. La guía de la profesora lo pone como Paso 9 (agregado al final) — aquí va incluido desde la primera versión, que es lo que pide la tarea.

- [x] **Paso 1: Escribir `service/requirements.txt` con las versiones del handoff**

```bash
python3 -c "
import json
h = json.load(open('handoff_u5_g03_20260918.json'))
print('# Versiones EXACTAS del entorno de entrenamiento (Workbench, U4).')
print('# Si difieren, joblib.load puede fallar o el modelo predecir distinto.')
for lib, ver in h['versiones'].items():
    print(f'{lib}=={ver}')
" > service/requirements.txt

cat >> service/requirements.txt <<'EOF'
joblib==1.6.0
numpy
pandas
fastapi==0.141.1
uvicorn[standard]==0.52.4
pydantic==2.12.4
google-cloud-storage==3.13.1
EOF

cat service/requirements.txt
```

Verificar que quedaron las tres líneas `scikit-learn==`, `xgboost==`, `lightgbm==` con versiones reales.

- [x] **Paso 2: Escribir `service/app/main.py`**

```python
"""Servicio de inferencia de churn -- Unidad 5, Grupo 3.

Carga el modelo ganador de U4 una sola vez al arrancar (lifespan) y expone
/health y /predict. Logging estructurado en JSON desde el arranque, para que
Cloud Logging lo indexe como campos buscables.
"""
from __future__ import annotations

import json as _json
import logging
import os
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import joblib
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.schemas import FEATURE_ORDER, ClienteInput, HealthOutput, PrediccionOutput

MODEL_GCS_URI = os.getenv("MODEL_GCS_URI", "")
MODEL_LOCAL_PATH = os.getenv("MODEL_LOCAL_PATH", "/tmp/model.joblib")
MODEL_VERSION = os.getenv("MODEL_VERSION", "u4-g03-mdl-20260918")
UMBRAL_DECISION = float(os.getenv("UMBRAL_DECISION", "0.5"))


class StructuredFormatter(logging.Formatter):
    """Formato que Cloud Logging interpreta como campos buscables (jsonPayload)."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "severity": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if hasattr(record, "json_fields"):
            payload.update(record.json_fields)
        return _json.dumps(payload, default=str)


def _init_logger() -> logging.Logger:
    log = logging.getLogger("churn-api")
    log.setLevel(logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(StructuredFormatter())
    log.handlers = [handler]
    log.propagate = False
    return log


logger = _init_logger()


class ModelState:
    def __init__(self) -> None:
        self.modelo = None
        self.error: Optional[str] = None
        self.loaded_at: Optional[datetime] = None

    def is_ready(self) -> bool:
        return self.modelo is not None and self.error is None


def _descargar_de_gcs(gcs_uri: str, destino: str) -> str:
    from google.cloud import storage

    if not gcs_uri.startswith("gs://"):
        raise ValueError(f"MODEL_GCS_URI mal formado: {gcs_uri}")
    bucket_name, _, blob_path = gcs_uri.removeprefix("gs://").partition("/")
    client = storage.Client()
    client.bucket(bucket_name).blob(blob_path).download_to_filename(destino)
    return destino


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Carga el modelo UNA vez al arrancar, no en cada request."""
    state = ModelState()
    app.state.model = state
    try:
        ruta = MODEL_LOCAL_PATH
        if MODEL_GCS_URI and not Path(ruta).exists():
            ruta = _descargar_de_gcs(MODEL_GCS_URI, MODEL_LOCAL_PATH)
        state.modelo = joblib.load(ruta)
        state.loaded_at = datetime.now(timezone.utc)
        logger.info(
            "startup_model_loaded",
            extra={"json_fields": {
                "model_version": MODEL_VERSION,
                "gcs_uri": MODEL_GCS_URI,
                "n_features": len(FEATURE_ORDER),
                "umbral": UMBRAL_DECISION,
            }},
        )
    except Exception as e:
        state.error = str(e)
        logger.error(
            "startup_model_load_failed",
            extra={"json_fields": {"error": str(e), "gcs_uri": MODEL_GCS_URI}},
        )
    yield
    app.state.model = None


app = FastAPI(
    title="Churn API - Grupo 3",
    version="1.0.0",
    description="Servicio de prediccion de churn. Modelo ganador de U4, 13 features de Tarea 1, protegida=gender.",
    lifespan=lifespan,
)


@app.get("/health", response_model=HealthOutput)
def health(request: Request) -> HealthOutput:
    """Cloud Run usa esto para saber si el servicio esta vivo y listo."""
    state: ModelState = request.app.state.model
    if state is None or not state.is_ready():
        detalle = state.error if state and state.error else "modelo aun no cargado"
        raise HTTPException(status_code=503, detail=detalle)
    return HealthOutput(status="ok", model_loaded=True, model_version=MODEL_VERSION)


@app.post("/predict", response_model=PrediccionOutput)
def predict(cliente: ClienteInput, request: Request) -> PrediccionOutput:
    """Predice churn para un cliente.

    200: prediccion  |  422: el input no cumple el contrato  |  503: modelo no disponible
    """
    state: ModelState = request.app.state.model
    if state is None or not state.is_ready():
        logger.error("predict_model_unavailable",
                     extra={"json_fields": {"error": state.error if state else "state=None"}})
        raise HTTPException(status_code=503, detail="Modelo no disponible")

    try:
        vector = cliente.to_feature_vector()
        proba = float(state.modelo.predict_proba([vector])[0][1])
    except Exception as e:
        logger.error("predict_error",
                     extra={"json_fields": {"customer_id": cliente.customer_id, "error": str(e)}})
        raise HTTPException(status_code=500, detail="Error interno al generar la prediccion.")

    resultado = PrediccionOutput(
        customer_id=cliente.customer_id,
        customer_risk_score=round(proba, 4),
        predicted_churn=bool(proba >= UMBRAL_DECISION),
        model_version=MODEL_VERSION,
        predicted_at=datetime.now(timezone.utc),
        requested_by=request.headers.get("x-goog-authenticated-user-email", "unknown"),
        source="api_single",
        input_file=None,
    )

    logger.info(
        "predict_ok",
        extra={"json_fields": {
            "input": cliente.model_dump(mode="json"),
            "output": resultado.model_dump(mode="json"),
        }},
    )
    return resultado


@app.exception_handler(RequestValidationError)
async def _log_422(request: Request, exc: RequestValidationError):
    """Loguea los rechazos por contrato -- evidencia de que el contrato protege."""
    logger.warning(
        "predict_422",
        extra={"json_fields": {"errors": exc.errors(), "path": request.url.path}},
    )
    return JSONResponse(status_code=422, content={"detail": _json.loads(_json.dumps(exc.errors(), default=str))})
```

- [x] **Paso 3: Verificar que el archivo es sintácticamente válido**

```bash
cd service && python3 -c "import ast; ast.parse(open('app/main.py').read()); print('OK')"
```

Esperado: `OK`

---

## Task 4: Probar el servicio en LOCAL antes de dockerizar

**Files:**
- Modify: ninguno (solo ejecución)
- Usa: el `.joblib` del modelo ganador, descargado a local

> **Por qué esta tarea existe:** cada ciclo build→push→deploy cuesta ~10 minutos. Descubrir aquí que un nombre de columna está mal cuesta 30 segundos. Con el deadline encima, esta tarea **ahorra horas**.

- [x] **Paso 1: Bajar el modelo ganador a local**

```bash
cd service
gcloud storage cp "$(python3 -c "import json;print(json.load(open('../handoff_u5_g03_20260918.json'))['model_gcs_uri'])")" /tmp/model.joblib
ls -lh /tmp/model.joblib
```

- [x] **Paso 2: Instalar dependencias en un venv**

```bash
cd service
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt pytest
```

- [x] **Paso 3: Verificar que el smoke test del handoff reproduce**

```bash
cd service && python3 -c "
import json, joblib
from app.schemas import FEATURE_ORDER
h = json.load(open('../handoff_u5_g03_20260918.json'))
modelo = joblib.load('/tmp/model.joblib')
vector = [h['smoke_test']['features'][c] for c in FEATURE_ORDER]
obtenido = float(modelo.predict_proba([vector])[0][1])
esperado = h['smoke_test']['proba_esperada']
print(f'esperado={esperado:.6f}  obtenido={obtenido:.6f}')
assert abs(obtenido - esperado) < 1e-6, 'DESALINEACION: el vector no coincide con el entrenamiento'
print('OK -- FEATURE_ORDER alineado con el modelo')
"
```

Esperado: `OK -- FEATURE_ORDER alineado con el modelo`.
Si falla: `FEATURE_ORDER` o las llaves de `to_feature_vector()` no coinciden con el notebook. **Arreglar antes de seguir** — este es el bug que predice mal en silencio.

- [x] **Paso 4: Levantar el servicio local**

```bash
cd service && MODEL_LOCAL_PATH=/tmp/model.joblib uvicorn app.main:app --port 8080
```

En otra terminal, probar `/health`:

```bash
curl -s localhost:8080/health
```

Esperado: `{"status":"ok","model_loaded":true,"model_version":"..."}`

- [x] **Paso 5: Probar los 4 casos en local**

```bash
# Caso 1 -- VALIDO (espera 200)
curl -s -w "\nHTTP %{http_code}\n" -X POST localhost:8080/predict \
  -H "Content-Type: application/json" \
  -d '{"customer_id":"TEST-VALID-001","gender":"Female","senior_citizen":false,"partner":true,"dependents":false,"tenure":12,"monthly_charges":89.5,"contract":"Month-to-month","payment_method":"Electronic check","internet_service":"Fiber optic","online_security":"No","tech_support":"No","paperless_billing":true}'

# Caso 2 -- 422 campo faltante (falta monthly_charges)
curl -s -w "\nHTTP %{http_code}\n" -X POST localhost:8080/predict \
  -H "Content-Type: application/json" \
  -d '{"customer_id":"TEST-422-MISSING","gender":"Female","senior_citizen":false,"partner":true,"dependents":false,"tenure":12,"contract":"Month-to-month","payment_method":"Electronic check","internet_service":"Fiber optic","online_security":"No","tech_support":"No","paperless_billing":true}'

# Caso 3 -- 422 enum fuera de dominio
curl -s -w "\nHTTP %{http_code}\n" -X POST localhost:8080/predict \
  -H "Content-Type: application/json" \
  -d '{"customer_id":"TEST-422-ENUM","gender":"Female","senior_citizen":false,"partner":true,"dependents":false,"tenure":12,"monthly_charges":89.5,"contract":"Perpetuo","payment_method":"Electronic check","internet_service":"Fiber optic","online_security":"No","tech_support":"No","paperless_billing":true}'

# Caso 4 -- 422 tipo invalido
curl -s -w "\nHTTP %{http_code}\n" -X POST localhost:8080/predict \
  -H "Content-Type: application/json" \
  -d '{"customer_id":"TEST-422-TYPE","gender":"Female","senior_citizen":false,"partner":true,"dependents":false,"tenure":"veinte","monthly_charges":89.5,"contract":"Month-to-month","payment_method":"Electronic check","internet_service":"Fiber optic","online_security":"No","tech_support":"No","paperless_billing":true}'
```

Esperado: `HTTP 200`, `HTTP 422`, `HTTP 422`, `HTTP 422`.
En la terminal de uvicorn deben verse líneas JSON con `"message": "predict_ok"` y `"message": "predict_422"`.

**No continuar a Docker hasta que los 4 casos den el código esperado.**

---

## Task 5: Dockerizar

**Files:**
- Create: `service/Dockerfile`

- [x] **Paso 1: Escribir `service/Dockerfile`**

```dockerfile
FROM python:3.12-slim

# libgomp1: XGBoost y LightGBM dependen de OpenMP -- no viene en la imagen slim
# y sin el, el import del modelo falla dentro del contenedor.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# requirements ANTES del codigo -> Docker cachea esta capa
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

EXPOSE 8080
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

- [x] **Paso 2: Construir y probar la imagen en local**

```bash
cd service
docker build -t churn-api-local:test .
docker run --rm -p 8080:8080 \
  -v /tmp/model.joblib:/tmp/model.joblib \
  -e MODEL_LOCAL_PATH=/tmp/model.joblib \
  churn-api-local:test
```

En otra terminal: `curl -s localhost:8080/health` → esperado `{"status":"ok",...}`.

Si el contenedor arranca pero `/health` da 503, revisar los logs: casi siempre es desajuste de versión de sklearn/xgboost entre el notebook y `requirements.txt` (Tarea 3, Paso 1).

---

## Task 6: Desplegar a Cloud Run

**Files:** ninguno (todo por `gcloud`, desde Cloud Shell)

- [x] **Paso 1: Subir el código a Cloud Shell**

Subir la carpeta `service/` completa (o clonar el repo). Verificar la estructura:

```bash
cd service && ls -la && ls -la app/
```

Debe verse `Dockerfile`, `requirements.txt`, y dentro de `app/`: `__init__.py`, `main.py`, `schemas.py`.

- [x] **Paso 2: Crear el repositorio de Artifact Registry**

```bash
export PROJECT_ID=computacionnube20261
gcloud artifacts repositories create u5-g03-repo-20260918 \
  --repository-format=docker \
  --location=us-central1 \
  --description="Imagenes de churn-api del Grupo 3"

gcloud auth configure-docker us-central1-docker.pkg.dev
```

Si da `PERMISSION_DENIED: artifactregistry.repositories.create`, el rol necesario es `roles/artifactregistry.admin` — pedirlo a la profesora.

- [x] **Paso 3: Build y push**

```bash
export IMG=us-central1-docker.pkg.dev/${PROJECT_ID}/u5-g03-repo-20260918/u5-g03-img-20260918:v1
docker build -t ${IMG} .
docker push ${IMG}
```

Si `docker push` falla con `connection refused`, reintentar el mismo comando; si persiste, repetir `gcloud auth configure-docker us-central1-docker.pkg.dev` y reintentar.

- [x] **Paso 4: Crear la service account dedicada y darle SOLO lectura del bucket**

```bash
gcloud iam service-accounts create u5-g03-sa-20260918 \
  --display-name="Service account para churn-api del Grupo 3"

gcloud storage buckets add-iam-policy-binding \
  gs://${PROJECT_ID}-u4-g03-mdl-20260918 \
  --member="serviceAccount:u5-g03-sa-20260918@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/storage.objectViewer"
```

`objectViewer` y nada más: el enunciado pide una SA dedicada con el mínimo privilegio.

- [x] **Paso 5: Desplegar con la SA y sin acceso público**

```bash
export MODEL_URI=$(python3 -c "import json;print(json.load(open('../handoff_u5_g03_20260918.json'))['model_gcs_uri'])")
export MODEL_VER=$(python3 -c "import json;print(json.load(open('../handoff_u5_g03_20260918.json'))['model_version'])")

gcloud run deploy u5-g03-cr-20260918 \
  --image=${IMG} \
  --region=us-central1 \
  --no-allow-unauthenticated \
  --service-account=u5-g03-sa-20260918@${PROJECT_ID}.iam.gserviceaccount.com \
  --min-instances=0 --max-instances=1 \
  --memory=512Mi --port=8080 \
  --set-env-vars="MODEL_GCS_URI=${MODEL_URI},MODEL_VERSION=${MODEL_VER}"
```

`--no-allow-unauthenticated` = sin acceso público (exigido). `--min-instances=0` = no cobra en reposo.

- [x] **Paso 6: Guardar la URL del servicio**

```bash
export SERVICE_URL=$(gcloud run services describe u5-g03-cr-20260918 \
  --region=us-central1 --format='value(status.url)')
echo $SERVICE_URL
```

---

## Task 7: Capturar la evidencia de la entrega

**Files:**
- Produce: capturas en `evidencias/`

- [ ] **Paso 1: `gcloud run services list` — captura obligatoria #1**

```bash
gcloud run services list --region=us-central1
```

Screenshot mostrando `u5-g03-cr-20260918` activo → `evidencias/01-run-services-list.png`

- [ ] **Paso 2: `curl /health` — captura obligatoria #2**

```bash
curl -s -w "\nHTTP %{http_code}\n" \
  -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  ${SERVICE_URL}/health
```

Esperado: `{"status":"ok","model_loaded":true,"model_version":"u4-g03-mdl-20260918-<arq>"}` y `HTTP 200`.
Screenshot con comando + respuesta → `evidencias/02-health.png`

- [ ] **Paso 3: `curl /predict` caso válido — captura obligatoria #3**

```bash
curl -s -w "\nHTTP %{http_code}\n" -X POST \
  -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  -H "Content-Type: application/json" \
  -d '{"customer_id":"TEST-VALID-001","gender":"Female","senior_citizen":false,"partner":true,"dependents":false,"tenure":12,"monthly_charges":89.5,"contract":"Month-to-month","payment_method":"Electronic check","internet_service":"Fiber optic","online_security":"No","tech_support":"No","paperless_billing":true}' \
  ${SERVICE_URL}/predict
```

Esperado: `HTTP 200` con `customer_risk_score` entre 0 y 1.
→ `evidencias/03-predict-valido.png`

- [ ] **Paso 4: `curl /predict` casos 422 — captura obligatoria #4**

Correr los casos 2, 3 y 4 de la Tarea 4 Paso 5, cambiando `localhost:8080` por `${SERVICE_URL}` y agregando el header `-H "Authorization: Bearer $(gcloud auth print-identity-token)"`.

Esperado: `HTTP 422` en los tres, con el detalle diciendo qué campo falló.
→ `evidencias/04-predict-422-faltante.png`, `evidencias/05-predict-422-enum.png`, `evidencias/06-predict-422-tipo.png`

- [ ] **Paso 5: Logging estructurado — captura de respaldo**

Consola GCP → Logging → Explorador de registros:

```
resource.type="cloud_run_revision"
resource.labels.service_name="u5-g03-cr-20260918"
jsonPayload.message="predict_ok"
```

Debe verse el `input` y `output` completos como campos buscables. Repetir con `jsonPayload.message="predict_422"`.
→ `evidencias/07-cloud-logging.png`

Esta captura no está en la lista obligatoria, pero es la **única prueba** de que el logging estructurado existe y funciona — el enunciado lo exige explícitamente.

---

## Task 8: Entrega y limpieza

- [x] **Paso 1: Copiar los dos entregables a la raíz**

El enunciado pide `schemas.py` y `main.py` como entregables. Los de la raíz son de la sesión anterior (modelo viejo) y hay que reemplazarlos:

```bash
cp service/app/schemas.py ./schemas.py
cp service/app/main.py ./main.py
```

- [ ] **Paso 2: Verificar el checklist de entregables**

- [ ] `schemas.py` — 13 features, `gender` incluida, enums cerrados
- [ ] `main.py` — logging estructurado desde el arranque
- [ ] `evidencias/01-run-services-list.png`
- [ ] `evidencias/02-health.png`
- [ ] `evidencias/03-predict-valido.png`
- [ ] `evidencias/04..06-predict-422-*.png`
- [ ] Notebook de U4 ejecutado con outputs (scorecard + leaderboard 360)

- [ ] **Paso 3: Bajar el servicio de Cloud Run**

El enunciado lo permite: *"El servicio no necesita quedar corriendo para la entrega, lo despliegan, toman la evidencia y lo bajan."*

```bash
gcloud run services delete u5-g03-cr-20260918 --region=us-central1 --quiet
```

- [x] **Paso 4: Borrar la instancia de Workbench**

```bash
gcloud workbench instances delete u4-g03 --location=us-central1-a --quiet
```

- [ ] **Paso 5: NO borrar nada más**

*"solo apagen y borren la instancia, no borren el bucket, ni el model registry ni los otros artefactos."*

**Se conservan:** el bucket `gs://computacionnube20261-u4-g03-mdl-20260918`, el Model Registry (las 3 arquitecturas), los runs de Experiments, y el repo de Artifact Registry.

---

## Riesgos conocidos y su mitigación

| Riesgo | Señal | Mitigación (dónde) |
|---|---|---|
| **Vector de features desalineado** — el modelo predice mal sin lanzar error | ninguna, es silencioso | Smoke test contra `proba_esperada` (Tarea 4, Paso 3) |
| Desajuste de versiones sklearn/xgboost | `joblib.load` falla o `/health` da 503 | Versiones fijas del handoff (Tarea 3, Paso 1) |
| `libgomp1` faltante | `ImportError` al cargar xgboost/lightgbm en el contenedor | Ya está en el Dockerfile (Tarea 5) |
| SA sin permiso sobre el bucket | `/health` da 503, log `startup_model_load_failed` | `objectViewer` (Tarea 6, Paso 4) |
| 403 en los curl | falta el identity token | Header `Authorization: Bearer $(gcloud auth print-identity-token)` |
| Nomenclatura incorrecta | descuento en la nota | Verificar contra el documento de pautas antes de Tarea 6 |
| Contenedor de serving de Vertex no soporta LightGBM | `Model.upload` falla | No bloqueante en U4 (no hay Endpoint); anotar como limitación |

## Orden de ejecución y tiempo estimado

```
Tarea 1 (Workbench, entrenar)      ~45-60 min  ← bloquea todo lo demás
Tarea 2 (schemas + tests)          ~30 min     ← se puede empezar apenas exista el handoff
Tarea 3 (main + requirements)      ~20 min
Tarea 4 (pruebas locales)          ~20 min     ← ahorra horas después
Tarea 5 (Docker local)             ~15 min
Tarea 6 (deploy Cloud Run)         ~25 min
Tarea 7 (evidencia)                ~15 min
Tarea 8 (entrega y limpieza)       ~10 min
                                   ─────────
                                   ~3h 30min
```

Deadline: **2026-09-19 06:00**.
