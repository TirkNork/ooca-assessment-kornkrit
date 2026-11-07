"""Customer, billing and service-status repositories backed by Postgres."""

from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from triage.models import BillingAccount, CustomerHistory, CustomerProfile, RegionStatus
from triage.repositories.postgres.schema import (
    BillingAccountRow,
    CustomerHistoryRow,
    CustomerRow,
    RegionStatusRow,
)


class SqlCustomerRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def get_profile(self, customer_id: str) -> CustomerProfile | None:
        with Session(self._engine) as session:
            row = session.get(CustomerRow, customer_id)
            return CustomerProfile.model_validate(row, from_attributes=True) if row else None

    def get_history(self, customer_id: str) -> CustomerHistory | None:
        with Session(self._engine) as session:
            row = session.get(CustomerHistoryRow, customer_id)
            return CustomerHistory.model_validate(row, from_attributes=True) if row else None


class SqlBillingRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def get_account(self, customer_id: str) -> BillingAccount | None:
        with Session(self._engine) as session:
            row = session.get(BillingAccountRow, customer_id)
            return BillingAccount.model_validate(row, from_attributes=True) if row else None


class SqlServiceStatusRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def get_region(self, region: str) -> RegionStatus | None:
        with Session(self._engine) as session:
            row = session.get(RegionStatusRow, region.strip().lower())
            return RegionStatus.model_validate(row, from_attributes=True) if row else None

    def regions(self) -> list[str]:
        with Session(self._engine) as session:
            return list(session.scalars(select(RegionStatusRow.region).order_by("region")))
