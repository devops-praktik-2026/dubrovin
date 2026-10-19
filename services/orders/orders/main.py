"""Точка входа сервиса заказов.

Запуск вручную:
    uvicorn orders.main:app --reload --port 8002
"""

from fastapi import FastAPI

from orders.api import router
from orders.config import settings
from orders.db import Base, engine
from orders.schemas import HealthRead

# Миграций у сервиса заказов ещё нет, поэтому таблицы создаём по моделям
# прямо при старте приложения: если таблиц нет — SQLAlchemy создаст их сам.
# Вызов безопасен повтором: существующие таблицы не трогаются.
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Сервис заказов",
    description=("Реализация контракта из docs/orders-api.md. "),
    version="0.1.0",
)

app.include_router(router)


@app.get("/health", response_model=HealthRead, tags=["Служебное"], summary="Жив ли сервис")
def health() -> HealthRead:
    """Короткий ответ для проверки после установки новой версии.

    Намеренно не обращается к базе данных: этот запрос должен отвечать
    быстро и всегда, иначе им нельзя пользоваться при выкатке.
    """
    return HealthRead(status="ok", service=settings.service_name)
