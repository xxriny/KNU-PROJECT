"""
/billing/* 라우터 — 플랜 조회, 구독 상태, Stripe 연동.

Stripe 실 연동은 STRIPE_SECRET_KEY 환경변수 설정 후 활성화됩니다.
현재는 plan_checker + webhook 수신 구조(stub)를 완성해두고
실 결제 시 stripe 패키지만 추가하면 됩니다.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from database import get_db
from models import Subscription, Team
from schemas import CheckoutRequest, PlanInfo, SubscriptionResponse

router = APIRouter(prefix="/billing", tags=["billing"])

# ── 플랜 정의 ────────────────────────────────────────────────

PLANS: dict[str, PlanInfo] = {
    "free": PlanInfo(
        id="free", name="Free", price_usd=0,
        features=["분석 3회/월", "팀원 1명", "로컬 저장"],
    ),
    "pro": PlanInfo(
        id="pro", name="Pro", price_usd=29,
        features=["무제한 분석", "팀원 5명", "GitHub 연동", "팀 스냅샷 공유"],
    ),
    "enterprise": PlanInfo(
        id="enterprise", name="Enterprise", price_usd=99,
        features=["모든 Pro 기능", "무제한 팀원", "우선 지원", "커스텀 모델 키"],
    ),
}

# Stripe 가격 ID (환경변수로 설정)
_STRIPE_PRICE = {
    "pro":        os.environ.get("STRIPE_PRICE_PRO",        ""),
    "enterprise": os.environ.get("STRIPE_PRICE_ENTERPRISE", ""),
}


# ── 헬퍼 ─────────────────────────────────────────────────────

def _get_or_create_subscription(db: Session, team_id: str) -> Subscription:
    sub = db.query(Subscription).filter(Subscription.team_id == team_id).first()
    if not sub:
        sub = Subscription(team_id=team_id, plan="free", status="active")
        db.add(sub)
        db.commit()
        db.refresh(sub)
    return sub


def check_plan(db: Session, team_id: Optional[str]) -> str:
    """팀 플랜 조회 — 없으면 'free' 반환 (plan_checker 역할)."""
    if not team_id:
        return "free"
    sub = db.query(Subscription).filter(Subscription.team_id == team_id).first()
    if not sub or sub.status not in ("active", "trialing"):
        return "free"
    return sub.plan


# ── 엔드포인트 ───────────────────────────────────────────────

@router.get("/plans")
async def list_plans():
    return {"plans": [p.model_dump() for p in PLANS.values()]}


@router.get("/subscription/{team_id}", response_model=SubscriptionResponse)
async def get_subscription(team_id: str, db: Session = Depends(get_db)):
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="팀을 찾을 수 없습니다.")
    sub = _get_or_create_subscription(db, team_id)
    return SubscriptionResponse(
        team_id=team_id,
        plan=sub.plan,
        status=sub.status,
        current_period_end=sub.current_period_end,
        stripe_subscription_id=sub.stripe_subscription_id,
    )


@router.post("/checkout")
async def create_checkout(req: CheckoutRequest, db: Session = Depends(get_db)):
    """Stripe Checkout 세션 생성. STRIPE_SECRET_KEY 없으면 미구현 응답."""
    secret_key = os.environ.get("STRIPE_SECRET_KEY", "")
    if not secret_key:
        return {
            "status": "not_configured",
            "message": "STRIPE_SECRET_KEY가 설정되지 않았습니다.",
        }

    if req.plan not in ("pro", "enterprise"):
        raise HTTPException(status_code=400, detail="지원하지 않는 플랜입니다.")

    price_id = _STRIPE_PRICE.get(req.plan, "")
    if not price_id:
        raise HTTPException(status_code=503, detail=f"STRIPE_PRICE_{req.plan.upper()} 환경변수를 설정하세요.")

    try:
        import stripe  # type: ignore
        stripe.api_key = secret_key

        sub = _get_or_create_subscription(db, req.team_id)
        customer_id = sub.stripe_customer_id

        # Stripe 고객 없으면 생성
        if not customer_id:
            team = db.query(Team).filter(Team.id == req.team_id).first()
            customer = stripe.Customer.create(metadata={"team_id": req.team_id, "team_name": team.name if team else ""})
            customer_id = customer.id
            sub.stripe_customer_id = customer_id
            db.commit()

        session = stripe.checkout.Session.create(
            customer=customer_id,
            payment_method_types=["card"],
            line_items=[{"price": price_id, "quantity": 1}],
            mode="subscription",
            success_url=req.success_url or "navigator://billing/success",
            cancel_url=req.cancel_url or "navigator://billing/cancel",
            metadata={"team_id": req.team_id, "plan": req.plan},
        )
        return {"status": "ok", "checkout_url": session.url, "session_id": session.id}

    except ImportError:
        return {"status": "not_installed", "message": "pip install stripe 후 재시도하세요."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Stripe Webhook 수신 — 구독 상태 업데이트.

    Stripe Dashboard에서 이 엔드포인트를 Webhook URL로 등록하고
    STRIPE_WEBHOOK_SECRET 환경변수를 설정하세요.
    """
    payload    = await request.body()
    sig_header = request.headers.get("stripe-signature", "")
    secret     = os.environ.get("STRIPE_WEBHOOK_SECRET", "")

    # Stripe 서명 검증 (키 있을 때만)
    event: dict = {}
    if secret:
        try:
            import stripe  # type: ignore
            stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "")
            event = stripe.Webhook.construct_event(payload, sig_header, secret)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Webhook 서명 검증 실패: {e}")
    else:
        try:
            event = json.loads(payload)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid payload")

    event_type = event.get("type", "")
    obj        = event.get("data", {}).get("object", {})
    team_id    = (obj.get("metadata") or {}).get("team_id", "")

    if event_type in ("customer.subscription.created", "customer.subscription.updated"):
        plan   = _resolve_plan_from_stripe(obj)
        status = obj.get("status", "active")
        period_end_ts = obj.get("current_period_end")
        period_end = datetime.utcfromtimestamp(period_end_ts) if period_end_ts else None

        if team_id:
            sub = _get_or_create_subscription(db, team_id)
            sub.plan                   = plan
            sub.status                 = status
            sub.stripe_subscription_id = obj.get("id")
            sub.current_period_end     = period_end
            if obj.get("customer"):
                sub.stripe_customer_id = obj["customer"]
            db.commit()

    elif event_type == "customer.subscription.deleted":
        if team_id:
            sub = db.query(Subscription).filter(Subscription.team_id == team_id).first()
            if sub:
                sub.plan   = "free"
                sub.status = "canceled"
                db.commit()

    elif event_type == "invoice.payment_failed":
        if team_id:
            sub = db.query(Subscription).filter(Subscription.team_id == team_id).first()
            if sub:
                sub.status = "past_due"
                db.commit()

    return {"status": "ok"}


