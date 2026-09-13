from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, create_engine, func, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

FREE_SIGNUP_CREDITS = 100
SUPERADMIN_USERNAME = os.getenv("SUPERADMIN_USERNAME", "rashedhasan090")
SUPERADMIN_EMAIL = os.getenv("SUPERADMIN_EMAIL", "rashedhasan090@gmail.com")

PLANS = {
    "free": {"name": "Free", "price": "$0", "credits": 100, "features": ["100 welcome credits", "Fast Verify", "Citation Finder", "CSV export"]},
    "researcher": {"name": "Researcher", "price": "$9/mo", "credits": 1500, "features": ["1,500 monthly credits", "Deep Verify", "Research Integrity Score", "Retraction & correction checks", "JSON/PDF export"]},
    "pro": {"name": "Pro", "price": "$19/mo", "credits": 5000, "features": ["5,000 monthly credits", "Batch manuscript audit", "Claim-evidence alignment", "Citation fingerprint analysis", "Priority deep search"]},
    "lab": {"name": "Lab", "price": "$49/mo", "credits": 20000, "features": ["20,000 monthly credits", "Large batch audits", "Team-ready reporting", "Advanced integrity analytics", "Priority support"]},
    "enterprise": {"name": "Superadmin", "price": "Unlimited", "credits": None, "features": ["All features", "Unlimited verification", "Admin console", "All premium tiers unlocked"]},
}
TIER_ORDER = {"free": 0, "researcher": 1, "pro": 2, "lab": 3, "enterprise": 99}


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(String(32), default="user")
    tier: Mapped[str] = mapped_column(String(32), default="free")
    credits: Mapped[int] = mapped_column(Integer, default=FREE_SIGNUP_CREDITS)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    password_set_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    reset_token_hash: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    reset_token_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    stripe_customer_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    subscription_status: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    @property
    def is_superadmin(self) -> bool:
        return self.role == "superadmin" or self.username.lower() == SUPERADMIN_USERNAME.lower()

    @property
    def unlimited(self) -> bool:
        return self.is_superadmin or self.tier == "enterprise"


class CreditEvent(Base):
    __tablename__ = "credit_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    delta: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class VerificationRun(Base):
    __tablename__ = "verification_runs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    citation_count: Mapped[int] = mapped_column(Integer)
    mode: Mapped[str] = mapped_column(String(32))
    authentic_count: Mapped[int] = mapped_column(Integer, default=0)
    unsure_count: Mapped[int] = mapped_column(Integer, default=0)
    not_found_count: Mapped[int] = mapped_column(Integer, default=0)
    average_integrity_score: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


def _db_url() -> str:
    url = os.getenv("DATABASE_URL", "sqlite:///citeguard.db")
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://"):]
    if url.startswith("postgresql://") and "+psycopg" not in url:
        return "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


def _make_engine():
    url = _db_url()
    kwargs = {"pool_pre_ping": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    return create_engine(url, **kwargs)


ENGINE = _make_engine()


def _derive(password: str, salt: bytes, iterations: int = 600_000) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)


def hash_password(password: str) -> str:
    if len(password) < 10:
        raise ValueError("Password must be at least 10 characters.")
    salt = secrets.token_bytes(16)
    iterations = 600_000
    return f"pbkdf2_sha256${iterations}${salt.hex()}${_derive(password, salt, iterations).hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algo, iterations, salt_hex, digest_hex = encoded.split("$", 3)
        if algo != "pbkdf2_sha256":
            return False
        digest = _derive(password, bytes.fromhex(salt_hex), int(iterations)).hex()
        return hmac.compare_digest(digest, digest_hex)
    except Exception:
        return False


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def init_db() -> None:
    Base.metadata.create_all(ENGINE)
    with Session(ENGINE) as s:
        user = s.scalar(select(User).where(User.username == SUPERADMIN_USERNAME))
        if user is None:
            user = User(username=SUPERADMIN_USERNAME, email=SUPERADMIN_EMAIL.lower(), password_hash=hash_password(secrets.token_urlsafe(48)), role="superadmin", tier="enterprise", credits=1_000_000_000)
            s.add(user)
            s.flush()
        else:
            user.role, user.tier, user.email = "superadmin", "enterprise", SUPERADMIN_EMAIL.lower()
            user.credits = max(user.credits, 1_000_000_000)
        bootstrap = os.getenv("SUPERADMIN_RESET_TOKEN")
        if bootstrap and user.password_set_at is None:
            user.reset_token_hash = _token_hash(bootstrap)
            user.reset_token_expires_at = datetime.now(timezone.utc) + timedelta(days=7)
        s.commit()


