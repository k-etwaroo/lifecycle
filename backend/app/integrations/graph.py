"""Graph — msal client-credentials + httpx against graph.microsoft.com.
Ported from the Codes folder; every method must be idempotent."""
from __future__ import annotations
import os


class Graph:
    system = "graph"

    def __init__(self, **cfg):
        self.cfg = cfg

    @classmethod
    def from_env(cls):
        return cls(entra_tenant_id=os.getenv("ENTRA_TENANT_ID"), graph_client_id=os.getenv("GRAPH_CLIENT_ID"), graph_client_secret=os.getenv("GRAPH_CLIENT_SECRET"))

    async def health(self):
        raise NotImplementedError

    async def wait_for_user(self, upn, timeout_s):
        raise NotImplementedError

    async def get_user(self, upn):
        raise NotImplementedError

    async def assign_licenses(self, object_id, skus, usage_location):
        raise NotImplementedError

    async def remove_all_licenses(self, object_id):
        raise NotImplementedError
