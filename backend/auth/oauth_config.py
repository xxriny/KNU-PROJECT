"""
Navigator GitHub OAuth App 자격증명 (동적 로딩 지원).
"""
import os
from sqlalchemy.orm import Session
from auth.models import Team

def get_github_credentials(db: Session, team_id: str = None):
    """
    GitHub OAuth 설정을 조회합니다.
    1. team_id가 있으면 해당 팀의 설정을 가져옵니다.
    2. team_id가 없으면 (로그인 전) DB에 등록된 첫 번째 팀의 설정을 확인합니다.
    3. DB에 설정이 없으면 환경변수에서 기본값을 가져옵니다.
    """
    team = None
    if team_id:
        team = db.query(Team).filter(Team.id == team_id).first()
    else:
        # 로그인 전에는 첫 번째 팀(초기 설정 시 생성된 팀)의 설정을 사용
        team = db.query(Team).first()

    if team and team.github_client_id and team.github_client_secret:
        return team.github_client_id, team.github_client_secret

    # Fallback to env (레거시 또는 시스템 관리자용)
    client_id = os.environ.get("GITHUB_OAUTH_CLIENT_ID", "")
    client_secret = os.environ.get("GITHUB_OAUTH_CLIENT_SECRET", "")
    
    return client_id, client_secret
