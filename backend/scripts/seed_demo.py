"""Seed a demo user + space with ~6 months of realistic transactions.

Local/staging demo data only — NEVER run against production. Deterministic
(seeded RNG) and idempotent: exits if the demo user already exists.

Run from backend/:  ../.venv/bin/python -m scripts.seed_demo
Uses the same DB_* env vars as the app.
"""

import datetime as dt
import random
from decimal import Decimal

from app import models, security
from app.db import get_engine
from app.services.seeds import seed_categories, seed_payment_methods
from sqlalchemy.orm import sessionmaker

DEMO_EMAIL = "demo@masareef.app"
DEMO_PASSWORD = "demo1234"

# (category, weekly frequency, min EGP, max EGP)
PROFILE = [
    ("Groceries", 2.0, 150, 900),
    ("Dining", 1.2, 80, 450),
    ("Transport", 3.0, 20, 150),
    ("Utilities", 0.25, 200, 700),
    ("Rent", 0.23, 7000, 7000),
    ("Health", 0.3, 60, 800),
    ("Education", 0.15, 300, 1500),
    ("Shopping", 0.5, 100, 1200),
    ("Entertainment", 0.6, 50, 400),
    ("Other", 0.4, 30, 300),
]
PAYMENT_WEIGHTS = ["Cash", "Cash", "Card", "Wallet", "Bank"]


def main() -> None:
    rng = random.Random(42)
    SessionLocal = sessionmaker(bind=get_engine(), expire_on_commit=False)
    db = SessionLocal()
    try:
        if db.query(models.User).filter(models.User.email == DEMO_EMAIL).one_or_none():
            print(f"{DEMO_EMAIL} already exists — nothing to do")
            return
        user = models.User(
            email=DEMO_EMAIL,
            password_hash=security.hash_password(DEMO_PASSWORD),
            display_name="Demo",
        )
        db.add(user)
        db.flush()
        space = models.Space(
            name="Demo Household", kind="household", currency="EGP", created_by=user.id
        )
        db.add(space)
        db.flush()
        db.add(models.SpaceMember(space_id=space.id, user_id=user.id, role="owner"))
        seed_categories(db, space.id)
        seed_payment_methods(db, space.id)
        db.flush()
        cats = {
            c.name: c.id
            for c in db.query(models.Category).filter(models.Category.space_id == space.id)
        }
        pms = {
            p.name: p.id
            for p in db.query(models.PaymentMethod).filter(
                models.PaymentMethod.space_id == space.id
            )
        }

        today = dt.date.today()
        start = (today - dt.timedelta(days=182)).replace(day=1)
        count = 0
        day = start
        while day <= today:
            for name, per_week, lo, hi in PROFILE:
                if rng.random() < per_week / 7:
                    amount = Decimal(rng.randint(lo, hi))
                    tx = models.Transaction(
                        space_id=space.id,
                        type="expense",
                        amount=amount,
                        occurred_on=day,
                        payment_method_id=pms[rng.choice(PAYMENT_WEIGHTS)],
                        paid_by=user.id,
                        created_by=user.id,
                        description="",
                    )
                    db.add(tx)
                    db.flush()
                    db.add(
                        models.TransactionCategory(
                            transaction_id=tx.id, category_id=cats[name], position=0
                        )
                    )
                    count += 1
            day += dt.timedelta(days=1)
        # Monthly salary on the 1st.
        pay = start
        while pay <= today:
            db.add(
                models.Transaction(
                    space_id=space.id,
                    type="income",
                    amount=Decimal(25000),
                    occurred_on=pay,
                    payment_method_id=pms["Bank"],
                    paid_by=user.id,
                    created_by=user.id,
                    description="Salary",
                )
            )
            count += 1
            pay = (pay + dt.timedelta(days=32)).replace(day=1)

        db.commit()
        print(f"Seeded {count} transactions for {DEMO_EMAIL} (password: {DEMO_PASSWORD})")
    finally:
        db.close()


if __name__ == "__main__":
    main()
