"""
[DEPRECATED] SA Analysis Node
이 모듈은 sa_advisor.py로 대체되었습니다.
기존 테스트 파일 호환성을 위해 파일만 유지합니다.
실제 파이프라인에서는 사용되지 않습니다.
"""

def sa_analysis_node(state):
    raise DeprecationWarning(
        "sa_analysis_node is deprecated. Use sa_advisor_node instead. "
        "See: pipeline/domain/sa/nodes/sa_advisor.py"
    )
