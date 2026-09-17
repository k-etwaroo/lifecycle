"""Utilities tab — one-off admin tasks from the Codes folder that aren't lifecycle steps."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.deps import current_user, get_db, get_integrations
from app.models.jobs import AuditEvent

router = APIRouter(prefix="/utilities", tags=["utilities"])


class CalendarGrant(BaseModel):
    owners: list[str]            # one or many mailbox UPNs (bulk paste)
    delegate: str
    access: str = "Editor"       # Editor | Reviewer


@router.post("/calendar-access")
async def grant_calendar_access(req: CalendarGrant, db=Depends(get_db), user=Depends(current_user)):
    """Grant-CalendarPermissions / Grant-CalendarReviewerPermissions."""
    exo = get_integrations()["exo"]
    results = [await exo.set_calendar_permission(o, req.delegate, req.access) for o in req.owners]
    db.add(AuditEvent(actor=user.upn, action="calendar.grant",
                      detail={"owners": req.owners, "delegate": req.delegate, "access": req.access}))
    db.commit()
    return {"results": results}


@router.get("/users/{sam}/groups")
async def user_groups_report(sam: str, user=Depends(current_user)):
    """Capture User's groups — groups with owner, owner email, notes."""
    ad = get_integrations()["ad"]
    u = await ad.get_user(sam)
    return {"user": sam, "groups": await ad.groups_with_owners(u.dn)}


@router.get("/users/{sam}/owned-groups")
async def owned_groups_report(sam: str, user=Depends(current_user)):
    """Capture Managed By — every group this person owns."""
    ad = get_integrations()["ad"]
    u = await ad.get_user(sam)
    return {"owner": sam, "groups": await ad.groups_managed_by(u.dn)}


class ReassignOwner(BaseModel):
    group_dns: list[str]
    new_owner_sam: str
    incident: str                # ServiceNow INC######


@router.post("/groups/reassign-owner")
async def reassign_owner(req: ReassignOwner, db=Depends(get_db), user=Depends(current_user)):
    """Update Managed by field to new owner — records previous owner and INC in group notes."""
    ad = get_integrations()["ad"]
    new_dn = await ad.dn_for(req.new_owner_sam)
    done = await ad.set_managed_by(req.group_dns, new_dn,
                                   prepend_note=f"{req.incident} — reassigned by {user.upn}")
    db.add(AuditEvent(actor=user.upn, action="group.reassign_owner",
                      detail={"incident": req.incident, "count": len(done)}))
    db.commit()
    return {"reassigned": done}


@router.get("/adobe/seats")
async def adobe_seats(user=Depends(current_user)):
    """Seat usage banner from the Adobe script — feeds the dashboard."""
    adobe = get_integrations()["adobe"]
    return await adobe.seat_usage()


@router.get("/groups/ownership-report")
async def ownership_report(user=Depends(current_user)):
    """Groups to send Owners — grouped by owner, for the quarterly review email."""
    ad = get_integrations()["ad"]
    return await ad.groups_grouped_by_owner()
