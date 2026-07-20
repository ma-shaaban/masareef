"""transactions table

Revision ID: 0004
Revises: 0003
"""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "transactions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "space_id", sa.Uuid(), sa.ForeignKey("spaces.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("type", sa.Text(), nullable=False, server_default="expense"),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("occurred_on", sa.Date(), nullable=False),
        sa.Column(
            "category_id",
            sa.Uuid(),
            sa.ForeignKey("categories.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("payment_method", sa.Text(), nullable=False, server_default="cash"),
        sa.Column(
            "paid_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "created_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("amount > 0", name="ck_transactions_amount_positive"),
        sa.CheckConstraint("type IN ('expense', 'income')", name="ck_transactions_type"),
        sa.CheckConstraint(
            "payment_method IN ('cash', 'card', 'wallet', 'bank', 'other')",
            name="ck_transactions_payment_method",
        ),
    )
    op.create_index("ix_transactions_space_occurred", "transactions", ["space_id", "occurred_on"])
    op.create_index("ix_transactions_space_category", "transactions", ["space_id", "category_id"])


def downgrade() -> None:
    op.drop_table("transactions")
