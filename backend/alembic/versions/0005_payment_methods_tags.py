"""per-space payment methods (replacing the fixed enum) + optional tags

Backfills payment_methods per existing space from the old enum values,
repoints transactions at them, then drops the old column.

Revision ID: 0005
Revises: 0004
"""
from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "payment_methods",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "space_id", sa.Uuid(), sa.ForeignKey("spaces.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("icon", sa.Text(), nullable=False, server_default=""),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_payment_methods_space_id", "payment_methods", ["space_id"])
    op.execute(
        "CREATE UNIQUE INDEX ix_payment_methods_space_lower_name "
        "ON payment_methods (space_id, lower(name)) WHERE NOT is_archived"
    )

    op.create_table(
        "tags",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "space_id", sa.Uuid(), sa.ForeignKey("spaces.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_tags_space_id", "tags", ["space_id"])
    op.execute(
        "CREATE UNIQUE INDEX ix_tags_space_lower_name "
        "ON tags (space_id, lower(name)) WHERE NOT is_archived"
    )

    op.create_table(
        "transaction_tags",
        sa.Column(
            "transaction_id",
            sa.Uuid(),
            sa.ForeignKey("transactions.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "tag_id", sa.Uuid(), sa.ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True
        ),
    )
    op.create_index("ix_transaction_tags_tag_id", "transaction_tags", ["tag_id"])

    op.add_column(
        "transactions",
        sa.Column(
            "payment_method_id",
            sa.Uuid(),
            sa.ForeignKey("payment_methods.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )

    # Backfill: every existing space gets the default set; the old enum
    # values map onto them by name ("other" gets its own row where used).
    op.execute(
        "INSERT INTO payment_methods (id, space_id, name, icon, sort_order) "
        "SELECT gen_random_uuid(), s.id, v.name, v.icon, v.sort "
        "FROM spaces s CROSS JOIN (VALUES "
        "('Cash', '💵', 0), ('Card', '💳', 1), ('Bank', '🏦', 2), ('Wallet', '📱', 3)"
        ") AS v(name, icon, sort)"
    )
    op.execute(
        "INSERT INTO payment_methods (id, space_id, name, icon, sort_order) "
        "SELECT gen_random_uuid(), t.space_id, 'Other', '➰', 4 "
        "FROM (SELECT DISTINCT space_id FROM transactions WHERE payment_method = 'other') t"
    )
    op.execute(
        "UPDATE transactions t SET payment_method_id = pm.id "
        "FROM payment_methods pm "
        "WHERE pm.space_id = t.space_id AND lower(pm.name) = t.payment_method"
    )
    op.drop_column("transactions", "payment_method")


def downgrade() -> None:
    op.add_column(
        "transactions",
        sa.Column("payment_method", sa.Text(), nullable=False, server_default="cash"),
    )
    op.execute(
        "UPDATE transactions t SET payment_method = lower(pm.name) "
        "FROM payment_methods pm WHERE pm.id = t.payment_method_id "
        "AND lower(pm.name) IN ('cash', 'card', 'bank', 'wallet', 'other')"
    )
    op.drop_column("transactions", "payment_method_id")
    op.drop_table("transaction_tags")
    op.drop_table("tags")
    op.drop_table("payment_methods")
