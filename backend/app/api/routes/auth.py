from fastapi import APIRouter, Depends, Request
from pymongo.errors import DuplicateKeyError

from app.api.deps import get_current_user, login_limiter
from app.core.exceptions import AuthError, ConflictError
from app.core.security import create_access_token, hash_password, verify_password
from app.db import mongo
from app.db.mongo import new_id, utcnow
from app.models.schemas import TokenOut, UserCreate, UserLogin, UserOut, UserUpdate

router = APIRouter(prefix="/auth", tags=["auth"])


def user_out(u: dict) -> UserOut:
    return UserOut(id=u["_id"], name=u["name"], email=u["email"], preferred_language=u.get("preferred_language", "en"),
                   created_at=u["created_at"])


@router.post("/register", response_model=TokenOut, status_code=201)
async def register(body: UserCreate):
    doc = {"_id": new_id(), "name": body.name.strip(), "email": body.email.lower(),
           "password_hash": hash_password(body.password), "created_at": utcnow()}
    try:
        await mongo.get_db()[mongo.USERS].insert_one(doc)
    except DuplicateKeyError as e:
        raise ConflictError("An account with this email already exists") from e
    return TokenOut(access_token=create_access_token(doc["_id"]), user=user_out(doc))


@router.post("/login", response_model=TokenOut)
async def login(body: UserLogin, request: Request):
    login_limiter.check(f"{request.client.host if request.client else 'x'}:{body.email.lower()}")
    user = await mongo.get_db()[mongo.USERS].find_one({"email": body.email.lower()})
    if not user or not verify_password(body.password, user["password_hash"]):
        raise AuthError("Incorrect email or password")
    return TokenOut(access_token=create_access_token(user["_id"]), user=user_out(user))


@router.get("/me", response_model=UserOut)
async def me(user: dict = Depends(get_current_user)):
    return user_out(user)


@router.patch("/me", response_model=UserOut)
async def update_me(body: UserUpdate, user: dict = Depends(get_current_user)):
    changes = {k: v for k, v in body.model_dump().items() if v is not None}
    if changes:
        await mongo.get_db()[mongo.USERS].update_one({"_id": user["_id"]}, {"$set": changes})
        user = {**user, **changes}
    return user_out(user)
