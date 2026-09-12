from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel


class Credentials(BaseModel):
    username: str
    password: str


class UserResponse(BaseModel):
    id: int
    username: str
    role: str
    created_at: str


class AuthResponse(BaseModel):
    token: str
    user: UserResponse


class PasswordChange(BaseModel):
    current_password: str
    new_password: str


def password_hash(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 260_000)
    return f"260000${salt.hex()}${digest.hex()}"


def password_matches(password: str, stored: str) -> bool:
    try:
        iterations, salt, digest = stored.split("$")
        candidate = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(iterations)).hex()
        return hmac.compare_digest(candidate, digest)
    except (ValueError, TypeError):
        return False


def make_token(user_id: int, role: str) -> str:
    payload = {"sub": user_id, "role": role, "exp": int((datetime.now(timezone.utc) + timedelta(days=7)).timestamp())}
    encoded = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")
    secret = os.getenv("CLICKBAIT_JWT_SECRET", "change-this-clickbait-secret").encode()
    signature = hmac.new(secret, encoded.encode(), hashlib.sha256).hexdigest()
    return f"{encoded}.{signature}"


def decode_token(token: str) -> dict:
    try:
        encoded, signature = token.split(".")
        secret = os.getenv("CLICKBAIT_JWT_SECRET", "change-this-clickbait-secret").encode()
        expected = hmac.new(secret, encoded.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError
        payload = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
        if payload["exp"] < datetime.now(timezone.utc).timestamp():
            raise ValueError
        return payload
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        raise HTTPException(status_code=401, detail="Invalid or expired session.")


class Database:
    def __init__(self):
        self.connection_string = os.getenv("CLICKBAIT_DB_CONNECTION", "")

    def connect(self):
        if not self.connection_string:
            raise HTTPException(status_code=503, detail="Database is not configured. Set CLICKBAIT_DB_CONNECTION.")
        import pyodbc
        return pyodbc.connect(self.connection_string)

    def user(self, username: str):
        with self.connect() as connection:
            return connection.cursor().execute("SELECT UserId, Username, PasswordHash, Role, CreatedAt FROM dbo.Users WHERE Username = ?", username).fetchone()

    def user_by_id(self, user_id: int):
        with self.connect() as connection:
            return connection.cursor().execute("SELECT UserId, Username, PasswordHash, Role, CreatedAt FROM dbo.Users WHERE UserId = ?", user_id).fetchone()

    def public_user(self, row) -> UserResponse:
        return UserResponse(id=row.UserId, username=row.Username, role=row.Role, created_at=row.CreatedAt.isoformat())

    @staticmethod
    def history_item(row) -> dict:
        return {"id": row.HistoryId, "user_id": row.UserId, "headline": row.Headline, "label": row.Label, "clickbait_probability": row.ClickbaitProbability, "confidence": row.Confidence, "created_at": row.CreatedAt.isoformat()}

    def save_prediction(self, user_id: int, headline: str, result):
        with self.connect() as connection:
            connection.cursor().execute("INSERT INTO dbo.PredictionHistory (UserId, Headline, Label, ClickbaitProbability, Confidence, ResultJson) VALUES (?, ?, ?, ?, ?, ?)", user_id, headline[:500], result.label, result.clickbait_probability, result.confidence, result.model_dump_json())

    def history(self, user_id: int | None = None):
        query = "SELECT HistoryId, UserId, Headline, Label, ClickbaitProbability, Confidence, CreatedAt FROM dbo.PredictionHistory"
        parameters = ()
        if user_id is not None:
            query += " WHERE UserId = ?"
            parameters = (user_id,)
        query += " ORDER BY CreatedAt DESC"
        with self.connect() as connection:
            rows = connection.cursor().execute(query, *parameters).fetchall()
        return [self.history_item(row) for row in rows]


database = Database()
router = APIRouter()


def current_user(authorization: str | None = Header(default=None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Sign in to use this feature.")
    return decode_token(authorization[7:])


def optional_user(authorization: str | None = Header(default=None)):
    if not authorization or not authorization.startswith("Bearer "):
        return None
    return decode_token(authorization[7:])


@router.post("/auth/register", response_model=AuthResponse)
async def register(credentials: Credentials):
    if len(credentials.username.strip()) < 3 or len(credentials.password) < 4:
        raise HTTPException(status_code=400, detail="Username must be 3+ characters and password 4+ characters.")
    try:
        with database.connect() as connection:
            cursor = connection.cursor()
            cursor.execute("INSERT INTO dbo.Users (Username, PasswordHash, Role) OUTPUT INSERTED.UserId, INSERTED.Username, INSERTED.Role, INSERTED.CreatedAt VALUES (?, ?, 'user')", credentials.username.strip(), password_hash(credentials.password))
            row = cursor.fetchone()
    except Exception as error:
        if "duplicate" in str(error).lower() or "unique" in str(error).lower():
            raise HTTPException(status_code=409, detail="That username is already in use.")
        raise
    return AuthResponse(token=make_token(row.UserId, row.Role), user=database.public_user(row))


@router.post("/auth/login", response_model=AuthResponse)
async def login(credentials: Credentials):
    row = database.user(credentials.username.strip())
    if not row or not password_matches(credentials.password, row.PasswordHash):
        raise HTTPException(status_code=401, detail="Invalid username or password.")
    return AuthResponse(token=make_token(row.UserId, row.Role), user=database.public_user(row))


@router.get("/auth/me", response_model=UserResponse)
async def me(user: dict = Depends(current_user)):
    row = database.user_by_id(int(user["sub"]))
    if not row:
        raise HTTPException(status_code=401, detail="User no longer exists.")
    return database.public_user(row)


@router.get("/auth/history")
async def history(user: dict = Depends(current_user)):
    return database.history(int(user["sub"]))


@router.post("/auth/change-password")
async def change_password(change: PasswordChange, user: dict = Depends(current_user)):
    row = database.user_by_id(int(user["sub"]))
    if not row or not password_matches(change.current_password, row.PasswordHash):
        raise HTTPException(status_code=400, detail="Current password is incorrect.")
    if len(change.new_password) < 4:
        raise HTTPException(status_code=400, detail="New password must be at least 4 characters.")
    with database.connect() as connection:
        connection.cursor().execute("UPDATE dbo.Users SET PasswordHash = ? WHERE UserId = ?", password_hash(change.new_password), int(user["sub"]))
    return {"message": "Password changed successfully."}


@router.get("/admin/users")
async def admin_users(user: dict = Depends(current_user)):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required.")
    with database.connect() as connection:
        rows = connection.cursor().execute("SELECT UserId, Username, PasswordHash, Role, CreatedAt FROM dbo.Users ORDER BY CreatedAt DESC").fetchall()
    return [database.public_user(row) for row in rows]


@router.get("/admin/history")
async def admin_history(user: dict = Depends(current_user)):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required.")
    return database.history()