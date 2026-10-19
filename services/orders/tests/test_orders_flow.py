"""Интеграционный тест связки: accounts + orders.
Оба приложения работают в одном процессе. httpx.get из accounts_client.py
перенаправляется в accounts_app через ASGITransport без реальных сетевых запросов.
"""

import asyncio

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

import accounts.db as accounts_db
import accounts.models  # noqa: F401 — таблицы создаются только после импорта моделей
import orders.accounts_client as orders_accounts_client
import orders.db as orders_db
import orders.models  # noqa: F401
from accounts.main import app as accounts_app
from orders.config import settings as orders_settings
from orders.main import app as orders_app


def _asgi_get(app):
    """Возвращает замену httpx.get: запрос уходит в ASGI-приложение без сети.

    accounts_client.py использует синхронный httpx.get, а ASGITransport —
    асинхронный, поэтому прогоняем корутину отдельным циклом событий.
    """
    transport = httpx.ASGITransport(app=app)

    def get(url, timeout):
        async def send():
            async with httpx.AsyncClient(transport=transport) as client:
                return await client.get(url, timeout=timeout)

        return asyncio.run(send())

    return get


def _asgi_send(app):
    """Возвращает замену httpx.Client.send: тот же трюк для произвольных
    запросов (POST/GET), чтобы весь трафик клиента шёл в приложение напрямую.
    """
    transport = httpx.ASGITransport(app=app)

    def send(request, **kwargs):
        async def run():
            async with httpx.AsyncClient(transport=transport) as ac:
                return await ac.send(request)

        response = asyncio.run(run())
        # Синхронный клиент читает body сразу и закрывает поток — иначе
        # ответ "протечёт" в закрытый асинхронный цикл событий.
        response.read()
        return response

    return send


@pytest.fixture()
def integration_clients(tmp_path):
    """Поднимает оба приложения с временными SQLite-базами в памяти.

    Здесь намеренно не используется monkeypatch: фикстура сама закрывает
    трафик через ASGI, а тесты сервиса orders полагаются на его автозаглушку.
    """
    saved = {}
    for module, base in ((accounts_db, accounts_db.Base), (orders_db, orders_db.Base)):
        engine = create_engine(
            f"sqlite:///{tmp_path / f'{module.__name__}.db'}",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        saved[module] = (module.engine, module.SessionFactory)
        module.engine = engine
        module.SessionFactory = module.sessionmaker(bind=engine)
        base.metadata.create_all(engine)

    # Заставляем orders стучаться по спец. адресу, который понимает транспорт
    saved_accounts_url = orders_settings.accounts_url
    orders_settings.accounts_url = "http://testserver"

    # Создаем клиентов, которые общаются напрямую через память (без сети!)
    accounts_client = httpx.Client(base_url="http://testserver")
    orders_client = httpx.Client(base_url="http://testserver")
    accounts_client.send = _asgi_send(accounts_app)
    orders_client.send = _asgi_send(orders_app)

    yield accounts_client, orders_client

    accounts_client.close()
    orders_client.close()
    orders_settings.accounts_url = saved_accounts_url
    for module, (engine, session_factory) in saved.items():
        module.engine = engine
        module.SessionFactory = session_factory


def test_create_account_then_order_returns_201(integration_clients, monkeypatch):
    """Создаём клиента через accounts, потом заказ через orders — должен быть 201."""
    accounts_client, orders_client = integration_clients

    # Шаг 1: Создаем клиента
    resp_account = accounts_client.post(
        "/accounts",
        json={"name": "Иван Петров", "email": "ivan@example.com"},
    )
    assert resp_account.status_code == 201
    account_id = resp_account.json()["id"]

    # Шаг 2: Создаем заказ.
    # Внутри orders сработает httpx.get, и ASGITransport тихо передаст его в accounts_app
    monkeypatch.setattr(orders_accounts_client.httpx, "get", _asgi_get(accounts_app))
    resp_order = orders_client.post(
        "/orders",
        json={"account_id": account_id, "item": "coffee", "quantity": 2},
    )
    assert resp_order.status_code == 201
    assert resp_order.json()["account_id"] == account_id
