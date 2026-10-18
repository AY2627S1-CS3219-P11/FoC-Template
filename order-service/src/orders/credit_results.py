"""Apply Credit replies within the transaction owned by the message consumer.

Each public handler owns one business operation. Shared helpers only handle
request correlation, locking, reservation validation, and receipt recording.
"""

from datetime import timedelta
from typing import assert_never

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from orders.models import (
    CreditOperationOutcome,
    CreditReservationResult,
    CreditResult,
    ReleaseCreditCommand,
    ReserveCreditCommand,
    RoutingKey,
    TransferCreditCommand,
)
from orders.orm_models import (
    CreditCommandOutbox,
    CreditCommandResult,
    ErrandRequest,
    Status,
)


async def handle_reservation_result(
    session: AsyncSession, result: CreditResult
) -> None:
    pending = await _load_stored_request(
        session, result, ReserveCreditCommand.routing_key
    )
    command = ReserveCreditCommand.model_validate(pending.payload)
    if command.requester_id != result.requester_id or command.amount != result.amount:
        raise ValueError(
            "Credit result does not match the original reservation request"
        )

    order = await _load_order_unless_duplicate(session, result)
    if order is None:
        return
    if command.requester_id != order.requester_id or command.amount != order.credits:
        raise ValueError("Credit reservation does not match the order")

    match result.outcome:
        case CreditOperationOutcome.REJECTED:
            if order.status == Status.PENDING:
                order.status = Status.REJECTED
                order.updated_at = (
                    await session.execute(select(func.clock_timestamp()))
                ).scalar_one()
        case CreditOperationOutcome.SUCCEEDED:
            _validate_reservation(result, order)
            # A late reply must not reopen an order that has moved on.
            if order.status == Status.PENDING:
                now = (
                    await session.execute(select(func.clock_timestamp()))
                ).scalar_one()
                order.status = Status.OPEN
                order.expires_at = now + timedelta(minutes=15)
                order.updated_at = now
        case unexpected:
            assert_never(unexpected)

    _record_reply(session, pending, result)


async def handle_release_result(session: AsyncSession, result: CreditResult) -> None:
    pending = await _load_stored_request(session, result, ReleaseCreditCommand.routing_key)
    ReleaseCreditCommand.model_validate(pending.payload)
    order = await _load_order_unless_duplicate(session, result)
    if order is None:
        return

    match result.outcome:
        case CreditOperationOutcome.SUCCEEDED:
            _validate_reservation(result, order)
        case CreditOperationOutcome.REJECTED:
            # Record the failure without changing the cancelled/expired order.
            pass
        case unexpected:
            assert_never(unexpected)

    # Cancellation/expiry already changed the order. Release only settles credits.
    _record_reply(session, pending, result)


async def handle_transfer_result(session: AsyncSession, result: CreditResult) -> None:
    pending = await _load_stored_request(
        session, result, TransferCreditCommand.routing_key
    )
    command = TransferCreditCommand.model_validate(pending.payload)
    if command.courier_id != result.courier_id:
        raise ValueError("Credit result does not match the original transfer request")

    order = await _load_order_unless_duplicate(session, result)
    if order is None:
        return
    if command.courier_id != order.courier_id:
        raise ValueError("Credit transfer does not match the assigned courier")

    match result.outcome:
        case CreditOperationOutcome.SUCCEEDED:
            reservation = _validate_reservation(result, order)
            if reservation.recipient_user_id != order.courier_id:
                raise ValueError("Credit transfer contains an unexpected recipient")
            if order.status == Status.RECEIVED:
                order.status = Status.COMPLETED
                order.updated_at = (
                    await session.execute(select(func.clock_timestamp()))
                ).scalar_one()
        case CreditOperationOutcome.REJECTED:
            # Record the failure, leaving the order awaiting settlement.
            pass
        case unexpected:
            assert_never(unexpected)

    _record_reply(session, pending, result)


async def _load_stored_request(
    session: AsyncSession,
    result: CreditResult,
    routing_key: RoutingKey,
) -> CreditCommandOutbox:
    """Lock the original command and check its route and identifiers.

    Each handler explicitly parses its own command payload afterward.
    """
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
        or str(pending.payload.get("request_id")) != str(result.request_id)
        or str(pending.payload.get("order_id")) != str(result.order_id)
        or pending.routing_key != routing_key
    ):
        raise ValueError("Credit result does not match the original command")
    return pending


async def _load_order_unless_duplicate(
    session: AsyncSession,
    result: CreditResult,
) -> ErrandRequest | None:
    """Skip identical receipts, reject conflicting ones, otherwise lock the order.

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


def _validate_reservation(
    result: CreditResult,
    order: ErrandRequest,
) -> CreditReservationResult:
    reservation = result.reservation
    if (
        reservation is None
        or reservation.order_id != order.id
        or reservation.user_id != order.requester_id
        or reservation.amount != order.credits
    ):
        raise ValueError("Credit result contains unexpected reservation details")
    return reservation


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
