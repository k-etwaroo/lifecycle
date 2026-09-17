"""Adobe — Adobe UMAPI v2, server-to-server OAuth.
Ported from the Codes folder; every method must be idempotent."""
from __future__ import annotations
import os


class Adobe:
    system = "adobe"

    def __init__(self, **cfg):
        self.cfg = cfg

    @classmethod
    def from_env(cls):
        return cls(umapi_client_id=os.getenv("UMAPI_CLIENT_ID"), umapi_client_secret=os.getenv("UMAPI_CLIENT_SECRET"), umapi_org_id=os.getenv("UMAPI_ORG_ID"))

    async def health(self):
        raise NotImplementedError

    async def ensure_user(self, email, first, last, country):
        raise NotImplementedError

    async def ensure_in_profile(self, email, profile, retries):
        raise NotImplementedError

    async def remove_from_profiles(self, email, profiles):
        raise NotImplementedError

    async def delete_user(self, email):
        raise NotImplementedError

    async def seat_usage(self):
        raise NotImplementedError
