"""
Тесты запросов к сервису заказов.
"""

import pytest


def test_create_order_returns_201(client, order_payload):
    response = client.post("/orders", json=order_payload)

    assert response.status_code == 201
    body = response.json()
    assert body["id"] > 0
    assert body["account_id"] == order_payload["account_id"]
    assert body["item"] == order_payload["item"]
    assert body["quantity"] == order_payload["quantity"]
    assert body["created_at"]


@pytest.mark.parametrize(
    "payload",
    [
        # пустой запрос: нет ни одного поля
        {},
        # нет поля item
        {"account_id": 1, "quantity": 2},
        # нет поля quantity
        {"account_id": 1, "item": "Кофемолка"},
        # quantity меньше 1
        {"account_id": 1, "item": "Кофемолка", "quantity": 0},
        # item пустой
        {"account_id": 1, "item": "", "quantity": 2},
    ],
)
def test_invalid_payload_returns_422(client, payload):
    response = client.post("/orders", json=payload)

    assert response.status_code == 422
