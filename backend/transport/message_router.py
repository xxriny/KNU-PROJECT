"""
앱 내 쪽지 API — 팀원 간 direct message (followup 컨텍스트 포함).

Endpoints:
  POST   /api/messages          — 쪽지 전송
  GET    /api/messages/inbox    — 수신함 (미읽 + 읽음)
  GET    /api/messages/sent     — 발신함
  PATCH  /api/messages/{id}/read — 읽음 처리
  GET    /api/messages/unread-count — 미읽 건수 (폴링용)
"""

import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth.database import get_shared_db
from auth.deps import get_current_user
from auth.shared_models import DirectMessage, User

message_router = APIRouter()


def _new_uuid() -> str:
    return str(uuid.uuid4())


# ── 요청/응답 스키마 ───────────────────────────────────────

class SendMessageRequest(BaseModel):
    receiver_id: str
    content: str
    context_question: Optional[str] = ""
    context_domain: Optional[str] = "general"


class MessageOut(BaseModel):
    id: str
    sender_id: str
    sender_name: str
    receiver_id: str
    receiver_name: str
    content: str
    context_question: str
    context_domain: str
    is_read: bool
    created_at: str


def _to_out(msg: DirectMessage) -> dict:
    return {
        "id": msg.id,
        "sender_id": msg.sender_id,
        "sender_name": msg.sender_name,
        "receiver_id": msg.receiver_id,
        "receiver_name": msg.receiver_name,
        "content": msg.content,
        "context_question": msg.context_question or "",
        "context_domain": msg.context_domain or "general",
        "is_read": bool(msg.is_read),
        "created_at": msg.created_at.isoformat() if msg.created_at else "",
    }


# ── 쪽지 전송 ─────────────────────────────────────────────

@message_router.post("/api/messages")
async def send_message(
    req: SendMessageRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_shared_db),
):
    receiver = db.query(User).filter(User.id == req.receiver_id).first()
    if not receiver:
        raise HTTPException(status_code=404, detail="수신자를 찾을 수 없습니다.")
    if receiver.team_id != current_user.team_id:
        raise HTTPException(status_code=403, detail="같은 팀원에게만 쪽지를 보낼 수 있습니다.")

    msg = DirectMessage(
        id=_new_uuid(),
        team_id=current_user.team_id,
        sender_id=current_user.id,
        sender_name=current_user.name or current_user.email,
        receiver_id=receiver.id,
        receiver_name=receiver.name or receiver.email,
        content=req.content,
        context_question=req.context_question or "",
        context_domain=req.context_domain or "general",
        is_read=False,
        created_at=datetime.utcnow(),
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return {"ok": True, "message": _to_out(msg)}


# ── 수신함 ───────────────────────────────────────────────

@message_router.get("/api/messages/inbox")
async def get_inbox(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_shared_db),
):
    msgs = (
        db.query(DirectMessage)
        .filter(DirectMessage.receiver_id == current_user.id)
        .order_by(DirectMessage.created_at.desc())
        .limit(100)
        .all()
    )
    return {"messages": [_to_out(m) for m in msgs]}


# ── 발신함 ───────────────────────────────────────────────

@message_router.get("/api/messages/sent")
async def get_sent(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_shared_db),
):
    msgs = (
        db.query(DirectMessage)
        .filter(DirectMessage.sender_id == current_user.id)
        .order_by(DirectMessage.created_at.desc())
        .limit(100)
        .all()
    )
    return {"messages": [_to_out(m) for m in msgs]}


# ── 미읽 건수 (30초 폴링용) ───────────────────────────────

@message_router.get("/api/messages/unread-count")
async def get_unread_count(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_shared_db),
):
    count = (
        db.query(DirectMessage)
        .filter(
            DirectMessage.receiver_id == current_user.id,
            DirectMessage.is_read == False,  # noqa: E712
        )
        .count()
    )
    return {"unread_count": count}


# ── 읽음 처리 ─────────────────────────────────────────────

@message_router.patch("/api/messages/{message_id}/read")
async def mark_read(
    message_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_shared_db),
):
    msg = db.query(DirectMessage).filter(DirectMessage.id == message_id).first()
    if not msg:
        raise HTTPException(status_code=404, detail="쪽지를 찾을 수 없습니다.")
    if msg.receiver_id != current_user.id:
        raise HTTPException(status_code=403, detail="본인 수신 쪽지만 읽음 처리할 수 있습니다.")
    msg.is_read = True
    db.commit()
    return {"ok": True}
