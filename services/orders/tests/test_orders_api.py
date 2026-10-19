"""
Тесты запросов к сервису заказов.
"""

import time

import httpx
import pytest
from conftest import make_hanging_get

from orders.config import settings


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


def test_read_created_order_returns_full_card(client, order_payload):
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


# --- GET /orders?account_id= (карточка 1.4, docs/orders-api.md, раздел 3) ---


def _create(client, account_id: int, item: str) -> dict:
    """Создаёт заказ и возвращает его карточку (вспомогательная функция тестов)."""
    response = client.post("/orders", json={"account_id": account_id, "item": item, "quantity": 1})
    assert response.status_code == 201
    return response.json()


def test_list_orders_returns_only_client_orders(client):
    """Запрос со ссылкой на клиента возвращает только его заказы."""
    mine = _create(client, 42, "coffee")
    _create(client, 7, "tea")
    second_mine = _create(client, 42, "sugar")

    response = client.get("/orders", params={"account_id": 42})

    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert {order["id"] for order in body} == {mine["id"], second_mine["id"]}
    assert all(order["account_id"] == 42 for order in body)
    # каждая запись — полная карточка заказа
    assert set(body[0]) == {"id", "account_id", "item", "quantity", "created_at"}


def test_list_orders_empty_result_is_200_and_empty_list(client):
    """У клиента без заказов возвращается пустой список и код 200, а не ошибка."""
    _create(client, 42, "coffee")  # заказы есть, но у другого клиента

    response = client.get("/orders", params={"account_id": 999})

    assert response.status_code == 200
    assert response.json() == []


def test_list_orders_limit_caps_response(client):
    """limit ограничивает размер выдачи."""
    ids = [_create(client, 42, f"item-{i}")["id"] for i in range(5)]

    response = client.get("/orders", params={"account_id": 42, "limit": 3})

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 3
    # порядок детерминированный: от старых к новым
    assert [order["id"] for order in body] == ids[:3]


def test_list_orders_default_limit_is_20(client):
    """Без limit по умолчанию отдаётся не больше 20 заказов."""
    for i in range(25):
        _create(client, 42, f"item-{i}")

    response = client.get("/orders", params={"account_id": 42})

    assert response.status_code == 200
    assert len(response.json()) == 20


@pytest.mark.parametrize("limit", ["0", "-1", "101", "abc"])
def test_list_orders_bad_limit_returns_422(client, limit):
    """422: limit вне диапазона 1–100 или не число."""
    response = client.get("/orders", params={"account_id": 42, "limit": limit})

    assert response.status_code == 422


def test_list_orders_without_account_id_returns_422(client):
    """422: параметр account_id обязателен."""
    response = client.get("/orders")

    assert response.status_code == 422


@pytest.mark.parametrize("account_id", ["abc", "0", "-5"])
def test_list_orders_bad_account_id_returns_422(client, account_id):
    """422: account_id должен быть положительным целым числом."""
    response = client.get("/orders", params={"account_id": account_id})

    assert response.status_code == 422


def test_order_for_missing_account_returns_404(client, order_payload, monkeypatch):
    """Если сосед говорит, что клиента нет — возвращаем 404."""
    # Подменяем ответ соседа на 404
    answer = httpx.Response(404, request=httpx.Request("GET", "http://accounts"))
    monkeypatch.setattr(httpx, "get", lambda url, timeout: answer)

    response = client.post("/orders", json=order_payload)
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


def test_order_when_accounts_is_down_returns_503(client, order_payload, monkeypatch):
    """Сосед погашен (docker compose stop accounts): соединение не устанавливается.

    httpx поднимает ConnectError — our handler должен отдать 503 сразу,
    а не 500 и не ждать минуту.
    """

    def refused_get(url, timeout):
        raise httpx.ConnectError(
            "all connection attempts failed", request=httpx.Request("GET", url)
        )

    monkeypatch.setattr(httpx, "get", refused_get)

    started = time.monotonic()
    response = client.post("/orders", json=order_payload)
    waited = time.monotonic() - started

    assert response.status_code == 503
    assert "не отвечает" in response.json()["detail"]
    # Ответ приходит почти мгновенно, а не после длинного системного таймаута.
    assert waited < settings.accounts_timeout_seconds + 1


def test_order_when_accounts_is_frozen_returns_503_after_timeout(
    client, order_payload, monkeypatch
):
    """Сосед заморожен (docker compose pause accounts): запрос висит без ответа.

    httpx прерывает ожидание по таймауту и поднимает ReadTimeout.
    Проверяем, что 503 приходит ровно через accounts_timeout_seconds,
    а не через минуту.
    """
    monkeypatch.setattr(httpx, "get", make_hanging_get(settings.accounts_timeout_seconds))

    started = time.monotonic()
    response = client.post("/orders", json=order_payload)
    waited = time.monotonic() - started

    assert response.status_code == 503
    assert "не отвечает" in response.json()["detail"]
    # Ждём ровно таймаут: ни сильно меньше (не оборвали раньше), ни минуты.
    assert settings.accounts_timeout_seconds <= waited < settings.accounts_timeout_seconds * 2
