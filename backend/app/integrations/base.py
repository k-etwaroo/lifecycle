"""Every integration exposes health() for the dashboard and idempotent
ensure_* methods for workflows. Real clients: ldap3 (ad), msal+httpx (graph),
boto3 (aws), httpx (adobe UMAPI), HTTP call to Windows agent (exo)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class Health:
    system: str
    ok: bool
    latency_ms: float
    detail: str = ""


class Integration(Protocol):
    system: str

    async def health(self) -> Health: ...


# --- AD example -------------------------------------------------------------

@dataclass
class ADUser:
    sam: str
    dn: str
    sid: str


class ActiveDirectory:
    system = "ad"

    def __init__(self, server: str, bind_dn: str, password: str, base_dn: str):
        self._server, self._bind_dn, self._pw, self._base = server, bind_dn, password, base_dn

    async def health(self) -> Health:
        # TODO: ldap3 bind + whoami, timed
        return Health(self.system, ok=True, latency_ms=0)

    async def ensure_user(self, *, sam: str, upn: str, given: str, sn: str,
                          ou: str, department: str, manager_upn: str | None) -> ADUser:
        """Return the user if it exists, otherwise create it. Never raises on
        'already exists' – that's what makes step retries safe."""
        existing = await self.find_user(sam)
        if existing:
            return existing
        # TODO: ldap3 add + set attributes + enable + set password
        raise NotImplementedError

    async def find_user(self, sam: str) -> ADUser | None:
        raise NotImplementedError

    async def ensure_member_of(self, dn: str, groups: list[str]) -> None:
        raise NotImplementedError
