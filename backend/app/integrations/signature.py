"""SignatureBuilder — python-docx replacement for New Signature.ps1.
Ported from the Codes folder; every method must be idempotent."""
from __future__ import annotations
import os


class SignatureBuilder:
    system = "signature"

    def __init__(self, **cfg):
        self.cfg = cfg

    @classmethod
    def from_env(cls):
        return cls(signature_logo_path=os.getenv("SIGNATURE_LOGO_PATH"), signature_out_dir=os.getenv("SIGNATURE_OUT_DIR"))

    async def health(self):
        raise NotImplementedError

    async def build(self, sam, cfg):
        raise NotImplementedError
