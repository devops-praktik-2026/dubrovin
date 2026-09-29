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


# --- GET /orders/{id} (карточка 1.3, docs/orders-api.md, раздел 2) ---


def test_read_created_account_returns_full_card(client, order_payload):
    """200 OK: возвращается полная карточка заказа."""
    created = client.post("/orders", json=order_payload).json()

    response = client.get(f"/orders/{created['id']}")

    assert response.status_code == 200
    body = response.json()
    assert body == created
    assert set(body) == {"id", "account_id", "item", "quantity", "created_at"}
    assert body["account_id"] == order_payload["account_id"]
    assert body["item"] == order_payload["item"]
    assert body["quantity"] == order_payload["quantity"]
    assert body["created_at"]


def test_read_missing_order_returns_404_with_number(client):
    """404: заказа нет — в detail обязательно номер, который искали."""
    response = client.get("/orders/99999")

    assert response.status_code == 404
    assert "order 99999 not found" in response.json()["detail"]


@pytest.mark.parametrize("broken_id", ["abc", "1.5"])
def test_read_order_bad_path_id_returns_422(client, broken_id):
    """422: ID в пути не парсится в целое число — автоматическая валидация FastAPI."""
    response = client.get(f"/orders/{broken_id}")

    assert response.status_code == 422


@pytest.mark.parametrize("absent_id", [0, -3])
def test_read_order_non_positive_int_id_returns_404(client, absent_id):
    """404: отрицательный/нулевой ID — корректное целое, парсится, но заказа нет.

    Ручной проверки знака в эндпоинте нет (по контракту), поэтому FastAPI
    принимает такое число и сервис отвечает 404 с номером из запроса.
    """
    response = client.get(f"/orders/{absent_id}")

    assert response.status_code == 404
    assert f"order {absent_id} not found" in response.json()["detail"]
