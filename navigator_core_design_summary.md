# Navigator 핵심 설계 요약 보고서

> **버전:** 1.0  
> **기반 문서:** `agile_engineering_strategy.md`, `implementation_design.md`  
> **핵심 키워드:** 팀 설계 협업 플랫폼, RBAC, 애자일 검증, DB 이원화

본 보고서는 Navigator 프로젝트의 세 가지 핵심 축인 **1) AUTH LAYER(인증 계층)**, **2) Agile Pipeline(애자일 파이프라인)**, **3) 데이터베이스 이원화(Separation)**에 대한 설계 명세를 구조적으로 분석하고 정리한 문서입니다.

---

## 1. AUTH LAYER (인증 및 역할 제어 계층)

기존 단일 사용자용 로컬 도구에서 **팀 단위 설계 협업 플랫폼**으로 포지셔닝을 전환함에 따라, **RBAC(역할 기반 접근 제어)** 중심의 보안 및 권한 관리를 핵심으로 설계되었습니다.

### 1.1 권한 매트릭스 (Role Matrix)
사용자 역할은 **PM**, **Engineer**, **Viewer**의 3가지로 나뉩니다.

| 기능 / 권한 | PM (관리자) | Engineer (개발자) | Viewer (참관자) |
| :--- | :---: | :---: | :---: |
| **PM/SA 분석 실행** | ✓ | - | - |
| **분석 결과 열람** | ✓ | ✓ | ✓ |
| **설계 변경 요청 (DCR)** | ✓ | ✓ | - |
| **설계 변경 승인 (DCR Approval)** | ✓ | - | - |
| **할당 태스크 확인** | ✓ | ✓ (본인) | - |
| **GitHub 대시보드 열람** | ✓ | ✓ | - |
| **팀원 관리** | ✓ | - | - |

### 1.2 인증 메커니즘
* **인증 프로토콜**: JWT(JSON Web Token)를 활용하여 사용자 인증을 처리합니다.
  * **Access Token**: 유효 기간 1시간
  * **Refresh Token**: 유효 기간 7일
* **토큰 저장**: 보안을 위해 Electron 클라이언트 내 `electron-store`를 통해 로컬에 암호화 보관됩니다.
* **FastAPI 백엔드 보안**: `Depends(get_current_user)` 의존성 주입 패턴을 적용하여, 모든 엔드포인트 요청 시 권한과 신원을 검증합니다.

### 1.3 인증 관련 핵심 DB 스키마
```sql
CREATE TABLE teams (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        VARCHAR(255) NOT NULL,
    github_repo VARCHAR(500),               -- "org/repo" 형식 연동
    created_at  TIMESTAMP DEFAULT NOW()
);

CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    team_id         UUID REFERENCES teams(id) ON DELETE CASCADE,
    name            VARCHAR(255) NOT NULL,
    email           VARCHAR(255) UNIQUE NOT NULL,
    role            VARCHAR(20) CHECK (role IN ('pm', 'engineer', 'viewer')),
    github_username VARCHAR(255),           -- Commit Analyzer 매핑용
    password_hash   VARCHAR(255) NOT NULL,
    created_at      TIMESTAMP DEFAULT NOW()
);
```

---

## 2. Agile Pipeline (애자일 파이프라인)

애자일 파이프라인은 단순히 코드를 생성하는 역할(기존 codegen)에서 벗어나, **"기획-설계 정합성 검증"** 및 **"스프린트 지능적 보조"**의 다운스트림 레이어로 재설계되었습니다. 핵심적으로 4가지의 독립적인 지능형 기능을 담당합니다.

### 2.1 영향도 분석 (Impact Analyzer)
요구사항(RTM)이 변경되거나 새로운 기능이 확장될 때 아키텍처에 미치는 물리적 영향 범위를 탐지합니다.
* **분석 기법**: RTM 기반 RAG 구조를 통해 변경 대상 `FEAT_ID`와 연결된 컴포넌트, API, DB 테이블 목록을 RAG로 고속 추출하고, LLM을 통해 간접적으로 파생되는 설계 영향도와 소요 공수(Estimated Dev Days)를 추정합니다.
* **출력 구조**:
  ```json
  {
    "impact_level": "high",
    "affected_components": ["AuthService", "PaymentService"],
    "affected_apis": ["POST /api/auth/login"],
    "estimated_dev_days": 2.5,
    "incremental_update_guide": {
      "must_change": ["sa_arch_bundle.apis에 /auth/oauth/callback 추가"],
      "should_verify": ["기존 JWT 미들웨어 OAuth 토큰 호환성"],
      "can_defer": ["소셜 계정 병합 기능"]
    }
  }
  ```

### 2.2 설계-구현 정합성 검증 (Verifier)
개발자가 구현한 코드가 SA 설계 사양(`sa_arch_bundle`)과 일치하는지 자동으로 모니터링하고 채점합니다.
* **검증 규칙**:
  * **V-001 (API 규격)**: 설계에 없는 비인가 엔드포인트 임의 추가 탐지.
  * **V-002 (의존성 방향)**: 컴포넌트 의존성 그래프(`dependencies`) 위반 탐지.
  * **V-003 (DB 스키마)**: Nullability, Column Type 불일치 검사.
  * **V-004 (보안 레이어)**: 인증 데코레이터 누락 검증.
