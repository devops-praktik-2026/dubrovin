"""Запросы, которые умеет обрабатывать сервис заказов."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from orders.db import get_session
from orders.models import Order
from orders.schemas import OrderCreate, OrderRead

router = APIRouter(prefix="/orders", tags=["Заказы"])


def _get_or_404(session: Session, order_id: int) -> Order:
    """Возвращает заказ по номеру или поднимает 404.

    Как и в сервисе клиентов (см. accounts/api.py), сообщение об ошибке
    обязательно содержит номер, который искали (docs/orders-api.md, раздел 2).
    """
    order = session.get(Order, order_id)
    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"order {order_id} not found",
        )
    return order


@router.post(
    "",
    response_model=OrderRead,
    status_code=status.HTTP_201_CREATED,
    summary="Создать заказ",
)
def create_order(payload: OrderCreate, session: Session = Depends(get_session)) -> Order:
    order = Order(**payload.model_dump())
    session.add(order)
    session.commit()
    session.refresh(order)
    return order


@router.get("/{order_id}", response_model=OrderRead, summary="Получить заказ по номеру")
def get_order(order_id: int, session: Session = Depends(get_session)) -> Order:
    """Карточка заказа по его номеру (карточка 1.3, docs/orders-api.md).

    Типизация ``order_id: int`` даёт автоматическую валидацию пути:
    запрос вида ``GET /orders/abc`` FastAPI сам ответит 422 без ручных проверок.
    Если заказа нет — 404 с номером, который искали, в поле ``detail``.
    """
    return _get_or_404(session, order_id)
