"""Signup / login / logout / me — cookie-session auth."""

from datetime import timedelta

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func

from app import models, security
from app.db import utcnow
from app.deps import CurrentUser, DbSession

router = APIRouter(prefix="/api/auth", tags=["auth"])

BAD_CREDENTIALS = "Wrong email or password"


class SignupBody(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)
    display_name: str = Field(min_length=1, max_length=100)


class LoginBody(BaseModel):
    email: EmailStr
    password: str


class PatchMeBody(BaseModel):
    display_name: str = Field(min_length=1, max_length=100)


def _user_json(user: models.User) -> dict:
    return {
        "id": str(user.id),
        "email": user.email,
        "display_name": user.display_name,
    }


def _start_session(db, response: Response, request: Request, user: models.User) -> None:
    token = security.new_session_token()
    db.add(
        models.UserSession(
            user_id=user.id,
            token_hash=security.hash_token(token),
            expires_at=utcnow() + timedelta(days=security.SESSION_DAYS),
            user_agent=request.headers.get("user-agent", "")[:400],
        )
    )
    security.set_session_cookie(response, request, token)


@router.post("/signup", status_code=201)
def signup(body: SignupBody, request: Request, response: Response, db: DbSession):
    email = body.email.strip().lower()
    exists = db.query(models.User).filter(func.lower(models.User.email) == email).one_or_none()
    if exists:
        raise HTTPException(status_code=409, detail="An account with this email already exists")
    user = models.User(
        email=email,
        password_hash=security.hash_password(body.password),
        display_name=body.display_name.strip(),
    )
    db.add(user)
    db.flush()  # assign user.id before the session row references it
    _start_session(db, response, request, user)
    return _user_json(user)


@router.post("/login")
def login(body: LoginBody, request: Request, response: Response, db: DbSession):
    email = body.email.strip().lower()
    ip = security.client_ip(request)
    if not security.check_login_rate(email, ip):
        raise HTTPException(status_code=429, detail="Too many attempts — try again later")
    user = db.query(models.User).filter(func.lower(models.User.email) == email).one_or_none()
    if user is None:
        # Burn comparable time as a real verify so unknown emails aren't
        # distinguishable by response latency.
        security.verify_password(security.hash_password("dummy-password"), "not-it")
        security.record_login_failure(email, ip)
        raise HTTPException(status_code=401, detail=BAD_CREDENTIALS)
    if not security.verify_password(user.password_hash, body.password):
        security.record_login_failure(email, ip)
        raise HTTPException(status_code=401, detail=BAD_CREDENTIALS)
    _start_session(db, response, request, user)
    return _user_json(user)


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response, db: DbSession):
    token = request.cookies.get(security.SESSION_COOKIE)
    if token:
        db.query(models.UserSession).filter(
            models.UserSession.token_hash == security.hash_token(token)
        ).delete()
    security.clear_session_cookie(response)


@router.get("/me")
def me(user: CurrentUser):
    return _user_json(user)


@router.patch("/me")
def patch_me(body: PatchMeBody, user: CurrentUser, db: DbSession):
    db_user = db.get(models.User, user.id)
    db_user.display_name = body.display_name.strip()
    return _user_json(db_user)
