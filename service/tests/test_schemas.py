import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas import FEATURE_ORDER, ClienteInput


HANDOFF = json.loads(
    Path(__file__).parent.parent.parent.joinpath("handoff_u5_g03_20260918.json").read_text()
)


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
    assert FEATURE_ORDER == HANDOFF["feature_order"]


def test_vector_tiene_el_largo_correcto():
    cliente = ClienteInput(**_cliente_valido())
    assert len(cliente.to_feature_vector()) == len(FEATURE_ORDER)


def test_categoria_base_produce_ceros():
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
