"""Клиент сервиса клиентов: проверка, что заказ оформляют на существующего клиента."""

import httpx
from fastapi import HTTPException, status

from orders.config import settings


def ensure_account_exists(account_id: int) -> None:
    url = f"{settings.accounts_url}/accounts/{account_id}"
    try:
        response = httpx.get(url, timeout=settings.accounts_timeout_seconds)
    except httpx.RequestError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Сервис клиентов не отвечает",
        ) from error

    if response.status_code == status.HTTP_404_NOT_FOUND:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"account {account_id} not found",
        )
    response.raise_for_status()
