"""Offboarding workflow — mirrors ImmediateActionTasks.ps1, Account Access Tasks for AD.ps1,
Capture/Update Managed By, plus the reverse of the onboarding steps."""
from __future__ import annotations

import secrets
import string

from app.config import mappings as M
from app.workflows.engine import Context, StepSpec

O = M["offboarding"]


async def ad_snapshot(ctx: Context) -> dict:
    """Capture groups (with owners/notes) and owned groups BEFORE changing anything.
    This is the 'Capture User's groups' report, kept on the job for audit."""
    ad = ctx.integrations["ad"]
    u = await ad.get_user(ctx.payload["sam"])
    return {"dn": u.dn, "upn": u.upn, "mail": u.mail,
            "member_of": await ad.groups_with_owners(u.dn),
            "owns": await ad.groups_managed_by(u.dn)}


async def ad_block_dl_send(ctx: Context) -> dict:
    """Day-of action: add the user's DN to unauthOrig on the three office DLs."""
    ad = ctx.integrations["ad"]
    dls = [o["dl"] for o in M["offices"].values()]
    return {"blocked_on": await ad.add_unauth_orig(ctx.outputs["ad.snapshot"]["dn"], dls)}


async def ad_set_expiration(ctx: Context) -> dict:
    ad = ctx.integrations["ad"]
    when = ctx.payload.get("access_until")          # ISO datetime; None = clear
    await ad.set_account_expiration(ctx.outputs["ad.snapshot"]["dn"], when)
    return {"expires": when}


async def ad_reassign_group_ownership(ctx: Context) -> dict:
    ad, p = ctx.integrations["ad"], ctx.payload
    owned = ctx.outputs["ad.snapshot"]["owns"]
    if not owned:
        return {"reassigned": []}
    new_owner_dn = await ad.dn_for(p["new_group_owner_sam"])
    note = f"{p['incident']} — ownership moved from {p['sam']} to {p['new_group_owner_sam']}"
    done = await ad.set_managed_by([g["dn"] for g in owned], new_owner_dn, prepend_note=note)
    return {"reassigned": done, "incident": p["incident"]}


async def ad_disable_user(ctx: Context) -> dict:
    ad = ctx.integrations["ad"]
    dn = ctx.outputs["ad.snapshot"]["dn"]
    await ad.disable(dn)
    attrs = {"mailNickname": ctx.payload["sam"]}
    if O["hide_from_gal"]:
        attrs["msExchHideFromAddressLists"] = True
    await ad.set_attrs(dn, attrs, clear=["manager"] if O["clear_manager"] else [])
    pwd = "".join(secrets.choice(string.ascii_letters + string.digits + "!@#$") for _ in range(24))
    await ad.reset_password(dn, pwd, must_change=False)
    await ad.unlock(dn)
    return {"disabled": True, "hidden_from_gal": O["hide_from_gal"]}


async def ad_strip_groups(ctx: Context) -> dict:
    ad = ctx.integrations["ad"]
    keep = set(O["excluded_groups"])
    groups = [g["dn"] for g in ctx.outputs["ad.snapshot"]["member_of"] if g["name"] not in keep]
    return {"removed": await ad.remove_from_groups(ctx.outputs["ad.snapshot"]["dn"], groups),
            "kept": sorted(keep)}


async def ad_move_to_disabled(ctx: Context) -> dict:
    ad = ctx.integrations["ad"]
    new_dn = await ad.move_to_sibling_ou(ctx.outputs["ad.snapshot"]["dn"],
                                         M["domain"]["disabled_ou_name"], auto_create=True)
    return {"dn": new_dn}


async def exo_offboard_mailbox(ctx: Context) -> dict:
    exo, p = ctx.integrations["exo"], ctx.payload
    upn = ctx.outputs["ad.snapshot"]["upn"]
    out = {}
    if p.get("convert_to_shared", True):
        out["shared"] = await exo.convert_to_shared(upn)
    if p.get("forward_to"):
        out["forward"] = await exo.set_forwarding(upn, p["forward_to"], keep_copy=True)
    if p.get("auto_reply"):
        out["auto_reply"] = await exo.set_auto_reply(upn, p["auto_reply"])
    return out


async def graph_remove_licenses(ctx: Context) -> dict:
    graph = ctx.integrations["graph"]
    obj = await graph.get_user(ctx.outputs["ad.snapshot"]["upn"])
    return {"removed": await graph.remove_all_licenses(obj["id"])}


async def aws_offboard_workspace(ctx: Context) -> dict:
    aws = ctx.integrations["aws"]
    found = await aws.find_workspaces(username=ctx.payload["sam"], targets=M["workspaces"]["targets"])
    action = O["workspace_action"]
    for ws in found:
        await (aws.terminate if action == "terminate" else aws.stop)(ws)
    return {"action": action, "workspaces": [w["WorkspaceId"] for w in found]}


async def adobe_remove_user(ctx: Context) -> dict:
    adobe = ctx.integrations["adobe"]
    mail = ctx.outputs["ad.snapshot"]["mail"]
    if O["adobe_action"] == "delete_user":
        return {"deleted": await adobe.delete_user(mail)}
    return {"removed_from": await adobe.remove_from_profiles(mail, list(M["adobe"]["profiles"].values()))}


OFFBOARD_STEPS: list[StepSpec] = [
    StepSpec("ad.snapshot",                 "ad",    ad_snapshot, max_attempts=1),
    StepSpec("ad.block_dl_send",            "ad",    ad_block_dl_send,
             when=lambda c: O["block_dl_send"]),
    StepSpec("ad.set_expiration",           "ad",    ad_set_expiration,
             when=lambda c: "access_until" in c.payload),
    StepSpec("ad.reassign_group_ownership", "ad",    ad_reassign_group_ownership,
             when=lambda c: O["reassign_group_ownership"] and c.payload.get("new_group_owner_sam")),
    StepSpec("ad.disable_user",             "ad",    ad_disable_user),
    StepSpec("ad.strip_groups",             "ad",    ad_strip_groups),
    StepSpec("exo.offboard_mailbox",        "exo",   exo_offboard_mailbox, continue_on_failure=True),
    StepSpec("graph.remove_licenses",       "graph", graph_remove_licenses, continue_on_failure=True),
    StepSpec("aws.offboard_workspace",      "aws",   aws_offboard_workspace, continue_on_failure=True),
    StepSpec("adobe.remove_user",           "adobe", adobe_remove_user, continue_on_failure=True),
    StepSpec("ad.move_to_disabled",         "ad",    ad_move_to_disabled),
]
