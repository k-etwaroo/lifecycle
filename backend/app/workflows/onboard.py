"""Onboarding workflow — mirrors New-OHAUser.ps1, NewUser-Exchange.ps1,
Create-WorkSpaces-Combined.ps1, New Signature.ps1, Adobe-Acrobat-Provisioning.ps1.
Every step is idempotent. Office/department lookups come from config/mappings.yaml."""
from __future__ import annotations

import re
import secrets
import string

from app.config import mappings as M
from app.workflows.engine import Context, StepSpec


def _base_sam(first: str, last: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (first[:1] + last).replace(" ", "").replace(".", "").lower())[:20]


def _initial_password() -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%"
    return "".join(secrets.choice(alphabet) for _ in range(16))


async def ad_create_user(ctx: Context) -> dict:
    ad, p = ctx.integrations["ad"], ctx.payload
    office = M["offices"][p["office"]]
    sam = await ad.unique_sam(_base_sam(p["first_name"], p["last_name"]))
    upn = f"{sam}@{M['domain']['upn_suffix']}"
    mail = f"{sam}@{M['domain']['primary_mail_domain']}"
    manager_dn = await ad.dn_for(p["manager_sam"]) if p.get("manager_sam") else None
    pwd = _initial_password()
    user = await ad.ensure_user(
        sam=sam, upn=upn, mail=mail, given=p["first_name"], sn=p["last_name"],
        cn=f"{p['last_name']}, {p['first_name']}", ou=office["ou"], password=pwd,
        attrs={
            "description": office["description"], "physicalDeliveryOfficeName": office["office"],
            "streetAddress": office["street"], "l": office["city"], "st": office["state"],
            "postalCode": office["postal_code"], "c": office["country"], "co": office["country_name"],
            "company": M["domain"]["company"], "title": p["job_title"], "department": p["department"],
            "scriptPath": M["domain"]["logon_script"], "mailNickname": sam,
            "proxyAddresses": [f"SMTP:{mail}", f"smtp:{sam}@{M['domain']['secondary_mail_domain']}"],
            **({"manager": manager_dn} if manager_dn else {}),
        },
    )
    # password is returned once to the job page and never persisted in step output
    ctx.transient["initial_password"] = pwd
    return {"sam": sam, "upn": upn, "mail": mail, "dn": user.dn, "sid": user.sid}


async def ad_add_groups(ctx: Context) -> dict:
    ad = ctx.integrations["ad"]
    office = M["offices"][ctx.payload["office"]]
    groups = M["common_groups"] + office["groups"] + ctx.payload.get("extra_groups", [])
    result = await ad.ensure_member_of(ctx.outputs["ad.create_user"]["dn"], groups)
    return {"added": result.added, "already": result.already, "missing": result.missing}


async def graph_wait_for_sync(ctx: Context) -> dict:
    graph = ctx.integrations["graph"]
    obj = await graph.wait_for_user(ctx.outputs["ad.create_user"]["upn"], timeout_s=1800)
    return {"object_id": obj["id"]}


async def graph_assign_licenses(ctx: Context) -> dict:
    graph, p = ctx.integrations["graph"], ctx.payload
    office = M["offices"][p["office"]]
    await graph.assign_licenses(ctx.outputs["graph.wait_for_sync"]["object_id"],
                                p["license_skus"], usage_location=office["usage_location"])
    return {"skus": p["license_skus"]}


async def exo_mailbox_settings(ctx: Context) -> dict:
    """Windows agent: wait for mailbox, enable archive, retention, 17a-4 FullAccess."""
    exo, x = ctx.integrations["exo"], M["exchange"]
    upn = ctx.outputs["ad.create_user"]["upn"]
    await exo.wait_for_mailbox(upn, timeout_s=x["mailbox_wait_timeout_s"], poll_s=x["mailbox_wait_poll_s"])
    out = {}
    if x["enable_online_archive"]:
        out["archive"] = await exo.enable_archive(upn)
    out["retention"] = await exo.set_retention_policy(upn, x["retention_policy"])
    out["delegate"] = await exo.ensure_full_access(upn, x["full_access_delegate"], automap=False)
    return out


async def aws_create_workspace(ctx: Context) -> dict:
    aws, p = ctx.integrations["aws"], ctx.payload
    target_key = p.get("workspace_target") or M["offices"][p["office"]]["workspace_target"]
    t = M["workspaces"]["targets"][target_key]
    sam = ctx.outputs["ad.create_user"]["sam"]
    username = f"{p['first_name']}.{p['last_name']}".lower() if t.get("username_rule") == "first_dot_last" else sam
    ws = await aws.ensure_workspace(
        account=t["account"], region=t["region"], directory_id=t["directory_id"],
        username=username, bundle_id=t.get("bundle_id"), bundle_name=t.get("bundle_name"),
        kms_key_arn=t.get("kms_key_arn"), kms_alias=M["workspaces"]["kms_alias"],
        running_mode=M["workspaces"]["running_mode"], encrypt=M["workspaces"]["encrypt_volumes"],
        tags={**t.get("tags", {}), "JobId": ctx.job.id},
        poll_interval_s=M["workspaces"]["poll_interval_s"], poll_max_min=M["workspaces"]["poll_max_min"],
    )
    return {"workspace_id": ws["WorkspaceId"], "state": ws["State"], "target": target_key}


async def docs_email_signature(ctx: Context) -> dict:
    """python-docx replacement for the Word COM script; stored as a job artifact."""
    sig = ctx.integrations["signature"]
    path = await sig.build(ctx.outputs["ad.create_user"]["sam"], M["signature"])
    return {"artifact": path}


async def adobe_add_user(ctx: Context) -> dict:
    adobe, p = ctx.integrations["adobe"], ctx.payload
    profile = M["adobe"]["profiles"][p["adobe_tier"]]         # "pro" | "standard"
    await adobe.ensure_user(email=ctx.outputs["ad.create_user"]["mail"], first=p["first_name"],
                            last=p["last_name"], country=M["adobe"]["default_country"])
    verified = await adobe.ensure_in_profile(ctx.outputs["ad.create_user"]["mail"], profile, retries=3)
    return {"profile": profile, "verified": verified}


ONBOARD_STEPS: list[StepSpec] = [
    StepSpec("ad.create_user",        "ad",    ad_create_user),
    StepSpec("ad.add_groups",         "ad",    ad_add_groups),
    StepSpec("graph.wait_for_sync",   "graph", graph_wait_for_sync, max_attempts=1),
    StepSpec("graph.assign_licenses", "graph", graph_assign_licenses),
    StepSpec("exo.mailbox_settings",  "exo",   exo_mailbox_settings, continue_on_failure=True),
    StepSpec("aws.create_workspace",  "aws",   aws_create_workspace,
             when=lambda c: c.payload.get("needs_workspace", True)),
    StepSpec("docs.email_signature",  "docs",  docs_email_signature, continue_on_failure=True),
    StepSpec("adobe.add_user",        "adobe", adobe_add_user, continue_on_failure=True,
             when=lambda c: bool(c.payload.get("adobe_tier"))),
]
