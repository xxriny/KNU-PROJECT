"""
/messages/* 라우터 — 팀 내 앱 내 쪽지 (followup 컨텍스트 포함).

Endpoints:
  POST   /messages                   — 쪽지 전송
  GET    /messages/inbox             — 수신함
  GET    /messages/sent              — 발신함
  GET    /messages/unread-count      — 미읽 건수 (30초 폴링용)
  PATCH  /messages/{id}/read         — 읽음 처리
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models import DirectMessage, User
from routers.auth import get_current_user

router = APIRouter(prefix="/messages", tags=["messages"])


def _new_uuid() -> str:
    return str(uuid.uuid4())


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


class SendMessageRequest(BaseModel):
    receiver_id: str
    content: str
    context_question: Optional[str] = ""
    context_domain: Optional[str] = "general"


@router.post("")
async def send_message(
    req: SendMessageRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
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


@router.get("/inbox")
async def get_inbox(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    msgs = (
        db.query(DirectMessage)
        .filter(DirectMessage.receiver_id == current_user.id)
        .order_by(DirectMessage.created_at.desc())
        .limit(100)
        .all()
    )
    return {"messages": [_to_out(m) for m in msgs]}


@router.get("/sent")
async def get_sent(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    msgs = (
        db.query(DirectMessage)
        .filter(DirectMessage.sender_id == current_user.id)
        .order_by(DirectMessage.created_at.desc())
        .limit(100)
        .all()
    )
    return {"messages": [_to_out(m) for m in msgs]}


@router.get("/unread-count")
async def get_unread_count(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
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


@router.patch("/{message_id}/read")
async def mark_read(
    message_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    msg = db.query(DirectMessage).filter(DirectMessage.id == message_id).first()
    if not msg:
        raise HTTPException(status_code=404, detail="쪽지를 찾을 수 없습니다.")
    if msg.receiver_id != current_user.id:
        raise HTTPException(status_code=403, detail="본인 수신 쪽지만 읽음 처리할 수 있습니다.")
    msg.is_read = True
    db.commit()
    return {"ok": True}
