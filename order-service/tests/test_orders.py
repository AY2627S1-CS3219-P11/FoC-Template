"""PostgreSQL regressions for duplicate commands and late financial replies."""

import asyncio
import os
import unittest
from datetime import timedelta
from uuid import uuid4

from sqlalchemy import event, func, select, text, update
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from orders import creation, credit_results, repository
from orders.models import (
    CreditOperation,
    CreditOperationOutcome,
    CreditResult,
)
from orders.orm_models import (
    Base,
    CreditCommandOutbox,
    CreditStatus,
    ErrandRequest,
    OrderCreationKey,
    Status,
)


@unittest.skipUnless(os.environ.get("ORDER_TEST_DATABASE_URL"), "requires ORDER_TEST_DATABASE_URL")
class OrderDatabaseTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.schema = "order_test_" + uuid4().hex
        url = make_url(os.environ["ORDER_TEST_DATABASE_URL"])
        if url.drivername == "postgresql":
            url = url.set(drivername="postgresql+psycopg")
        self.engine = create_async_engine(url)

        @event.listens_for(self.engine.sync_engine, "begin")
        def set_search_path(connection):
            connection.exec_driver_sql(f'SET LOCAL search_path TO "{self.schema}"')

        async with self.engine.begin() as connection:
            await connection.execute(text(f'CREATE SCHEMA "{self.schema}"'))
            await connection.run_sync(Base.metadata.create_all)
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        self.requester = uuid4()
        self.fields = dict(
            supplier_id=uuid4(), supplier_snapshot={},
            items=[{"name": "Tea", "quantity": 1}], pickup_notes=None, credits=10,
        )

    async def asyncTearDown(self):
        async with self.engine.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA "{self.schema}" CASCADE'))
        await self.engine.dispose()

    async def create(self, **changes):
        async with self.sessions() as session:
            return await creation.create_order_idempotently(
                session, self.requester, "key", **(self.fields | changes),
            )

    async def test_concurrent_retries_reserve_only_once(self):
        orders = await asyncio.wait_for(asyncio.gather(*(self.create() for _ in range(8))), 20)
        self.assertEqual(len({order.id for order in orders}), 1)
        async with self.sessions() as session:
            for model in (ErrandRequest, OrderCreationKey, CreditCommandOutbox):
                self.assertEqual(await session.scalar(select(func.count()).select_from(model)), 1)

    async def test_replay_accepts_snapshot_changes_but_rejects_changed_intent(self):
        first = await self.create()
        replay = await self.create(supplier_snapshot={"name": "Updated supplier"})
        self.assertEqual(first.id, replay.id)
        self.assertEqual(replay.supplier_snapshot, {})
        with self.assertRaises(creation.CreationConflict):
            await self.create(credits=11)

    async def test_late_reservation_is_refunded_once_without_reopening(self):
        order = await self.create()
        async with self.sessions() as session:
            await session.execute(update(ErrandRequest).where(ErrandRequest.id == order.id)
                                  .values(created_at=func.clock_timestamp() - timedelta(days=1)))
            await session.commit()
            self.assertEqual(await repository.expire_initializing_orders(session), [order.id])
            reserve = await session.scalar(select(CreditCommandOutbox).where(
                CreditCommandOutbox.order_id == order.id))
            reply = CreditResult(
                request_id=reserve.id, order_id=order.id,
                operation=CreditOperation.RESERVE,
                outcome=CreditOperationOutcome.SUCCEEDED,
            )
            for _ in range(2):
                await credit_results.handle_reservation_result(session, reply)
                await session.commit()
            stored = await repository.get_order_by_id(session, order.id)
            self.assertEqual((stored.status, stored.credit_status), (Status.EXPIRED, CreditStatus.PENDING))
            commands = list(await session.scalars(select(CreditCommandOutbox).where(
                CreditCommandOutbox.order_id == order.id)))
            self.assertEqual(len(commands), 2)
            release = next(c for c in commands if c.routing_key == "credit.release")
            released = reply.model_copy(update={
                "request_id": release.id, "operation": CreditOperation.RELEASE,
            })
            await credit_results.handle_release_result(session, released)
            await session.commit()
            self.assertEqual((stored.status, stored.credit_status), (Status.EXPIRED, CreditStatus.SUCCEEDED))

    async def test_late_transfer_records_payment_without_exiting_dispute(self):
        order = await self.create()
        courier = uuid4()
        async with self.sessions() as session:
            await session.execute(update(ErrandRequest).where(ErrandRequest.id == order.id).values(
                status=Status.DELIVERED, credit_status=CreditStatus.SUCCEEDED,
                courier_id=courier, progress_due_at=func.clock_timestamp() + timedelta(days=1),
            ))
            await session.commit()
            await repository.receive_order(session, order.id, self.requester)
            await session.execute(update(ErrandRequest).where(ErrandRequest.id == order.id)
                                  .values(settlement_due_at=func.clock_timestamp() - timedelta(seconds=1)))
            await session.commit()
            self.assertEqual(await repository.dispute_overdue_orders(session), [order.id])
            transfer = await session.scalar(select(CreditCommandOutbox).where(
                CreditCommandOutbox.order_id == order.id,
                CreditCommandOutbox.routing_key == "credit.transfer",
            ))
            reply = CreditResult(
                request_id=transfer.id, order_id=order.id,
                operation=CreditOperation.TRANSFER,
                outcome=CreditOperationOutcome.SUCCEEDED,
            )
            await credit_results.handle_transfer_result(session, reply)
            await session.commit()
            stored = await repository.get_order_by_id(session, order.id)
            self.assertEqual((stored.status, stored.credit_status), (Status.DISPUTED, CreditStatus.SUCCEEDED))
