"""
Navigator GitHub OAuth App 자격증명 (동적 로딩 지원).
"""
import os
from sqlalchemy.orm import Session
from auth.models import Team

# NAVIGATOR 앱 자체 GitHub OAuth App Client ID.
# 앱 배포 시 개발자가 한 번만 등록하면 됨 (사용자 설정 불필요).
# Device Flow는 Client Secret 없이 Client ID만으로 동작.
NAVIGATOR_GITHUB_CLIENT_ID = os.environ.get("NAVIGATOR_GITHUB_CLIENT_ID", "")


def get_github_credentials(db: Session, team_id: str = None):
    """
    GitHub OAuth 설정을 조회합니다.
    1. team_id가 있으면 해당 팀의 설정을 가져옵니다.
    2. team_id가 없으면 (로그인 전) DB에 등록된 첫 번째 팀의 설정을 확인합니다.
    3. DB에 설정이 없으면 환경변수에서 기본값을 가져옵니다.
    4. 최종 fallback: NAVIGATOR 앱 자체 OAuth App Client ID (Device Flow 전용).
    """
    team = None
    if team_id:
        team = db.query(Team).filter(Team.id == team_id).first()
    else:
        team = db.query(Team).first()

    if team and team.github_client_id and team.github_client_secret:
        return team.github_client_id, team.github_client_secret

    client_id = os.environ.get("GITHUB_OAUTH_CLIENT_ID", "")
    client_secret = os.environ.get("GITHUB_OAUTH_CLIENT_SECRET", "")

    if not client_id:
        client_id = NAVIGATOR_GITHUB_CLIENT_ID

    return client_id, client_secret


def get_device_flow_client_id(db: Session) -> str:
    """Device Flow용 Client ID 반환. 우선순위: DB팀 설정 → 환경변수 → NAVIGATOR 기본값."""
    team = db.query(Team).first()
    if team and team.github_client_id:
        return team.github_client_id

    client_id = os.environ.get("GITHUB_OAUTH_CLIENT_ID", "") or \
                os.environ.get("NAVIGATOR_GITHUB_CLIENT_ID", "")
    return client_id
