"""ORM models. Schema changes happen in hand-written alembic migrations;
these classes must stay in sync with backend/alembic/versions/."""

import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(sa.Text, nullable=False)
    password_hash: Mapped[str] = mapped_column(sa.Text, nullable=False)
    display_name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )


class Space(Base):
    __tablename__ = "spaces"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    kind: Mapped[str] = mapped_column(sa.Text, nullable=False, server_default="household")
    currency: Mapped[str] = mapped_column(sa.Text, nullable=False, server_default="EGP")
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )


class SpaceMember(Base):
    __tablename__ = "space_members"

    space_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid, sa.ForeignKey("spaces.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid, sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    role: Mapped[str] = mapped_column(sa.Text, nullable=False, server_default="member")
    joined_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )


class SpaceInvite(Base):
    __tablename__ = "space_invites"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid4)
    space_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid, sa.ForeignKey("spaces.id", ondelete="CASCADE"), nullable=False
    )
    code: Mapped[str] = mapped_column(sa.Text, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )
    revoked_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid4)
    space_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid, sa.ForeignKey("spaces.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    emoji: Mapped[str] = mapped_column(sa.Text, nullable=False, server_default="")
    color: Mapped[str] = mapped_column(sa.Text, nullable=False, server_default="")
    sort_order: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default="0")
    is_archived: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, server_default=sa.false()
    )


class PaymentMethod(Base):
    __tablename__ = "payment_methods"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid4)
    space_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid, sa.ForeignKey("spaces.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    icon: Mapped[str] = mapped_column(sa.Text, nullable=False, server_default="")
    sort_order: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default="0")
    is_archived: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, server_default=sa.false()
    )


class TransactionCategory(Base):
    __tablename__ = "transaction_categories"

    transaction_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid, sa.ForeignKey("transactions.id", ondelete="CASCADE"), primary_key=True
    )
    category_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid, sa.ForeignKey("categories.id", ondelete="CASCADE"), primary_key=True
    )
    # 0 = the record's MAIN category (drives the by-category chart).
    position: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default="0")


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid4)
    space_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid, sa.ForeignKey("spaces.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[str] = mapped_column(sa.Text, nullable=False, server_default="expense")
    amount: Mapped[object] = mapped_column(sa.Numeric(14, 2), nullable=False)
    occurred_on: Mapped[object] = mapped_column(sa.Date, nullable=False)
    payment_method_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid, sa.ForeignKey("payment_methods.id", ondelete="SET NULL"), nullable=True
    )
    paid_by: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    description: Mapped[str] = mapped_column(sa.Text, nullable=False, server_default="")
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
    )


class UserSession(Base):
    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(sa.Text, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )
    user_agent: Mapped[str] = mapped_column(sa.Text, nullable=False, server_default="")
