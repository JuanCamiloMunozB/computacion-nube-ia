"""Contrato de entrada y salida del servicio churn-api del Grupo 3."""

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


# Fuente: handoff_u5_g03_20260918.json["feature_order"].
# El orden es parte del contrato del modelo posicional y no debe editarse a mano.
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
    """Dominio compartido por OnlineSecurity y TechSupport."""

    yes = "Yes"
    no = "No"
    no_internet_service = "No internet service"


class ClienteInput(BaseModel):
    """Datos crudos del CRM transformados al vector esperado por el modelo."""

    customer_id: str = Field(min_length=1, max_length=64)
    gender: Gender
    senior_citizen: bool
    partner: bool
    dependents: bool
    tenure: int = Field(ge=0, le=100)
    monthly_charges: float = Field(gt=0.0, le=200.0)
    contract: Contract
    payment_method: PaymentMethod
    internet_service: InternetService
    online_security: YesNoNoInternet
    tech_support: YesNoNoInternet
    paperless_billing: bool

    def to_feature_vector(self) -> list[float]:
        """Replica el one-hot con ``drop_first=True`` del entrenamiento U4."""
        fila = {
            "SeniorCitizen": float(self.senior_citizen),
            "tenure": float(self.tenure),
            "MonthlyCharges": float(self.monthly_charges),
            "gender_Male": 1.0 if self.gender is Gender.male else 0.0,
            "Partner_True": float(self.partner),
            "Dependents_True": float(self.dependents),
            "Contract_One_year": 1.0 if self.contract is Contract.one_year else 0.0,
            "Contract_Two_year": 1.0 if self.contract is Contract.two_year else 0.0,
            "PaymentMethod_Credit_card__automatic_": (
                1.0 if self.payment_method is PaymentMethod.credit_card else 0.0
            ),
            "PaymentMethod_Electronic_check": (
                1.0 if self.payment_method is PaymentMethod.electronic_check else 0.0
            ),
            "PaymentMethod_Mailed_check": (
                1.0 if self.payment_method is PaymentMethod.mailed_check else 0.0
            ),
            "InternetService_Fiber_optic": (
                1.0 if self.internet_service is InternetService.fiber_optic else 0.0
            ),
            "InternetService_No": 1.0 if self.internet_service is InternetService.no else 0.0,
            "OnlineSecurity_No_internet_service": (
                1.0 if self.online_security is YesNoNoInternet.no_internet_service else 0.0
            ),
            "OnlineSecurity_Yes": (
                1.0 if self.online_security is YesNoNoInternet.yes else 0.0
            ),
            "TechSupport_No_internet_service": (
                1.0 if self.tech_support is YesNoNoInternet.no_internet_service else 0.0
            ),
            "TechSupport_Yes": 1.0 if self.tech_support is YesNoNoInternet.yes else 0.0,
            "PaperlessBilling_True": float(self.paperless_billing),
        }
        return [fila[column] for column in FEATURE_ORDER]


class PrediccionOutput(BaseModel):
    customer_id: str
    customer_risk_score: float = Field(ge=0.0, le=1.0)
    predicted_churn: bool
    model_version: str
    predicted_at: datetime
    requested_by: str
    source: Literal["api_single", "api_batch", "batch_job"]
    input_file: str | None = None


class HealthOutput(BaseModel):
    status: Literal["ok", "degraded"] = "ok"
    model_loaded: bool
    model_version: str | None = None
