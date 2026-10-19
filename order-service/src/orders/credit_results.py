"""Apply Credit replies within the transaction owned by the message consumer.

Each public handler owns one business operation. Shared helpers only handle
request correlation, locking, and receipt recording.
"""

from datetime import datetime
from typing import assert_never
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from orders.deadlines import init_window, open_window
from orders.models import (
    CreditOperationOutcome,
    CreditResult,
    ReleaseCreditCommand,
    ReserveCreditCommand,
    RoutingKey,
    TransferCreditCommand,
)
from orders.orm_models import (
    CreditCommandOutbox,
    CreditCommandResult,
    CreditStatus,
    ErrandRequest,
    Status,
)
from orders.repository import add_credit_command


async def handle_reservation_result(
    session: AsyncSession, result: CreditResult
) -> None:
    pending = await _load_stored_request(
        session, result, ReserveCreditCommand.routing_key
    )
    order = await _load_order_unless_duplicate(session, result)
    if order is None:
        return

    now = (await session.execute(select(func.clock_timestamp()))).scalar_one()
    # Enforce the timeout even when a reply beats the periodic sweep.
    if order.status == Status.INIT and order.created_at + init_window() <= now:
        order.status = Status.EXPIRED
        order.status_reason = (
            "Credit reservation was not confirmed within the initialization deadline. "
            "Any delayed reservation will be refunded automatically."
        )
        order.updated_at = now

    match result.outcome:
        case CreditOperationOutcome.REJECTED:
            if order.status in (Status.INIT, Status.EXPIRED):
                order.credit_status = CreditStatus.REJECTED
                if order.status == Status.INIT:
                    order.status = Status.REJECTED
                else:
                    order.status_reason = "Initialization timed out; the reservation was rejected and no credits were reserved."
                order.updated_at = now
        case CreditOperationOutcome.SUCCEEDED:
            if order.status == Status.INIT:
                order.credit_status = CreditStatus.SUCCEEDED
                order.status = Status.OPEN
                order.expires_at = now + open_window()
                order.updated_at = now
            elif order.status == Status.EXPIRED:
                # An unknown reservation is not safe to refund until success is
                # confirmed. Record that confirmation and release atomically.
                existing_release = await session.scalar(
                    select(CreditCommandOutbox.id).where(
                        CreditCommandOutbox.order_id == order.id,
                        CreditCommandOutbox.routing_key == RoutingKey.CREDIT_RELEASE,
                    )
                )
                if existing_release is None:
                    add_credit_command(session, ReleaseCreditCommand(
                        request_id=uuid4(), order_id=order.id,
                    ))
                    order.credit_status = CreditStatus.PENDING
                    order.status_reason = "Initialization timed out; a delayed credit reservation is being refunded."
                    order.updated_at = now
        case unexpected:
            assert_never(unexpected)

    _record_reply(session, pending, result)


async def handle_release_result(session: AsyncSession, result: CreditResult) -> None:
    pending = await _load_stored_request(session, result, ReleaseCreditCommand.routing_key)
    order = await _load_order_unless_duplicate(session, result)
    if order is None:
        return

    # Only the active release may change this dimension. A late reservation
    # reply must not overwrite it, and release never reopens the order.
    if order.status in (Status.CANCELLED, Status.EXPIRED):
        order.credit_status = CreditStatus(result.outcome.value.lower())
        if order.status == Status.EXPIRED:
            order.status_reason = (
                "Order expired; reserved credits have been returned."
                if result.outcome == CreditOperationOutcome.SUCCEEDED else
                "Order expired, but the credit refund was rejected and requires investigation."
            )
        order.updated_at = (
            await session.execute(select(func.clock_timestamp()))
        ).scalar_one()

    _record_reply(session, pending, result)


async def handle_transfer_result(session: AsyncSession, result: CreditResult) -> None:
    pending = await _load_stored_request(
        session, result, TransferCreditCommand.routing_key
    )
    order = await _load_order_unless_duplicate(session, result)
    if order is None:
        return

    match result.outcome:
        case CreditOperationOutcome.SUCCEEDED:
            if order.status in (Status.RECEIVED, Status.DISPUTED):
                now = (await session.execute(select(func.clock_timestamp()))).scalar_one()
                _dispute_late_settlement(order, now)
                order.credit_status = CreditStatus.SUCCEEDED
                if order.status == Status.RECEIVED:
                    order.status = Status.COMPLETED
                    order.settlement_due_at = None
                order.updated_at = now
        case CreditOperationOutcome.REJECTED:
            if order.status in (Status.RECEIVED, Status.DISPUTED):
                now = (await session.execute(select(func.clock_timestamp()))).scalar_one()
                _dispute_late_settlement(order, now)
                order.credit_status = CreditStatus.REJECTED
                order.updated_at = now
        case unexpected:
            assert_never(unexpected)

    _record_reply(session, pending, result)


def _dispute_late_settlement(order: ErrandRequest, now: datetime) -> None:
    if (order.status == Status.RECEIVED and order.credit_status == CreditStatus.PENDING
            and order.settlement_due_at is not None and order.settlement_due_at <= now):
        order.status = Status.DISPUTED
        order.status_reason = "The credit settlement deadline was exceeded; its eventual outcome is recorded separately."


async def _load_stored_request(
    session: AsyncSession,
    result: CreditResult,
    routing_key: RoutingKey,
) -> CreditCommandOutbox:
    """Lock the original command and correlate the reply by order and operation."""
    pending = await session.scalar(
        select(CreditCommandOutbox)
        .where(CreditCommandOutbox.id == result.request_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if pending is None:
        raise ValueError("Credit result has no matching Order command")

    if (
        pending.order_id != result.order_id
        or pending.routing_key != routing_key
    ):
        raise ValueError("Credit result does not match the original command")
    return pending


async def _load_order_unless_duplicate(
    session: AsyncSession,
    result: CreditResult,
) -> ErrandRequest | None:
    """Skip identical receipts, otherwise lock the order.

    Call only after verifying and locking the stored request. Its lock serializes
    replies for that request until the consumer commits the transaction.
    """
    saved_result = await session.get(CreditCommandResult, result.request_id)
    if saved_result is not None:
        if saved_result.payload != result.model_dump(mode="json"):
            raise ValueError("Credit returned a different outcome for the same request")
        return None

    order = await session.scalar(
        select(ErrandRequest)
        .where(ErrandRequest.id == result.order_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if order is None:
        raise ValueError("Credit result references an unknown order")
    return order


def _record_reply(
    session: AsyncSession,
    pending: CreditCommandOutbox,
    result: CreditResult,
) -> None:
    # Receipt and order changes commit together; the consumer acknowledges afterward.
    session.add(
        CreditCommandResult(
            request_id=result.request_id,
            payload=result.model_dump(mode="json"),
        )
    )
    match result.outcome:
        case CreditOperationOutcome.REJECTED:
            pending.last_error = f"Credit {result.operation} rejected: {result.reason}"
        case CreditOperationOutcome.SUCCEEDED:
            pending.last_error = None
        case unexpected:
            assert_never(unexpected)
