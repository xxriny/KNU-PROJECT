"""
[DEPRECATED] PM Analysis Node
이 모듈은 pm_embedding.py에 통합되었습니다.
pm_embedding_node가 pm_bundle 자동 조립 + 임베딩을 수행합니다.
기존 테스트 파일 호환성을 위해 파일만 유지합니다.
"""

def pm_analysis_node(state):
    raise DeprecationWarning(
        "pm_analysis_node is deprecated. pm_embedding_node now auto-assembles pm_bundle. "
        "See: pipeline/domain/pm/nodes/pm_embedding.py"
    )
