"""Spaces, membership, invites. Non-members get 404 (not 403) so space ids
don't leak existence."""

import secrets
import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import models
from app.db import utcnow
from app.deps import CurrentUser, DbSession
from app.services.seeds import seed_categories

router = APIRouter(prefix="/api", tags=["spaces"])

KINDS = {"household", "shop", "company", "other"}


class SpaceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    kind: str = "household"
    currency: str = Field(default="EGP", min_length=3, max_length=3)


class SpacePatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    kind: str | None = None
    currency: str | None = Field(default=None, min_length=3, max_length=3)


def get_membership(db: Session, space_id: uuid.UUID, user: models.User) -> models.SpaceMember:
    m = db.get(models.SpaceMember, (space_id, user.id))
    if m is None:
        raise HTTPException(status_code=404, detail="Space not found")
    return m


def get_space_or_404(db: Session, space_id: uuid.UUID, user: models.User) -> models.Space:
    get_membership(db, space_id, user)
    space = db.get(models.Space, space_id)
    if space is None:
        raise HTTPException(status_code=404, detail="Space not found")
    return space


def _space_json(space: models.Space, role: str) -> dict:
    return {
        "id": str(space.id),
        "name": space.name,
        "kind": space.kind,
        "currency": space.currency,
        "role": role,
    }


def _validate_kind(kind: str) -> str:
    if kind not in KINDS:
        raise HTTPException(status_code=422, detail=f"kind must be one of {sorted(KINDS)}")
    return kind


@router.get("/spaces")
def list_spaces(user: CurrentUser, db: DbSession):
    rows = (
        db.query(models.Space, models.SpaceMember.role)
        .join(models.SpaceMember, models.SpaceMember.space_id == models.Space.id)
        .filter(models.SpaceMember.user_id == user.id)
        .order_by(models.Space.created_at)
        .all()
    )
    return [_space_json(s, role) for s, role in rows]


@router.post("/spaces", status_code=201)
def create_space(body: SpaceCreate, user: CurrentUser, db: DbSession):
    _validate_kind(body.kind)
    space = models.Space(
        name=body.name.strip(),
        kind=body.kind,
        currency=body.currency.upper(),
        created_by=user.id,
    )
    db.add(space)
    db.flush()
    db.add(models.SpaceMember(space_id=space.id, user_id=user.id, role="owner"))
    seed_categories(db, space.id)
    return _space_json(space, "owner")


@router.get("/spaces/{space_id}")
def get_space(space_id: uuid.UUID, user: CurrentUser, db: DbSession):
    m = get_membership(db, space_id, user)
    space = db.get(models.Space, space_id)
    return _space_json(space, m.role)


@router.patch("/spaces/{space_id}")
def patch_space(space_id: uuid.UUID, body: SpacePatch, user: CurrentUser, db: DbSession):
    m = get_membership(db, space_id, user)
    if m.role != "owner":
        raise HTTPException(status_code=403, detail="Only the owner can edit the space")
    space = db.get(models.Space, space_id)
    if body.name is not None:
        space.name = body.name.strip()
    if body.kind is not None:
        space.kind = _validate_kind(body.kind)
    if body.currency is not None:
        space.currency = body.currency.upper()
    return _space_json(space, m.role)


@router.get("/spaces/{space_id}/members")
def list_members(space_id: uuid.UUID, user: CurrentUser, db: DbSession):
    get_membership(db, space_id, user)
    rows = (
        db.query(models.SpaceMember, models.User)
        .join(models.User, models.User.id == models.SpaceMember.user_id)
        .filter(models.SpaceMember.space_id == space_id)
        .order_by(models.SpaceMember.joined_at)
        .all()
    )
    return [
        {"user_id": str(u.id), "display_name": u.display_name, "email": u.email, "role": m.role}
        for m, u in rows
    ]


@router.delete("/spaces/{space_id}/members/{user_id}", status_code=204)
def remove_member(space_id: uuid.UUID, user_id: uuid.UUID, user: CurrentUser, db: DbSession):
    me = get_membership(db, space_id, user)
    target = db.get(models.SpaceMember, (space_id, user_id))
    if target is None:
        raise HTTPException(status_code=404, detail="Member not found")
    if user_id != user.id and me.role != "owner":
        raise HTTPException(status_code=403, detail="Only the owner can remove members")
    if target.role == "owner":
        other_owners = (
            db.query(models.SpaceMember)
            .filter(
                models.SpaceMember.space_id == space_id,
                models.SpaceMember.role == "owner",
                models.SpaceMember.user_id != user_id,
            )
            .count()
        )
        if other_owners == 0:
            raise HTTPException(status_code=409, detail="The last owner cannot leave the space")
    db.delete(target)


@router.post("/spaces/{space_id}/invites", status_code=201)
def create_invite(space_id: uuid.UUID, user: CurrentUser, db: DbSession):
    get_membership(db, space_id, user)
    invite = models.SpaceInvite(
        space_id=space_id, code=secrets.token_urlsafe(12), created_by=user.id
    )
    db.add(invite)
    db.flush()
    return {"id": str(invite.id), "code": invite.code}


@router.get("/spaces/{space_id}/invites")
def list_invites(space_id: uuid.UUID, user: CurrentUser, db: DbSession):
    get_membership(db, space_id, user)
    rows = (
        db.query(models.SpaceInvite)
        .filter(models.SpaceInvite.space_id == space_id, models.SpaceInvite.revoked_at.is_(None))
        .order_by(models.SpaceInvite.created_at)
        .all()
    )
    return [{"id": str(i.id), "code": i.code} for i in rows]


@router.delete("/spaces/{space_id}/invites/{invite_id}", status_code=204)
def revoke_invite(space_id: uuid.UUID, invite_id: uuid.UUID, user: CurrentUser, db: DbSession):
    get_membership(db, space_id, user)
    invite = db.get(models.SpaceInvite, invite_id)
    if invite is None or invite.space_id != space_id:
        raise HTTPException(status_code=404, detail="Invite not found")
    invite.revoked_at = utcnow()


def _live_invite(db: Session, code: str) -> models.SpaceInvite:
    invite = (
        db.query(models.SpaceInvite)
        .filter(models.SpaceInvite.code == code, models.SpaceInvite.revoked_at.is_(None))
        .one_or_none()
    )
    if invite is None:
        raise HTTPException(status_code=404, detail="Invite not found")
    return invite


@router.get("/invites/{code}")
def preview_invite(code: str, user: CurrentUser, db: DbSession):
    invite = _live_invite(db, code)
    space = db.get(models.Space, invite.space_id)
    member_count = (
        db.query(models.SpaceMember).filter(models.SpaceMember.space_id == space.id).count()
    )
    return {"space_name": space.name, "member_count": member_count}


@router.post("/invites/{code}/accept")
def accept_invite(code: str, user: CurrentUser, db: DbSession):
    invite = _live_invite(db, code)
    space = db.get(models.Space, invite.space_id)
    existing = db.get(models.SpaceMember, (space.id, user.id))
    if existing is None:
        db.add(models.SpaceMember(space_id=space.id, user_id=user.id, role="member"))
        role = "member"
    else:
        role = existing.role
    return _space_json(space, role)