* **Coherence Score (판정 기준)**:
  * `Score ≥ 0.90` ➔ **Pass** (통과)
  * `0.70 ≤ Score < 0.90` ➔ **Warn** (경고, 팀 리뷰 권장)
  * `Score < 0.70` ➔ **Fail** (재작업 필요)

### 2.3 GitHub 문서 발행 (Wiki Publisher)
SA 파이프라인 단계 완료 시, 최신 아키텍처 설계와 RTM을 변환하여 **GitHub Wiki로 자동 퍼블리싱**합니다. 설계 정보가 코드와 동떨어져 표류하는 '문서 부조화' 문제를 원천 해결합니다.
* **발행 구조**:
  * `Home.md` (프로젝트 요약)
  * `Requirements/RTM.md` (전체 요구사항 요구 명세)
  * `Architecture/Components.md` (컴포넌트 설계 명세)
  * `Architecture/API-Specification.md` (API 사양서)
  * `Testing/Test-Strategy.md` (단위, 통합, 시스템 테스트 전략)
  * `Project-Structure.md` (디렉토리 구조 정보)

### 2.4 지능형 업무 분배 (Task Coordinator)
AI `main_agent`가 엔지니어 개개인의 현재 누적 작업량과 기술적 전문성을 실시간 분석하여 공정하게 태스크를 배분합니다.
* **업무량 공식 (Workload Score)**:
  $$\text{Workload Score} = (\text{Commit Count} \times 1.0) + \left(\frac{\text{LOC Changed}}{200}\right) + (\text{Open Tasks} \times 2.0)$$
* **배분 로직**:
  1. 팀 평균 업무량 대비 **편차**가 적은(여유가 있는) 팀원을 1차 타깃으로 선정합니다.
  2. `sa_project_structure`가 산출한 `component_mapping`(파일-컴포넌트 매칭 테이블)을 참조하여, **해당 컴포넌트 영역에 최근 기여가 많은 전문성 높은 엔지니어에게 가중치**를 부여합니다.

---

## 3. 데이터베이스 이원화 (Database Separation)

데이터베이스의 높은 결합도를 제거하고 향후 클라우드 및 서버 환경으로의 손쉬운 마이그레이션을 보장하기 위해, **물리적인 DB 파일 및 SQLAlchemy 세션을 로컬(개인) 영역과 공유(팀 스냅샷) 영역으로 철저히 이원화**했습니다.

```
                  ┌─────────────── Navigator DB System ────────────────┐
                  │                                                    │
        ┌─────────┴─────────┐                                ┌─────────┴─────────┐
        │  1) local.db      │                                │  2) shared.db     │
        ├───────────────────┤                                ├───────────────────┤
        │ 개인 데이터 보관   │                                │ 팀 공유용 데이터  │
        │                   │                                │                   │
        │ - Users           │                                │ - Published       │
        │ - Teams           │                                │   Snapshots       │
        │ - Sessions        │                                │                   │
        │ - Memos           │                                │                   │
        │ - Agile Tasks     │                                │                   │
        └───────────────────┘                                └───────────────────┘
```

### 3.1 로컬 DB (`local.db`)
* **목적**: 개발자/기획자 개인의 고유한 작업 내역 및 환경을 격리하여 저장합니다.
* **저장 데이터**: 사용자 계정(`users`), 소속 팀(`teams`), 로컬 세션(`sessions`), 메모 아이템(`memos`), 생성된 애자일 태스크(`agile_tasks`) 등
* **ORM 바인딩**: `LOCAL_DB_URL = "sqlite:///storage/local.db"`를 사용하는 `engine`과 `SessionLocal`을 바인딩합니다.

### 3.2 공유 DB (`shared.db`)
* **목적**: 팀 단위 공유가 완료되었거나 공식 배포 및 보존 대상이 되는 데이터를 격리 보관합니다.
* **저장 데이터**: 배포 완료된 스냅샷 정보(`published_snapshots`)
* **ORM 바인딩**: `SHARED_DB_URL = "sqlite:///storage/shared.db"`를 사용하는 `shared_engine`과 `SharedSessionLocal`을 바인딩합니다.

### 3.3 아키텍처적 의의
* **결합도 분리**: 개인 계정 및 작업 내역이 팀 전체의 공유 히스토리와 얽히지 않도록 데이터베이스 연결 레벨에서 트랜잭션을 분리했습니다.
* **클라우드 스케일링 준비**: 로컬 중심의 MVP는 SQLite 이원화 구조로 가볍게 구동하고, 팀 규모 확장에 따라 백엔드 공유 데이터베이스(`shared.db`)만 PostgreSQL 또는 중앙 관리형 관계형 데이터베이스(RDB)로 손쉽게 이관(Endpoint만 교체)할 수 있도록 완벽히 대비되었습니다.
