"""FastAPI dependencies: DB session, Entra JWT auth, integration factory."""
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

import httpx
from fastapi import Depends, HTTPException, Request
from jose import jwt

from app.db import SessionLocal

TENANT_ID = os.getenv("ENTRA_TENANT_ID", "")
API_CLIENT_ID = os.getenv("ENTRA_API_CLIENT_ID", "")
DEV_BYPASS_AUTH = os.getenv("DEV_BYPASS_AUTH", "false").lower() == "true"


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@dataclass
class User:
    upn: str
    roles: list[str]


@lru_cache
def _jwks() -> dict:
    url = f"https://login.microsoftonline.com/{TENANT_ID}/discovery/v2.0/keys"
    return httpx.get(url, timeout=10).json()


def current_user(request: Request) -> User:
    if DEV_BYPASS_AUTH:
        return User(upn="dev@local", roles=["Lifecycle.Admin"])
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "missing bearer token")
    token = auth[7:]
    try:
        header = jwt.get_unverified_header(token)
        key = next(k for k in _jwks()["keys"] if k["kid"] == header["kid"])
        claims = jwt.decode(token, key, algorithms=["RS256"], audience=API_CLIENT_ID,
                            issuer=f"https://login.microsoftonline.com/{TENANT_ID}/v2.0")
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(401, f"invalid token: {exc}") from exc
    return User(upn=claims.get("preferred_username", claims.get("upn", "?")),
                roles=claims.get("roles", []))


def require_role(role: str):
    def _check(user: User = Depends(current_user)) -> User:
        if role not in user.roles and "Lifecycle.Admin" not in user.roles:
            raise HTTPException(403, f"requires {role}")
        return user
    return _check


@lru_cache
def get_integrations() -> dict:
    """Builds one client per system from environment / Key Vault-injected secrets."""
    from app.integrations.ad import ActiveDirectory
    from app.integrations.graph import Graph
    from app.integrations.exo_agent import ExchangeAgent
    from app.integrations.aws_workspaces import WorkSpaces
    from app.integrations.adobe import Adobe
    from app.integrations.signature import SignatureBuilder

    return {
        "ad": ActiveDirectory.from_env(),
        "graph": Graph.from_env(),
        "exo": ExchangeAgent.from_env(),
        "aws": WorkSpaces.from_env(),
        "adobe": Adobe.from_env(),
        "signature": SignatureBuilder.from_env(),
    }
