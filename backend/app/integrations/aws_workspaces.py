"""WorkSpaces — boto3 with assume-role per account.
Ported from the Codes folder; every method must be idempotent."""
from __future__ import annotations
import os


class WorkSpaces:
    system = "aws_workspaces"

    def __init__(self, **cfg):
        self.cfg = cfg

    @classmethod
    def from_env(cls):
        return cls(aws_role_name=os.getenv("AWS_ROLE_NAME"))

    async def health(self):
        raise NotImplementedError

    async def ensure_workspace(self, **kw):
        raise NotImplementedError

    async def find_workspaces(self, username, targets):
        raise NotImplementedError

    async def terminate(self, ws):
        raise NotImplementedError

    async def stop(self, ws):
        raise NotImplementedError