def get_user(user_id: int) -> Optional[User]:
    with Session(ENGINE) as s:
        return s.get(User, user_id)


def create_user(username: str, email: str, password: str) -> User:
    username, email = username.strip(), email.strip().lower()
    if len(username) < 3:
        raise ValueError("Username must be at least 3 characters.")
    if "@" not in email:
        raise ValueError("Enter a valid email address.")
    with Session(ENGINE) as s:
        if s.scalar(select(User).where(User.username == username)):
            raise ValueError("That username is already registered.")
        if s.scalar(select(User).where(User.email == email)):
            raise ValueError("That email is already registered.")
        u = User(username=username, email=email, password_hash=hash_password(password), tier="free", credits=FREE_SIGNUP_CREDITS, password_set_at=datetime.now(timezone.utc))
        s.add(u); s.flush(); s.add(CreditEvent(user_id=u.id, delta=FREE_SIGNUP_CREDITS, reason="Free signup welcome credits")); s.commit(); s.refresh(u)
        return u


def authenticate(login: str, password: str) -> Optional[User]:
    login = login.strip()
    with Session(ENGINE) as s:
        u = s.scalar(select(User).where((User.username == login) | (User.email == login.lower())))
        if not u or not u.active or not verify_password(password, u.password_hash):
            return None
        s.expunge(u)
        return u


def create_reset_token(email: str, ttl_minutes: int = 30) -> Optional[str]:
    token = secrets.token_urlsafe(32)
    with Session(ENGINE) as s:
        u = s.scalar(select(User).where(User.email == email.strip().lower()))
        if not u:
            return None
        u.reset_token_hash = _token_hash(token)
        u.reset_token_expires_at = datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes)
        s.commit()
    return token


def reset_password(token: str, password: str) -> bool:
    now = datetime.now(timezone.utc)
    with Session(ENGINE) as s:
        u = s.scalar(select(User).where(User.reset_token_hash == _token_hash(token)))
        if not u or not u.reset_token_expires_at:
            return False
        expires = u.reset_token_expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if expires < now:
            return False
        u.password_hash = hash_password(password)
        u.password_set_at = now
        u.reset_token_hash = u.reset_token_expires_at = None
        s.commit()
        return True


def tier_allows(user: User, required: str) -> bool:
    return user.unlimited or TIER_ORDER.get(user.tier, 0) >= TIER_ORDER.get(required, 0)


def consume_credits(user_id: int, amount: int, reason: str) -> tuple[bool, int]:
    with Session(ENGINE) as s:
        u = s.get(User, user_id)
        if not u:
            return False, 0
        if u.unlimited:
            return True, u.credits
        if u.credits < amount:
            return False, u.credits
        u.credits -= amount
        s.add(CreditEvent(user_id=u.id, delta=-amount, reason=reason)); s.commit()
        return True, u.credits


def refund_credits(user_id: int, amount: int, reason: str) -> None:
    with Session(ENGINE) as s:
        u = s.get(User, user_id)
        if u and not u.unlimited and amount > 0:
            u.credits += amount; s.add(CreditEvent(user_id=u.id, delta=amount, reason=reason)); s.commit()


def record_run(user_id: int, results, mode: str) -> None:
    if not results:
        return
    avg = int(round(sum(getattr(r, "integrity_score", 0) for r in results) / len(results)))
    with Session(ENGINE) as s:
        s.add(VerificationRun(user_id=user_id, citation_count=len(results), mode=mode, authentic_count=sum(r.assessment.startswith("authentic") for r in results), unsure_count=sum(r.assessment == "unsure" for r in results), not_found_count=sum(r.assessment == "not_found" for r in results), average_integrity_score=avg)); s.commit()


def recent_runs(user_id: int, limit: int = 20) -> list[VerificationRun]:
    with Session(ENGINE) as s:
        return list(s.scalars(select(VerificationRun).where(VerificationRun.user_id == user_id).order_by(VerificationRun.created_at.desc()).limit(limit)).all())


def admin_stats() -> dict[str, int]:
    with Session(ENGINE) as s:
        return {"users": int(s.scalar(select(func.count()).select_from(User)) or 0), "runs": int(s.scalar(select(func.count()).select_from(VerificationRun)) or 0), "citations": int(s.scalar(select(func.coalesce(func.sum(VerificationRun.citation_count), 0))) or 0)}


def list_users(limit: int = 100) -> list[User]:
    with Session(ENGINE) as s:
        return list(s.scalars(select(User).order_by(User.created_at.desc()).limit(limit)).all())
