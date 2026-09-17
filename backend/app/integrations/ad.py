"""ActiveDirectory — ldap3 (LDAPS 636) or proxy to the Windows agent.
Ported from the Codes folder; every method must be idempotent."""
from __future__ import annotations
import os


class ActiveDirectory:
    system = "ad"

    def __init__(self, **cfg):
        self.cfg = cfg

    @classmethod
    def from_env(cls):
        return cls(ad_server=os.getenv("AD_SERVER"), ad_bind_dn=os.getenv("AD_BIND_DN"), ad_bind_password=os.getenv("AD_BIND_PASSWORD"), ad_base_dn=os.getenv("AD_BASE_DN"))

    async def health(self):
        raise NotImplementedError

    async def unique_sam(self, base):
        raise NotImplementedError

    async def dn_for(self, sam):
        raise NotImplementedError

    async def get_user(self, sam):
        raise NotImplementedError

    async def ensure_user(self, **kw):
        raise NotImplementedError

    async def ensure_member_of(self, dn, groups):
        raise NotImplementedError

    async def groups_with_owners(self, dn):
        raise NotImplementedError

    async def groups_managed_by(self, dn):
        raise NotImplementedError

    async def groups_grouped_by_owner(self):
        raise NotImplementedError

    async def add_unauth_orig(self, dn, dl_dns):
        raise NotImplementedError

    async def set_account_expiration(self, dn, when):
        raise NotImplementedError

    async def set_managed_by(self, group_dns, new_owner_dn, prepend_note):
        raise NotImplementedError

    async def disable(self, dn):
        raise NotImplementedError

    async def set_attrs(self, dn, attrs, clear):
        raise NotImplementedError

    async def reset_password(self, dn, pwd, must_change):
        raise NotImplementedError

    async def unlock(self, dn):
        raise NotImplementedError

    async def remove_from_groups(self, dn, group_dns):
        raise NotImplementedError

    async def move_to_sibling_ou(self, dn, ou_name, auto_create):
        raise NotImplementedError
