"""API authentication for the Task Manager backend.

Stage-1 auth: a single shared API key, checked via the `X-API-Key` header
against the `API_KEY` environment variable. This is intentionally simple —
today no endpoint needs to know *which* individual is calling, only that the
caller is a trusted client, so a shared secret is enough and avoids building
a login system nobody needs yet.

Evolution path: when the product needs real per-user identity (e.g. a task
owner allowed to edit/delete only their own tasks, or multi-tenancy),
replace `require_api_key` with an OAuth2/JWT dependency that resolves and
returns the authenticated `User` instead of `None`. The `Depends(...)`
wiring at the router level (see `api/*.py`) does not need to change shape —
only what the dependency returns and, in the route bodies, an added
ownership check against that returned user. See ARCHITECTURE.md for the
full design decision and why per-resource authorization is deferred.
"""

import os
import secrets

from fastapi import Header, HTTPException, status

API_KEY_HEADER_NAME = "X-API-Key"


def require_api_key(
    x_api_key: str | None = Header(default=None, alias=API_KEY_HEADER_NAME),
) -> None:
    """FastAPI dependency enforcing a valid API key on protected routes.

    Raises 401 if the key is missing or wrong, and 500 if the server itself
    has no `API_KEY` configured (fail closed, never silently open access).
    """
    expected = os.getenv("API_KEY")
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server misconfiguration: API_KEY is not set",
        )

    if not x_api_key or not secrets.compare_digest(x_api_key, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "API-Key"},
        )
