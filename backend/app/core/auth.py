from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from urllib import error, request

from fastapi import HTTPException, Request, status

from app.core.config import settings


@dataclass
class AuthUser:
    id: str
    email: str | None


def _verify_token_with_auth_service(token: str) -> tuple[int, dict | None]:
    req = request.Request(
        url=f"{settings.auth_service_url}/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
        method="GET",
    )
    try:
        with request.urlopen(req, timeout=5) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
            return resp.getcode(), payload
    except error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")
        try:
            payload = json.loads(body) if body else None
        except json.JSONDecodeError:
            payload = None
        return e.code, payload


async def get_current_user(request: Request) -> AuthUser:
    authorization = request.headers.get("authorization", "")
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization Bearer 토큰이 필요합니다",
        )
    token = parts[1].strip()

    try:
        code, payload = await asyncio.to_thread(_verify_token_with_auth_service, token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="인증 서비스를 확인할 수 없습니다",
        )

    if code != status.HTTP_200_OK or not isinstance(payload, dict):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="유효하지 않은 세션입니다",
        )

    user = payload.get("user") if isinstance(payload.get("user"), dict) else None
    user_id = user.get("id") if user else None
    if not isinstance(user_id, str) or not user_id.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="유효하지 않은 사용자 정보입니다",
        )
    email = user.get("email") if user else None
    return AuthUser(id=user_id, email=email if isinstance(email, str) else None)
