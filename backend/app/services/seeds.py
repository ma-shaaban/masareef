"""Default data seeded into every new space."""

from app import models

DEFAULT_CATEGORIES = [
    ("Groceries", "🛒", "#4f9d69"),
    ("Dining", "🍽️", "#e07a5f"),
    ("Transport", "🚗", "#3d8bd4"),
    ("Utilities", "💡", "#f2b134"),
    ("Rent", "🏠", "#8d6ba8"),
    ("Health", "💊", "#d64550"),
    ("Education", "📚", "#2a9d8f"),
    ("Shopping", "🛍️", "#e76f9b"),
    ("Entertainment", "🎬", "#f4845f"),
    ("Other", "📦", "#8a8f98"),
]


DEFAULT_PAYMENT_METHODS = [
    ("Cash", "💵"),
    ("Card", "💳"),
    ("Bank", "🏦"),
    ("Wallet", "📱"),
]


def seed_categories(db, space_id) -> None:
    for i, (name, emoji, color) in enumerate(DEFAULT_CATEGORIES):
        db.add(
            models.Category(space_id=space_id, name=name, emoji=emoji, color=color, sort_order=i)
        )


def seed_payment_methods(db, space_id) -> None:
    for i, (name, icon) in enumerate(DEFAULT_PAYMENT_METHODS):
        db.add(models.PaymentMethod(space_id=space_id, name=name, icon=icon, sort_order=i))
