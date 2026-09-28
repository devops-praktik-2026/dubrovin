"""Описание того, что сервис принимает и что отдаёт.

Эти классы — не формальность. Из них FastAPI сам собирает документацию
по адресу /docs и сам проверяет входящие данные.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class OrderCreate(BaseModel):
    """Данные для создания заказа (вход POST /orders по docs/orders-api.md).

    Все три поля обязательны, но объявлены как ``| None`` с default=None:
    так пустой запрос даёт не автоматическую ошибку «missing», а проходит
    в наш валидатор ниже — и ответ 422 содержит одно понятное сообщение
    со всеми проблемными полями.
    """

    account_id: int | None = Field(default=None, gt=0, examples=[42])
    item: str | None = Field(default=None, min_length=1, max_length=120, examples=["coffee"])
    quantity: int | None = Field(default=None, ge=1, examples=[2])

    @model_validator(mode="before")
    @classmethod
    def check_required_fields(cls, data: object) -> object:
        """Требования из контракта: все три поля обязательны.

        Проверяем именно «отсутствует или пустое», а не «не передано»:
        иначе 0 и "" прошли бы как валидные значения.
        """
        if not isinstance(data, dict):
            return data
        problems: list[str] = []

        def is_missing(name: str) -> bool:
            return name not in data or data[name] is None or data[name] == ""

        if is_missing("account_id"):
            problems.append("нужен номер клиента (account_id)")
        if is_missing("item"):
            problems.append("нужно название товара (item)")
        if is_missing("quantity"):
            problems.append("нужно количество (quantity)")
        if problems:
            raise ValueError("нет поля: " + ", ".join(problems))
        return data


class OrderRead(BaseModel):
    """То, что сервис отдаёт наружу: эталонная карточка заказа."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    account_id: int
    item: str
    quantity: int
    created_at: datetime


class HealthRead(BaseModel):
    """Ответ служебной проверки «жив ли сервис»."""

    status: str
    service: str
