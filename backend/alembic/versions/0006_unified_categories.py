"""unify tags into categories: ordered transaction_categories m2m

A record now carries an ordered category list (position 0 = main). Old
single category_id becomes position 0; old tags become same-space
categories (created 🏷️/#8a8f98 when missing) appended after it.

Revision ID: 0006
Revises: 0005
"""
from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "transaction_categories",
        sa.Column(
            "transaction_id",
            sa.Uuid(),
            sa.ForeignKey("transactions.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "category_id",
            sa.Uuid(),
            sa.ForeignKey("categories.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_transaction_categories_category", "transaction_categories", ["category_id"])

    # 1. Old single category → main (position 0).
    op.execute(
        "INSERT INTO transaction_categories (transaction_id, category_id, position) "
        "SELECT id, category_id, 0 FROM transactions WHERE category_id IS NOT NULL"
    )
    # 2. Every tag name becomes a category in its space (unless one exists).
    op.execute(
        "INSERT INTO categories (id, space_id, name, emoji, color, sort_order) "
        "SELECT gen_random_uuid(), tg.space_id, tg.name, '🏷️', '#8a8f98', 100 "
        "FROM tags tg WHERE NOT EXISTS ("
        "  SELECT 1 FROM categories c "
        "  WHERE c.space_id = tg.space_id AND lower(c.name) = lower(tg.name))"
    )
    # 3. Tagged transactions get those categories appended after the main one
    #    (or as main when the record had no category).
    op.execute(
        "INSERT INTO transaction_categories (transaction_id, category_id, position) "
        "SELECT tt.transaction_id, c.id, "
        "       COALESCE(base.cnt, 0) - 1 + "
        "       ROW_NUMBER() OVER (PARTITION BY tt.transaction_id ORDER BY tg.name) "
        "FROM transaction_tags tt "
        "JOIN tags tg ON tg.id = tt.tag_id "
        "JOIN categories c ON c.space_id = tg.space_id AND lower(c.name) = lower(tg.name) "
        "LEFT JOIN (SELECT transaction_id, count(*) AS cnt "
        "           FROM transaction_categories GROUP BY transaction_id) base "
        "  ON base.transaction_id = tt.transaction_id "
        "ON CONFLICT (transaction_id, category_id) DO NOTHING"
    )

    op.drop_table("transaction_tags")
    op.drop_table("tags")
    op.drop_index("ix_transactions_space_category", table_name="transactions")
    op.drop_column("transactions", "category_id")


def downgrade() -> None:
    op.add_column(
        "transactions",
        sa.Column(
            "category_id",
            sa.Uuid(),
            sa.ForeignKey("categories.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_transactions_space_category", "transactions", ["space_id", "category_id"]
    )
    op.execute(
        "UPDATE transactions t SET category_id = tc.category_id "
        "FROM transaction_categories tc "
        "WHERE tc.transaction_id = t.id AND tc.position = 0"
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
    op.drop_table("transaction_categories")