def _resolve_plan_from_stripe(obj: dict) -> str:
    """Stripe 구독 오브젝트에서 플랜 ID 추출."""
    plan_meta = (obj.get("metadata") or {}).get("plan", "")
    if plan_meta in PLANS:
        return plan_meta
    # items에서 price nickname으로 추출
    items = (obj.get("items") or {}).get("data", [])
    for item in items:
        price = item.get("price") or {}
        nickname = (price.get("nickname") or "").lower()
        for plan_id in ("enterprise", "pro"):
            if plan_id in nickname:
                return plan_id
    return "pro"  # 알 수 없으면 pro로 폴백


@router.post("/subscription/{team_id}/cancel")
async def cancel_subscription(team_id: str, db: Session = Depends(get_db)):
    """구독 취소 (즉시 free로 다운그레이드)."""
    sub = db.query(Subscription).filter(Subscription.team_id == team_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="구독을 찾을 수 없습니다.")

    stripe_key = os.environ.get("STRIPE_SECRET_KEY", "")
    if stripe_key and sub.stripe_subscription_id:
        try:
            import stripe  # type: ignore
            stripe.api_key = stripe_key
            stripe.Subscription.cancel(sub.stripe_subscription_id)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Stripe 취소 실패: {e}")

    sub.plan   = "free"
    sub.status = "canceled"
    sub.stripe_subscription_id = None
    db.commit()
    return {"status": "ok", "plan": "free"}
