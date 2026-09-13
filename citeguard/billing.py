from __future__ import annotations

import os

PAYMENT_LINK_ENV = {
    "researcher": "STRIPE_RESEARCHER_LINK",
    "pro": "STRIPE_PRO_LINK",
    "lab": "STRIPE_LAB_LINK",
}


def payment_link(tier: str) -> str | None:
    env_name = PAYMENT_LINK_ENV.get(tier)
    return os.getenv(env_name) if env_name else None


def billing_configured() -> bool:
    return all(payment_link(t) for t in PAYMENT_LINK_ENV)
