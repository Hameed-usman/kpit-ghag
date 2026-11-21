"""
Ghag – Dashboard routers.

GET  /api/v1/dashboard/stats    — anonymous analytics (FR-9)
POST /api/v1/dashboard/approve  — council approve pending Q&A (FR-10)

See specs/api-contract.md for the full contract.
"""
from fastapi import APIRouter, HTTPException

from app.config import settings
from app.schemas import ApproveRequest, ApproveResponse, DashboardStatsResponse
from app.services import logstore

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


@router.get("/stats", response_model=DashboardStatsResponse)
async def stats() -> DashboardStatsResponse:
    """
    Return anonymised dashboard analytics.
    No auth required. Data is fully anonymised (Constitution P-4).
    """
    return logstore.get_dashboard_stats()


@router.post("/approve", response_model=ApproveResponse)
async def approve(body: ApproveRequest) -> ApproveResponse:
    """
    Approve a pending unanswered question by writing a KB answer draft.
    Validates admin_token against ADMIN_TOKEN env var.
    Returns 403 in public mode, 401 on bad token, 404 if pending_id not found, 422 if URL invalid.
    """
    if settings.public_mode:
        raise HTTPException(
            status_code=403,
            detail="Public demo mode: administrative modifications are disabled",
        )

    if not settings.admin_token or body.admin_token != settings.admin_token:
        raise HTTPException(status_code=401, detail="Invalid admin token")

    if not (body.source_url.startswith("http://") or body.source_url.startswith("https://")):
        raise HTTPException(status_code=422, detail="Invalid source_url. Must be a valid HTTP/HTTPS URL.")

    if not body.answer_text or not body.answer_text.strip():
        raise HTTPException(status_code=422, detail="Answer text cannot be empty.")

    try:
        kb_id = logstore.approve_pending_question(
            pending_id=body.pending_id,
            answer_text=body.answer_text,
            source_url=body.source_url,
        )
        return ApproveResponse(status="approved", kb_entry_id=kb_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Pending question #{body.pending_id} not found")


@router.get("/audit")
@router.post("/audit")
async def dashboard_audit():
    """Administrative audit endpoint (FR-15)."""
    if settings.public_mode:
        raise HTTPException(
            status_code=403,
            detail="Public demo mode: administrative audit access is disabled",
        )
    return {"status": "ok", "audit": "active"}

