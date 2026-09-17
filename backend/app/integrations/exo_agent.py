"""ExchangeAgent — HTTPS calls to the Windows agent in /agent (runs EXO PowerShell).
Ported from the Codes folder; every method must be idempotent."""
from __future__ import annotations
import os


class ExchangeAgent:
    system = "exo_agent"

    def __init__(self, **cfg):
        self.cfg = cfg

    @classmethod
    def from_env(cls):
        return cls(exo_agent_url=os.getenv("EXO_AGENT_URL"), exo_agent_key=os.getenv("EXO_AGENT_KEY"))

    async def health(self):
        raise NotImplementedError

    async def wait_for_mailbox(self, upn, timeout_s, poll_s):
        raise NotImplementedError

    async def enable_archive(self, upn):
        raise NotImplementedError

    async def set_retention_policy(self, upn, name):
        raise NotImplementedError

    async def ensure_full_access(self, upn, delegate, automap):
        raise NotImplementedError

    async def convert_to_shared(self, upn):
        raise NotImplementedError

    async def set_forwarding(self, upn, to, keep_copy):
        raise NotImplementedError

    async def set_auto_reply(self, upn, text):
        raise NotImplementedError

    async def set_calendar_permission(self, owner, delegate, access):
        raise NotImplementedError
