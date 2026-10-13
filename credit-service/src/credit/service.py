from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.exc import MultipleResultsFound
from sqlalchemy.ext.asyncio import AsyncSession, AsyncSessionTransaction

from credit.exceptions import (
    CreditConsistencyError,
    CreditNotFoundError,
    CreditReservationConflictError,
    CreditReservationNotFoundError,
    InsufficientCreditsError,
)
from credit.models import MAX_CREDITS, CreditReservationResult, CreditResponse
from credit.orm_models import Credit, CreditReservation
from credit.repository import (
    find_credit_account_by_user_id,
    find_credit_reservation,
    find_credit_transfer,
    insert_credit_reservation,
    lock_credit_accounts,
    record_credit_transfer,
    sum_active_reservations,
)


async def get_current_credit_balance(user_id: UUID, session: AsyncSession) -> CreditResponse:
    account = await find_credit_account_by_user_id(session, user_id)
    if account is None:
        raise CreditNotFoundError("Credit account not found.")
    return account


async def get_credit_reservation(
    session: AsyncSession, order_id: UUID,
) -> CreditReservationResult:
    """Look up an order's durable credit outcome for reconciliation."""
    _validate_ids(order_id)
    async with _operation_transaction(session):
        reservation = await _require_reservation(session, order_id)
        return await _reservation_result(session, reservation)


async def reserve_credits(
    session: AsyncSession, order_id: UUID, requester_id: UUID, amount: int,
) -> CreditReservationResult:
    """Reserve available credits once for an order; a matching retry is harmless."""
    _validate_ids(order_id, requester_id)
    if type(amount) is not int or not 1 <= amount <= MAX_CREDITS:
        raise ValueError("Credit amount must be a positive supported integer.")

    async with _operation_transaction(session):
        accounts = await lock_credit_accounts(session, {requester_id})
        account = _require_account(accounts, requester_id)
        reservation = await find_credit_reservation(session, order_id, for_update=True)
        if reservation is not None:
            _validate_reserve_retry(reservation, requester_id, amount)
            return await _reservation_result(session, reservation)

        await _validate_reserved_balance(session, account)
        if account.available_credits < amount:
            raise InsufficientCreditsError("Insufficient available credits.")
        _validate_balance_limit(account.reserved_credits + amount)

        reservation = await insert_credit_reservation(session, order_id, requester_id, amount)
        if reservation is None:
            reservation = await _require_reservation(session, order_id, for_update=True)
            _validate_reserve_retry(reservation, requester_id, amount)
            return await _reservation_result(session, reservation)

        account.available_credits -= amount
        account.reserved_credits += amount
        account.updated_at = _now()
        await session.flush()
        return await _reservation_result(session, reservation)


async def release_credits(
    session: AsyncSession, order_id: UUID,
) -> CreditReservationResult:
    """Refund a cancelled or expired order once, retaining its reservation record."""
    _validate_ids(order_id)
    async with _operation_transaction(session):
        reservation = await _require_reservation(session, order_id)
        accounts = await lock_credit_accounts(session, {reservation.user_id})
        reservation = await _require_reservation(session, order_id, for_update=True)
        if reservation.status == "RELEASED":
            return await _reservation_result(session, reservation)
        if reservation.status != "RESERVED":
            raise CreditReservationConflictError("Transferred credits cannot be released.")

        account = _require_account(accounts, reservation.user_id)
        await _validate_reserved_balance(session, account)
        _validate_balance_limit(account.available_credits + reservation.amount)

        now = _now()
        account.reserved_credits -= reservation.amount
        account.available_credits += reservation.amount
        account.updated_at = now
        reservation.status = "RELEASED"
        reservation.updated_at = now
        await session.flush()
        return await _reservation_result(session, reservation)


async def transfer_credits(
    session: AsyncSession, order_id: UUID, courier_id: UUID,
) -> CreditReservationResult:
    """Settle confirmed delivery once, atomically paying the courier and recording it."""
    _validate_ids(order_id, courier_id)
    async with _operation_transaction(session):
        reservation = await _require_reservation(session, order_id)
        if reservation.user_id == courier_id:
            raise ValueError("The requester cannot receive their own credit transfer.")

        accounts = await lock_credit_accounts(session, {reservation.user_id, courier_id})
        reservation = await _require_reservation(session, order_id, for_update=True)
        if reservation.status == "TRANSFERRED":
            result = await _reservation_result(session, reservation)
            if result.recipient_user_id != courier_id:
                raise CreditReservationConflictError("The order was transferred to another courier.")
            return result
        if reservation.status != "RESERVED":
            raise CreditReservationConflictError("Released credits cannot be transferred.")

        requester = _require_account(accounts, reservation.user_id)
        courier = _require_account(accounts, courier_id)
        await _validate_reserved_balance(session, requester)
        await _validate_reserved_balance(session, courier)
        _validate_balance_limit(courier.total_credits + reservation.amount)

        now = _now()
        requester.reserved_credits -= reservation.amount
        courier.available_credits += reservation.amount
        requester.updated_at = courier.updated_at = now
        reservation.status = "TRANSFERRED"
        reservation.updated_at = now
        record_credit_transfer(session, reservation, courier_id, now)
        await session.flush()
        return await _reservation_result(session, reservation)


def _operation_transaction(session: AsyncSession) -> AsyncSessionTransaction:
    """Use a savepoint inside a caller transaction; otherwise commit the operation."""
    return session.begin_nested() if session.in_transaction() else session.begin()


def _validate_ids(*identifiers: UUID) -> None:
    if any(not isinstance(identifier, UUID) for identifier in identifiers):
        raise ValueError("Credit operation identifiers must be UUIDs.")


def _validate_balance_limit(balance: int) -> None:
    if balance > MAX_CREDITS:
        raise ValueError("Credit balance exceeds the supported limit.")


def _require_account(accounts: dict[UUID, Credit], user_id: UUID) -> Credit:
    account = accounts.get(user_id)
    if account is None:
        raise CreditNotFoundError("Credit account not found.")
    return account


async def _require_reservation(
    session: AsyncSession, order_id: UUID, *, for_update: bool = False,
) -> CreditReservation:
    reservation = await find_credit_reservation(session, order_id, for_update=for_update)
    if reservation is None:
        raise CreditReservationNotFoundError("Credit reservation not found.")
    return reservation


def _validate_reserve_retry(
    reservation: CreditReservation, requester_id: UUID, amount: int,
) -> None:
    if reservation.user_id != requester_id or reservation.amount != amount:
        raise CreditReservationConflictError("The order has different reservation details.")


async def _validate_reserved_balance(session: AsyncSession, account: Credit) -> None:
    if account.reserved_credits != await sum_active_reservations(session, account.user_id):
        raise CreditConsistencyError("Reserved balance does not match active reservations.")


async def _reservation_result(
    session: AsyncSession, reservation: CreditReservation,
) -> CreditReservationResult:
    result = CreditReservationResult.model_validate(reservation)
    if reservation.status == "TRANSFERRED":
        try:
            transfer = await find_credit_transfer(session, reservation.order_id)
        except MultipleResultsFound:
            raise CreditConsistencyError("The order has multiple credit transfer records.") from None
        if (
            transfer is None
            or transfer.user_id != reservation.user_id
            or transfer.amount != reservation.amount
            or transfer.recipient_user_id is None
        ):
            raise CreditConsistencyError("The transferred reservation has no matching transfer record.")
        result.recipient_user_id = transfer.recipient_user_id
    return result


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)
