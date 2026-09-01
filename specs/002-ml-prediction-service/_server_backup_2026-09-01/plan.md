# Implementation Plan: LoL 승패 예측·설명 서비스 (시스템 구현분)

**Feature**: `002-ml-prediction-service` | **Version**: 1.1 | **Date**: 2026-09-01 | **Status**: `/speckit.tasks` **재생성 필요** (현행 [tasks.md](./tasks.md) 70개는 v1.0 기준)
**v1.1 개정** — EDA 노트북(`notebooks/eda-win-factors.ipynb`)에서 검토된 모델들을 기능으로 승격하고,
데이터 매트릭스·모델 레지스트리·외부 유사 모델 비교를 추가했다. 실측 수치를 분할 기준으로 정정했다.
**Spec**: [spec.md](./spec.md) v1.2 (미결 0건) | **Constitution**: [v1.0.0](../../.specify/memory/constitution.md)
**Branch**: `main` — 단일 브랜치 정책. 기능 구분은 `specs/<NNN-slug>/` 로만 한다(헌장 Workflow 3).

> ℹ️ `.specify/templates/plan-template.md` 가 부재해(헌장 Sync Impact Report 기록) 이 문서를 직접 작성했다.
> 헌장이 요구하는 Constitution Check 절은 아래에 온전히 포함한다.

---

## Summary

경기 스냅샷 1건을 받아 **① 승리 확률 ② 판단 근거 지표 ③ 신뢰도 경고**를 한 번의 호출로
함께 반환하는 지도학습 이진분류 서비스와, 그 결과를 보여주는 웹 데모를 만든다.

**모델 계열은 이미 확정되어 있다**(로지스틱 회귀 · 차이 지표 14개).
따라서 이 계획의 초점은 성능 탐색이 아니라 **재현·설명·경고·파리티의 구현**이다.
성능 개선 작업에는 2시간 상한을 둔다(헌장 "성능 목표의 지위").

**v1.1 이 더하는 것** — 예측 모델 하나로 끝나던 구성을 **모델 레지스트리 7종**으로 넓힌다.
EDA 노트북이 이미 만들어 둔 군집·보정·구성 비교 모델이 노트북 안에만 갇혀 있어 서비스가 쓸 수 없었다.
이것들을 아티팩트와 API 로 끌어내되, **승리 확률을 만드는 모델은 여전히 하나(M1)** 임을 구조로 못 박는다.

**설계의 중심 위험은 하나다** — 스택 B(Python + Vue/Express)가 **예측 로직을 두 곳에 만들 수 있다**는 것.
계획 전체가 이 위험을 구조로 막는 데 맞춰져 있다: 학습이 `model_params.json` 하나를 내보내고,
웹은 그 수치로 산술만 하며, 두 경로의 일치를 **홀드아웃 전량 1e-9 파리티 검증이 배포 관문으로 강제**한다.

---

## Technical Context

| 항목 | 결정 | 상태 |
|---|---|---|
| **언어 (학습·예측)** | Python 3.9.6 | ✅ `venv/` 구성됨 |
| **ML 라이브러리** | scikit-learn 1.6.1 · pandas 2.3.3 · numpy 2.0.2 · joblib 1.5.3 | ✅ 설치됨 |
| **DB 드라이버** | PyMySQL 1.2.0 (Python) · mysql2 3.24 (Node) | ✅ 설치됨 |
| **추가 Python 의존성** | jupyter · nbconvert · ipykernel · pytest | ⬜ `requirements.txt` 로 고정 |
| **언어 (서비스)** | Node.js v25.3.0 · TypeScript 5.x | ✅ Node 확인 · ⬜ TS |
| **서버** | Express 4.x | ⬜ |
| **화면** | Vue 3.4+ · Vite 5.x · Pinia 2.x | ⬜ |
| **데이터 저장소** | MariaDB 12.1.2 `ABC8pioneer4` — **읽기 전용 + View 12종 + `ml_split`** | ✅ 적용·검증 완료 (51 PASS) |
| **모델** | 로지스틱 회귀 (8종 비교 1위, 학습–검증 격차 최소) — **서빙 모델 M1** | ✅ 확정 (A1) |
| **모델 레지스트리** | M1 예측 · M2 간편 · M3 대조군 · M4 정보량통제 · M5 유형군집 · M6 신뢰도 · M7 챌린저 | 🆕 v1.1 — 아래 「모델 구성 계획」 |
| **입력** | 차이 지표 14개 (blue − red) | ✅ 확정 · View 로 구현됨 |
| **데이터셋** | gold2(2) · diff13(13) · diff14(14) · clean27(27) · clean29(29) · cluster5(중립 5축) | ✅ DB 에 존재 · ⬜ **DDL 16종 결손** |
| **평가** | 홀드아웃 20% + 5-fold 교차검증, seed 42, 분할은 `ml_split` 고정 | ✅ 확정 |
| **테스트** | pytest (Python) · `node:test` (Node) | ⬜ |
| **실행 환경** | **네이티브 — Docker 미사용**. 프로젝트 폴더 내 직접 실행 | ✅ 절대규칙 |
| **자원 제약** | 단일 처리 코어, 4인 × 4일 | 학습 실측 0.1초 — 여유 |
| **성능 목표** | 확정 0.70 / 도전 0.75 (미달을 실패로 보지 않음) | ✅ 실측 **0.7136** (`ml_split` 홀드아웃 · CV 0.730~0.737) |

**NEEDS CLARIFICATION: 0건.** 명세 미결 0건이고, 기술 결정은 [research.md](./research.md) 에서 모두 해소했다.

---

## Constitution Check

헌장 Governance 는 계획 단계에서 **각 원리에 대한 충족 여부를 명시적으로 점검**하고,
충족하지 못하는 항목은 사유와 대안을 기록할 것을 요구한다(침묵 금지).

### 원리별 점검

| 원리 | 판정 | 이 계획에서 충족되는 방식 |
|---|---|---|
| **1. 기준선 우선** | ✅ | `performance.json` 이 `baseline_accuracy` 와 `improvement_pp` 를 **필수 필드**로 갖는다. 정확도만 단독 노출하는 API 경로를 두지 않는다(`/api/report` 는 항상 함께 반환). 기준선 없는 성능 보고가 구조적으로 불가능하다 |
| **2. 누수 불가능 설계** | ✅ | 입력 계약이 `schema.json` 14개로 닫혀 있고, **계약에 없는 키는 거부**한다(추가 항목 허용 안 함). 시점 이후 정보는 애초에 이름이 없어 실수로도 들어올 수 없다. 중복 제거도 별도 단계가 아니라 **차이 지표 생성의 부산물**이다 |
| **3. 비교는 통제된 조건에서만** | ✅ | 15분 비교는 후속 이관(A4)이라 이번 범위에서 비교 자체를 실행하지 않는다. 대신 diff14 vs clean29 대조군을 **동일 분할·동일 모델·동일 검증**으로 유지한다(`v_lol_10min_clean29` 가 그래서 존재한다) |
| **4. 해석 가능성 > 점수** | ✅ | 로지스틱을 채택하고 랜덤포레스트·HistGB 를 탈락시킨 근거를 문서에 남긴다 — 안정성 위반이자 **방향(+/−)을 제시할 수 없어 FR-002 미충족**. 개별 예측 근거도 `coef × z` 라는 로그오즈 기여 그 자체를 쓰고, SHAP 등 별도 설명기를 얹지 않는다 |
| **5. 검증된 점수만 보고** | ✅ | 교차검증 평균±표준편차와 학습/검증 점수를 **항상 병기**한다. `cv_std < 0.02`·`train_cv_gap < 0.03` 이 학습의 **실패 조건**이지 사후 확인 항목이 아니다 |
| **6. 이어받을 수 있게** | ✅ | `README.md` 하나로 실행까지 도달(A8), 클린 노트북 재실행(NFR-006), 접속 정보 환경 변수(E8), 산출물 9종. **DB View DDL 을 저장소에 반입**해 데이터 계층까지 재현 범위에 넣었다 |
| **7. 모델이 말하게 한다** | ✅ | 아래 별도 점검 |

### 원리 7 상세 — 이 계획의 최대 위험 지점

웹 계층이 JS 로 확률을 계산하는 것은 **원리 7이 금지하는 "예측 로직 이중화"에 가장 근접한 설계**다.
헌장이 이를 허용하는 조건은 명확하다 — 파라미터 수치만 사용하고, 전건 일치 검증으로 정당화할 것.

| 헌장 금지 항목 | 이 계획의 차단 방식 |
|---|---|
| 규칙 하드코딩 | 웹의 연산은 `z = (x−mean)/scale` · `logit = intercept + Σ coef·z` · `sigmoid` **뿐**이다. 조건문 기반 판단이 없다 |
| 확률 수동 보정 | 서버는 원시 확률을 반환한다. 반올림·백분율 변환은 **화면 렌더링에서만** 한다 |
| 외부 모델 도입 | 웹이 읽는 파일은 `model_params.json` **하나**이며, 이 파일은 학습만 생성한다 |
| 표시 계층의 임의 상수 | 근거 목록·경고 임계값·구간 정확도까지 전부 `model_params.json` 을 통해 흘러간다. JS 에 적힌 수치 리터럴 0건 |

**검증 없는 표시 계층은 산출물로 인정하지 않는다** — 서버는 기동 시 `parity_report.json` 의
`passed` 를 확인하고, 없거나 실패면 `/api/predict` 를 503 으로 막는다.

#### v1.1 추가 점검 — 모델을 7종으로 늘려도 원리 7이 유지되는가

모델 다중화는 원리 7이 금지하는 "예측 로직 이중화"에 **두 번째로 가까운 설계**다. 다음으로 막는다.

| 위험 | 차단 방식 |
|---|---|
| 어느 모델이 답했는지 모호해짐 | 응답 계약에 **`model_id` 필수**. M2 로 답했으면 화면에도 "간편 입력 모드"가 표시된다. 무언의 대체 금지 |
| 두 모델의 확률이 갈라짐 | M1·M2 는 **서로 다른 입력 자릿수를 가진 독립 모드**이지 같은 질문의 두 답이 아니다. 같은 입력으로 둘을 동시에 호출하는 경로를 API 에 두지 않는다 |
| 참조 모델이 슬며시 서빙됨 | M3·M4·M7 은 `model_params` 를 **생성하지 않는다.** 웹이 읽을 파일 자체가 없어 서빙이 구조적으로 불가능하다 |
| 군집·보정 수치가 코드에 박힘 | M5·M6 의 결과는 `match_types.json`·`calibration.json` 으로만 흐른다. JS·Python 양쪽 모두 수치 리터럴 0건 유지 |
| 파리티 범위 누락 | 파리티는 **서빙되는 모델 전부**(M1·M2)에 대해 홀드아웃 전량으로 돈다. 서빙 모델이 늘면 파리티 대상도 자동으로 는다 |

**판정 ✅** — 늘어난 것은 *예측 경로*가 아니라 *분석 산출물*이다. 확률을 만드는 경로는 여전히
`model_params*.json` → 산술 하나뿐이고, 그 화살표마다 파리티가 걸려 있다.

### 추가 제약 점검

| 제약 | 판정 | 근거 |
|---|---|---|
| **실행 환경** — 추가 실행 계층 없이 직접 실행, DB 드라이버 직결 | ✅ | Docker 미사용. Python 서버를 따로 띄우는 대안을 **이 조항 때문에 배제**했다(research R3 대안 2) |
| **자원 제약** — 단일 코어 4일 완주 | ✅ | 학습 0.1초 · 파리티 ~2초 · 노트북 ~30초. 4일 예산의 대부분이 문서·화면에 남는다 |
| **보안** — 접속 정보 환경 변수, 저장소에 평문 금지 | ⚠️ | 코드·명세는 충족(`.env` gitignore). **단, `Intent-Plan.md` 에 DB 비밀번호가 평문으로 커밋되어 있다** — 아래 Complexity Tracking 참조 |
| **성능 목표의 지위** — 개선 작업 2시간 상한 | ✅ | 하이퍼파라미터 탐색·앙상블은 Out of Scope. 상한 도달 시 즉시 중단 |

### Workflow 점검

| 조항 | 판정 |
|---|---|
| 1. 명세 우선 — 미결 남은 채 계획 진입 금지 | ✅ 002 자체 3건 · 001 승계 3건 모두 확정 |
| 2. 기능 → 모델 → 피처 → 데이터 순서 | ✅ FR 에서 출발해 로지스틱 → 차이 지표 14개 → View 순으로 내려왔다. 성능 수치에서 역산하지 않았다 |
| 3. 단일 브랜치 | ✅ `main` 유지, 기능 브랜치 생성 없음 |
| 4. 막힐 때 순서 — 모델 교체 → 특성 공학 → 튜닝 | ✅ 튜닝은 Out of Scope. quickstart 문제 해결표에도 "튜닝 먼저 금지" 명시 |

**Gate 판정: 통과.** 위반 0건, 조건부 1건(보안 — 코드 밖 문서 이슈, 아래에 기록).

---

## 데이터 구성 계획

계획 v1.0 은 학습 입력 View 하나(`v_lol_10min_diff14`)를 기준으로 썼다. 그 뒤 EDA 가 진행되면서
**DB 의 데이터 계층이 계획서보다 앞서 자라 버렸다.** v1.1 은 그 실제 상태를 먼저 확정하고,
모델 구성 계획이 딛고 설 데이터 매트릭스를 정의한다.

### 실측 — DB 에 실제로 존재하는 것 (2026-09-01 조회)

| 종류 | 개수 | 내역 |
|---|---|---|
| BASE TABLE | 3 | `lol_matches_10min`(원천 9,879×40) · `ml_split`(고정 분할) · **`lol_analysis_10min`(22컬럼) ← 저장소에 정의 없음** |
| VIEW | **28** | 아래 표 |

**`scripts/create-views.sql` 은 이 중 12종만 정의한다. 나머지 16종과 분석 테이블 1개는 DDL 이 저장소에 없다.**
→ 초기화된 환경에서 EDA 노트북이 **재실행되지 않는다.** 원리 6·NFR-006 위반이며, 아래 Complexity Tracking 4번에 기록한다.

### 데이터 매트릭스 — 어떤 모델이 어떤 데이터를 먹는가

| 데이터셋 | View (all/train/test) | 피처 | 쓰는 모델 | DDL 반입 |
|---|---|---|---|---|
| **gold2** | `v_gold2_*` | 2 (`GoldDiff` `ExpDiff`) | **M2** 간편 입력 | ❌ 결손 |
| **diff14** ★ | `v_diff14_*` | 14 (blue−red) | **M1** 주 모델 | ⚠️ `v_lol_10min_diff14` 로 별도 정의 존재 (컬럼명 불일치) |
| **diff13** | `v_diff13_*` | 13 (diff14 − `EliteMonstersDiff`) | **M4** 정보량 통제 | ❌ 결손 |
| **clean27** | `v_clean27_*` | 27 (clean29 − elite 쌍) | M4 대조 | ❌ 결손 |
| **clean29** | `v_clean29_*` | 29 (접기 전 원본) | **M3** 대조군 | ⚠️ `v_lol_10min_clean29` 로 별도 정의 존재 |
| **cluster5** | `v_cluster5_all` `_train` | 5 중립축 | **M5** 경기 유형 | ❌ 결손 |
| neutral | `v_lol_10min_neutral` | 15 + `leadTeamWin` | M5 라벨 | ✅ |
| snapshot | `v_snapshot_features` `_train` `_test` `_feature_long` `v_feature_axis` | 시점 축 | FR-009 | ✅ |
| 요인 | `v_win_factor_stats` `v_win_factors` `v_win_factor_bins` | — | 설명·경고 | ✅ |
| 원본 | `v_base` (41컬럼 = 원천 40 + `split`) | — | 공용 베이스 | ❌ 결손 |

**분할은 전 데이터셋이 `ml_split` 하나를 공유한다** — train 7,903 / test 1,976, 전 View 에서 행 수 일치 확인.
데이터셋이 6종으로 늘어도 **비교 조건이 자동으로 통제된다**(원리 3). 이것이 View 층에 분할을 박아 둔 이유다.

### 정합해야 할 것 셋

| # | 불일치 | 조치 |
|---|---|---|
| **D1** | 같은 14피처가 `v_lol_10min_diff14`(`goldDiff`)와 `v_diff14_all`(`GoldDiff`) 두 이름 체계로 존재한다. 노트북이 `D14_MAP` 으로 매번 rename 하고 있다 | `features.py` 의 `feature_order` 를 **유일한 이름 출처**로 삼고, View 쪽을 여기에 맞춰 **한 벌로 통합**한다. rename 사전은 삭제한다 |
| **D2** | `lol_analysis_10min` 이 `gameType`(군집 결과)을 **테이블에 고정**해 두었다. 원천은 읽기 전용이라는 전제와 충돌하고, 군집을 다시 돌리면 값이 갈라진다 | 군집 결과는 **아티팩트(`match_types.json`)에만** 둔다. 이 테이블은 EDA 편의 자산으로 격하하고 학습·예측 경로에서 참조 금지 |
| **D3** | View 16종 + 분석 테이블 1개의 DDL 이 저장소에 없다 | `create-views.sql` 을 **28종 전량**으로 확장하고 검증 항목을 늘린다. **이것이 tasks 재생성 시 최우선 작업이다** |

### 시점 확장 시 (FR-009)

15분 데이터가 들어오면 고칠 곳은 v1.0 과 동일하게 `v_snapshot_features` 의 `UNION ALL` 한 블록이다.
다만 **데이터셋이 6종으로 늘었으므로 각 데이터셋 View 도 시점 축을 갖도록 같은 패턴으로 확장**해야 한다.
`create-views.sql` 을 28종으로 정리할 때 이 패턴을 미리 적용해 둔다 — 나중에 다시 손대지 않기 위해서다.

---

## 모델 구성 계획

**요청의 핵심** — 노트북에서 검토한 내용을 "분석 결과"가 아니라 **기능으로 구성**하는 것.
EDA 12·13절이 이미 만든 모델들이 현재 노트북 안에만 살아 있어, 서비스에서는 쓸 수 없다.
v1.1 은 이것들을 **모델 레지스트리**로 승격해 각각을 API 와 화면에 연결한다.

### 설계 원칙 — 모델이 여섯이어도 예측의 진실은 하나다

모델을 늘리는 순간 원리 7("예측 로직 이중화 금지")에 닿는다. 다음 셋으로 경계를 고정한다.

1. **승리 확률을 만드는 모델은 M1 하나다.** M2 는 입력 자릿수가 다른 별도 모드이며,
   응답에 `model_id` 를 필수로 실어 **어느 모델이 답했는지 숨기지 않는다.** 무언의 대체는 금지.
2. **M3·M4·M7 은 서빙 경로에 없다.** 학습 시 1회 실행되어 리포트에만 기여한다. 아티팩트 디렉터리를 분리한다.
3. **M5·M6 은 확률을 만들지 않는다.** 각각 분류 라벨과 신뢰 구간 통계를 낼 뿐이며,
   그 수치는 전부 `model_params.json` 을 통해서만 표시 계층으로 흐른다(JS 수치 리터럴 0건 유지).

### 레지스트리

| ID | 모델 | 알고리즘 | 데이터 | 산출 | 노출 기능 | 근거 |
|---|---|---|---|---|---|---|
| **M1** ★ | 기본 예측 | LogReg + StandardScaler | diff14 | `model.joblib` `model_params.json` | `POST /api/predict` · 화면 승률·근거·경고 | FR-001~008 · 확정 |
| **M2** | 간편 입력 | 동일 (별도 학습) | gold2 | `model_simple.joblib` `model_params.simple.json` | `POST /api/predict?mode=simple` · 화면 "간편 입력" 탭 | FR-012 — **선택→정식 승격 권고** |
| **M3** | 구성 대조군 | 동일 | clean29 / clean27 | `comparison.json` | `GET /api/report` 의 구성 비교표 | FR-021 · 원리 3 |
| **M4** | 정보량 통제 | 동일 | diff13 | `comparison.json` | 동일 | FR-021 |
| **M5** | 경기 유형 | KMeans (k 실루엣 선택) | cluster5 (중립 5축) | `match_types.json` | `GET /api/match-types` · 유형별 리드팀 승률 | FR-020 · SC-017 |
| **M6** | 신뢰도·보정 | 통계 산출 (학습 없음) | M1 홀드아웃 예측 | `errors.json` `calibration.json` | 경고 문구의 수치 · 화면 신뢰 배지 | FR-006 · FR-011 |
| **M7** | 챌린저 (참조 전용) | RandomForest · HistGB | diff14 | `challenger.json` | **없음 — 문서에만** | 원리 4 근거 보존 |

### 각 모델이 노트북의 어느 절에서 왔는가

| 모델 | 노트북 근거 | 이미 실측된 것 |
|---|---|---|
| M1 | 12절 — 계수·ROC·보정 | AUC 0.8113 · Brier 0.1773 |
| M2 | 12-2절 — 세 구성 벤치 | gold2 가 diff14 와 동률 (`ml_split` 0.7191 vs 0.7136) |
| M3 | 8절 — 진영 대칭성 | blue/red 상관이 부호만 반대 → 접기 무손실 |
| M4 | 12-2절 + `v_diff13` 존재 | elite 지표 제거 영향 측정 준비됨 |
| M5 | 13절 — KMeans k=4 | 중립 5축 군집, 유형별 리드팀 승률 산출됨 |
| M6 | 12-1 · 12-3절 | 격차 5구간 정확도 · 확신도 10구간 정확도 곡선 |
| M7 | `bakeoff.py` 8종 비교 | RF 학습 1.0000(암기) · HistGB 격차 +0.1387 |

### M5 — 노트북과 계획의 차이를 여기서 확정한다

| 항목 | 노트북 13절 | research R7 | **v1.1 확정** |
|---|---|---|---|
| 축 | 5개 (`일방성_골드차` `난타전_총킬` `오브젝트_총획득` `시야전_총와드` `성장_총CS`) | 4개 | **5축 채택** — 시야 축이 11절에서 "승패 정보는 없지만 경기 성격은 가른다"로 확인되었고, 유형 분류의 목적은 예측이 아니다 |
| k | 4 고정 | {2,3,4} 실루엣 선택 | **실루엣 선택 유지** — k 를 사람이 고르면 원리 7의 경계에 닿는다. 노트북의 k=4 는 선택 결과의 대조군 |
| 컬럼명 | 한글 | 영문 | **영문으로 통일** — `features.py` 가 이름의 단일 출처(D1) |
| 진영 배제 검증 | 육안 | 반전 불변성 테스트 | **테스트 강제 유지** |

### M6 — 경고의 수치가 오는 길 (FR-006 의 구현 확정)

노트북 12-3 이 만든 **확신도 밴드**를 경고 체계에 정식 편입한다. 기존 R5 의 경고 2종에 하나를 더한다.

| 경고 | 발동 | 동봉 수치 | 출처 |
|---|---|---|---|
| `out_of_range` | 지표가 `schema.json` 범위 밖 | 지표명·입력값·학습 관측 범위 | 학습 시 min/max |
| `close_game` | `abs(goldDiff) ≤ 1000` | 구간 실측 정확도(0.5956)·표본 비중(34%) | `errors.json` |
| **`low_confidence`** *(신규)* | 확신도 `abs(p−0.5)×2` 가 최하위 밴드 | 해당 밴드의 실측 정확도 | **`calibration.json` ← M6** |

`close_game` 은 입력을 보고 켜지고, `low_confidence` 는 **모델이 낸 확률을 보고 켜진다.**
둘은 자주 겹치지만 같지 않다 — 골드는 붙었는데 다른 지표가 갈린 경기가 있기 때문이다.
**임계 밴드 경계와 정확도는 코드에 적지 않고 아티팩트에서 읽는다**(원리 7).

### 학습 관문 — 모델이 늘어도 관문은 공유한다

M1·M2 는 **동일한 7개 관문**을 통과해야 아티팩트가 생성된다(NFR-004 · 원리 5).

```
① cv_std < 0.02          ② train_cv_gap < 0.03      ③ 기준선 대비 개선 ≥ +20%p
④ 공통 상위 요인 ≥ 5개    ⑤ 저장·복원 예측 일치       ⑥ 피처 수·순서가 schema 와 일치
⑦ 분할이 ml_split 과 일치 (행 수 7,903 / 1,976)
```

M3·M4·M7 은 관문 ①②만 적용한다 — 서빙되지 않으므로 배포를 막을 이유가 없고,
**오히려 관문 위반 사실 자체가 기록할 결과**다(RF 의 학습 1.0000 처럼).

### 실행 예산

| 모델 | 학습 시간 실측/예상 | 비고 |
|---|---|---|
| M1 · M2 · M3 · M4 | 각 0.1초 | 로지스틱, 단일 코어 |
| M5 | ~1초 | KMeans × k 3회 |
| M6 | ~0.1초 | 집계만 |
| M7 | ~52초 | RF 14.3s + HistGB 37.2s — **CI 성격, 1회만** |

전체 재학습이 **1분 이내**다. 모델을 6종으로 늘려도 헌장의 자원 제약(단일 코어 4일)에 영향이 없다.
성능 개선 2시간 상한은 **그대로 유효하다** — 이 확장은 성능 탐색이 아니라 기능 구성이다.

---

## 외부 유사 모델 비교 (요구사항 2)

같은 문제를 푼 외부 결과와 대조했다. 목적은 두 가지 — **① 우리 천장이 데이터의 성질인지 우리 실수인지 가르는 것,
② 로지스틱 채택(원리 4)이 성능 희생인지 확인하는 것.**

### 비교표

| 출처 | 데이터 | 시점 | 모델 | 보고 정확도 |
|---|---|---|---|---|
| **본 프로젝트** | 9,879경기 × 40컬럼 | **10분** | 로지스틱 (diff14) | **0.7136** (`ml_split` 홀드아웃) · CV 0.730~0.737 |
| Kaggle *LoL Diamond Ranked Games (10 min)* 공개 커널 다수 | **9,879경기 × 40컬럼** | 10분 | 로지스틱 | ~0.73 |
| 〃 | 〃 | 10분 | XGBoost / RF | ~0.72 |
| Lafrance & Grewal (2026, 티어 효과 연구) | 20,781경기 (Riot API) | **10분** | XGBoost (최고) | **0.727** — 전 모델 0.719~0.727 |
| arXiv 2309.02449 *Real-Time Result Prediction* | 비공개 | 경기 진행 **60~80%** | LightGBM (최고) | 0.8162 |
| MOBA 승률 예측 리뷰 · 앙상블 연구 | 다양 | **경기 전체/후반** | LightGBM · 하이브리드 앙상블 | 0.95~0.98 |

### 여기서 나온 결론 넷

**① 우리 원천은 공개 Kaggle 데이터셋과 동일한 형태다.** 행 수 9,879 와 컬럼 수 40 이 정확히 일치한다.
모집단은 **다이아몬드~마스터 솔로큐**이며, 001 명세가 확장 데이터를 "프로 경기"로 적어 둔 것과 다르다.
→ **후속 15분 비교 시 반드시 같은 티어로 맞춰야 한다.** 다르면 시점 효과가 아니라 표본 효과를 재게 된다(원리 3).
이 사실을 `model_card.md` 의 "사용 금지 상황"에 명시한다 — 브론즈·프로 경기에 이 모델을 쓰면 안 된다.

**② 0.72~0.73 은 우리 한계가 아니라 10분 시점의 한계다.** 20,781경기를 따로 수집한 독립 연구가
같은 시점에서 0.719~0.727 을 보고했다. 우리 실측(0.7136~0.7328)이 같은 대역에 있다.
→ 001 A5 의 "0.75 도달 곤란" 판단이 외부 근거로 뒷받침된다. **성능 개선 2시간 상한은 정당하다.**

**③ XGBoost 도 로지스틱을 못 이긴다 — 10분 시점에서는.** 외부 연구의 최고 모델(XGBoost 0.727)과
로지스틱(~0.73)의 차이가 오차 범위다. 우리 `bakeoff.py` 결과(로지스틱 1위, HistGB 최하위)와 방향이 같다.
→ 원리 4(해석 가능성 우선) 채택이 **성능을 포기한 선택이 아니다.** M7 챌린저 모델이 이 비교를 저장소 안에서 재현한다.

**④ 0.95 이상 보고들은 우리와 비교 대상이 아니다.** 전부 경기 후반 또는 전체 경기 데이터를 쓴다.
arXiv 연구가 "진행 60~80% 구간에서 0.8162"로 보고한 것이 이 관계를 잘 보여준다 — **정확도는 시점의 함수다.**
→ 이런 수치를 목표로 인용하면 원리 3 위반이다. `model_card.md` 의 "한계" 절에 **이 비교를 그대로 적어**
읽는 사람이 0.71 을 낮은 점수로 오해하지 않게 한다.

> **비교의 규칙** — 외부 수치를 인용할 때는 **① 관측 시점 ② 모집단 티어 ③ 분할 방식**을 함께 적는다.
> 셋 중 하나라도 다르면 "참고"이지 "비교"가 아니다.

### 참고 문헌

- [Kaggle — League of Legends Diamond Ranked Games (10 min)](https://www.kaggle.com/datasets/bobbyscience/league-of-legends-diamond-ranked-games-10-min)
- [Kaggle 커널 — League of Legends 10 mins prediction](https://www.kaggle.com/code/shengkunwang/league-of-legends-10-mins-prediction/)
- [Lafrance & Grewal — Determining the Effects of League of Legends Ranked Tiers on Outcome Prediction Models (ScienceDirect)](https://www.sciencedirect.com/science/article/pii/S1875952126000108)
- [arXiv 2309.02449 — League of Legends: Real-Time Result Prediction](https://arxiv.org/abs/2309.02449)
- [Win Prediction in Multi-Player Esports: Live Professional Match Prediction (White Rose)](https://eprints.whiterose.ac.uk/id/eprint/152931/1/Win_Prediction_in_Multi_Player_Esports_Live_Professional_Match_Prediction.pdf)
- [Towards Data Science — Using Machine Learning to Understand League of Legends](https://towardsdatascience.com/the-path-to-a-victorious-league-of-legends-match-40d51a1a089e/)

---

## Project Structure

```
project2608/
├── .env.example / .env(gitignored)      접속 정보는 환경 변수로만
├── requirements.txt                  ⬜ Python 의존성 고정
├── Makefile                          ⬜ views -> train -> parity -> notebook
│
├── scripts/                          ✅ DB 계층 (Node)
│   ├── _db.js                           공용 접속 헬퍼 (.env 자동 로드)
│   ├── create-views.sql              ⚠️ View 12종 DDL — **DB 의 28종 중 12종만. 16종 결손(D3)**
│   ├── create-views.js               ✅ 적용 + 51항목 검증 — 확장 시 항목 수도 늘어난다
│   └── (기존 실측 스크립트 6종)          bakeoff · interp · err · db-check · db-profile · preprocess-export
│
├── ml/                               ⬜ 학습·예측의 단일 진실
│   ├── config.py                        SNAPSHOT_MINUTE · 경로 · seed 42 — 시점 분기가 여기 한 곳뿐
│   ├── features.py                      ★ feature_order 단일 상수. schema·params·순서가 전부 여기서 파생
│   ├── dataset.py                       View 조회 + 불변식 검사(행수·유니크·NULL·균형·피처수)
│   ├── train.py                         파이프라인 학습 -> 7개 관문 -> 아티팩트 6종 -> 저장·복원 검증
│   ├── predict.py                       ★ predict(payload) -> dict / predict_batch / CLI
│   ├── explain.py                       표준화 계수 × 순열 중요도 교차 -> 공통 상위
│   ├── evaluate.py                      성능·오류 리포트 (기준선 병기 강제)
│   ├── match_types.py                   M5 경기 유형 군집 (cluster5 중립 5축 + KMeans)
│   ├── calibration.py                🆕 M6 확신도 밴드·보정 — low_confidence 경고의 수치 출처
│   ├── compare.py                    🆕 M3·M4 구성 대조 (gold2·diff13·diff14·clean27·clean29)
│   ├── challenger.py                 🆕 M7 참조 전용 (RF·HistGB) — 서빙 경로 없음
│   ├── registry.py                   🆕 모델 레지스트리 — id·데이터셋·아티팩트 경로의 단일 출처
│   └── parity.py                        홀드아웃 전량 1e-9 전건 대조
│
├── artifacts/10min/                  ⬜ 시점별 분리 — 15분 확보 시 artifacts/15min/ 이 나란히 생긴다
│   ├── model.joblib                     M1 — 전처리 포함 파이프라인 전체
│   ├── model_simple.joblib           🆕 M2 — 간편 입력 (gold2)
│   ├── schema.json / schema.simple.json 입력 계약 14개 / 2개
│   ├── model_params.json                웹 계층의 유일한 입력 (M1)
│   ├── model_params.simple.json      🆕 M2 용 — 같은 스키마, 별도 파일
│   ├── performance.json / errors.json / match_types.json / parity_report.json
│   ├── calibration.json              🆕 M6 — 확신도 밴드별 정확도
│   ├── comparison.json               🆕 M3·M4 — 6개 구성 동일 분할 비교
│   └── challenger.json               🆕 M7 — 참조 모델 성적 (문서 인용용)
│
├── backend/                          ⬜ Express — 표시 계층
│   └── src/
│       ├── predictor.js                 model_params.json 산술만. 수치 리터럴 0건
│       ├── routes.js                    OpenAPI 7개 경로
│       ├── server.js                    기동 시 parity 확인 -> 실패면 /api/predict 503
│       └── parity-run.js                파리티 검증이 호출하는 CLI (predictor.js 재사용)
│
├── frontend/                         ⬜ Vue 3 + Vite + Pinia
│   └── src/                             입력 폼(/api/schema 로 생성) · 승률 · 근거 · 경고 한 화면
│
├── notebooks/final_analysis.ipynb    ⬜ 얇게 — ml/ 호출 + 표·그림만
├── docs/model_card.md                ⬜ 용도·성능·금지상황·한계 4개 절
├── README.md                         ⬜ 최종 산출물 (6개 절)
│
└── specs/002-ml-prediction-service/
    ├── spec.md ✅ · plan.md ✅ · research.md ✅ · data-model.md ✅ · quickstart.md ✅
    └── contracts/ ✅  README · db-views.md · schema.contract.json
                       prediction-result.schema.json · model-params.schema.json · web-api.openapi.yaml
```

**구조가 말하는 것 한 가지** — `ml/` 과 `backend/` 사이에 화살표가 하나뿐이다(`model_params.json`).
그 화살표에 파리티 검증이 걸려 있다. 다른 경로로 수치가 흐르면 그것이 곧 버그다.

---

## Phase 0 — Research ✅ 완료

→ [research.md](./research.md) · 13개 항목

주요 결정: 차이 지표 14개의 유도 규칙(R1) · 시점 인자 구조(R2) · 웹 산술 이식(R3) ·
오프라인 전건 파리티(R4) · 경고 규칙(R5) · 근거 교차 산출(R6) · 경기 유형 KMeans(R7) ·
저장 검증(R8) · 노트북 클린 실행(R9) · 버전 고정(R10) · 데이터 경로(R11) · 테스트 도구(R12)

**미해소 2건** (계획 진행을 막지 않음):
1. **14피처 실측 수치의 재현 근거 부재** — `evidence/measured-facts.md` 는 29피처 기준만 담고 있다.
   Phase 2 최초 학습에서 재산출해 evidence 를 갱신한다. 재산출값이 명세와 다르면 **문서가 실측을 따른다**(원리 5)
2. **SC-010 제3자 README 실행 확인** — 자동화 대상이 아니다. 팀 내 1인이 초기화 환경에서 수동 수행

---

## Phase 1 — Design & Contracts ✅ 완료

→ [data-model.md](./data-model.md) · [contracts/](./contracts/) · [quickstart.md](./quickstart.md)

### 산출된 계약

| 계약 | 검증 상태 |
|---|---|
| [`db-views.md`](./contracts/db-views.md) | ✅ **DB 에 적용·검증 완료** — 51 PASS / 0 FAIL |
| [`schema.contract.json`](./contracts/schema.contract.json) | ✅ 예시가 14개·순서 일치 확인 |
| [`prediction-result.schema.json`](./contracts/prediction-result.schema.json) | ✅ 5키·factors≥5·크기 내림차순·공통요인만 확인 |
| [`model-params.schema.json`](./contracts/model-params.schema.json) | ✅ 배열 길이 일치·범위 키 일치·scale>0 확인 |
| [`web-api.openapi.yaml`](./contracts/web-api.openapi.yaml) | ✅ YAML 파싱·Snapshot 14개가 `feature_order` 와 순서 일치 확인 |

계약끼리 교차 검증했다 — `feature_order` 가 세 파일에서 같은 순서인지 실제로 대조했고, 일치했다.

### 데이터 계층은 이미 서 있다

계획 도중 **DB View 를 적용·검증하고 DDL 을 저장소에 반입**했다. 계획서가 "만들 것"으로만
남겨 두면 원리 6(재현 가능한 절차)의 첫 단계가 비어 있게 되기 때문이다.

| 층 | View | 역할 |
|---|---|---|
| 피처 | `v_lol_10min_diff14` · `clean29` · `simple2` · `neutral` | 학습 입력 · 대조군 · 간편 입력 · 경기 유형 |
| 시점 | `v_feature_axis` · `v_snapshot_features` · `v_snapshot_train` / `_test` · `v_snapshot_feature_long` | FR-009 시점 축 + 고정 분할 |
| 요인 | `v_win_factor_stats` · `v_win_factors` · `v_win_factor_bins` | FR-002 · FR-007 · 001-FR-010 |

**분할이 `ml_split` 테이블로 DB 에 고정되어 있다**(train 7,903 / test 1,976).
`ml/dataset.py` 는 분할을 다시 뽑지 않고 읽는다 — 재학습해도 같은 경기가 같은 쪽에 남아,
"우연히 좋은 분할"이 성능으로 둔갑할 수 없다(원리 5).

**15분 확보 시 고칠 곳은 `v_snapshot_features` 의 `UNION ALL` 한 블록뿐이다.**
FR-009 의 "절차 수정 없이 재실행"이 Python 코드가 아니라 SQL 구조 수준에서 성립한다.

### Agent context

`.specify/scripts/bash/update-agent-context.sh` 가 **부재**해 자동 갱신을 수행하지 못했다.
현재 저장소에 `CLAUDE.md` 도 없다. 이 계획서·`quickstart.md`·`contracts/` 가 그 역할을 대신한다.
필요해지면 `/init` 로 생성한다.

---

## Requirement → Artifact 매핑

| FR/NFR | 어디서 충족되는가 | 검증 |
|---|---|---|
| FR-001 단일 진입점 | `ml/predict.py::predict` | SC-013 · 응답 계약 검사 |
| FR-002 방향·크기 | `coef × z` → `factors[]` | SC-003 |
| FR-003 일괄 | `predict_batch` (단건 재사용) | SC-013 단건=일괄 |
| FR-004 파이프라인 내장 전처리 | `Pipeline([Scaler, LogReg])` | AS4 · E4 |
| FR-005 기준선 병기 | `performance.json` 필수 필드 | SC-002 |
| FR-006 경고 | `warning_rules` ← schema + errors | SC-006 |
| FR-007 두 방법 교차 | `ml/explain.py` | SC-003 (5개 미만 시 학습 실패) |
| FR-008 저장·복원 검증 | `train.py` 저장 관문 | SC-004 |
| FR-009 시점 인자 | `ml/config.py` 단일 분기 | SC-009 · `--minute 15` 중단 테스트 |
| FR-010 입력 계약 | `schema.json` ← `features.py` | SC-012 |
| FR-011 성능·오류 리포트 | `ml/evaluate.py` | SC-008 |
| FR-015 README | `README.md` 6개 절 | SC-007 · SC-010 |
| FR-016 최종 노트북 | `notebooks/final_analysis.ipynb` | SC-011 클린 재실행 |
| FR-017 모델 카드 | `docs/model_card.md` 4개 절 | SC-008 · SC-014 |
| FR-018 웹 데모 | `backend/` + `frontend/` | SC-015 한 화면 |
| FR-019 파리티 | `ml/parity.py` ↔ `parity-run.js` | SC-016 1e-9 전건 |
| FR-020 경기 유형 | `ml/match_types.py` (M5) + cluster5 View | SC-017 |
| **FR-012 간편 입력** *(승격 권고)* | `ml/train.py --dataset gold2` (M2) → `model_params.simple.json` | 관문 7종 동일 통과 |
| **FR-021 정보량 통제** *(승격 권고)* | `ml/compare.py` (M3·M4) → `comparison.json` | 동일 분할 6구성 비교 |
| **FR-006 저신뢰 경고** *(확장)* | `ml/calibration.py` (M6) → `calibration.json` | 밴드별 실측 정확도 |
| **NFR-003 해석 가능성 근거** | `ml/challenger.py` (M7) → `challenger.json` + 외부 비교 | 모델 선택 근거 문서 |
| NFR-001 재현성 | seed 42 · 분할 보존 · `model.sha256` | SC-004 |
| NFR-002 누수 차단 | 닫힌 입력 계약 | 지표 목록 검사 0건 |
| NFR-006 클린 실행 | nbconvert 전량 실행 | SC-011 |
| NFR-008 모델·서비스 분리 | `model_params.json` 단일 화살표 | SC-016 |
| NFR-009 네이티브 | Docker 미사용 · `.env` | E8 |

**선택 요구사항** FR-012(간편 입력) · FR-013(실험 로그) · FR-014(임계값) · FR-021(정보량 통제)는
핵심 경로 완료 후 일정 여유가 있을 때만 착수한다.

---

## Complexity Tracking

헌장은 충족하지 못하는 항목을 침묵으로 넘기지 못하게 한다. 기록할 것이 셋 있다.

### 1. 웹 계층이 예측 산술을 이식한다 — 조건부 허용

| 항목 | 내용 |
|---|---|
| **무엇이 복잡한가** | 확률을 계산하는 코드가 Python 과 JS 두 곳에 존재한다 |
| **왜 필요한가** | FR-018 시연 요구 + A12 팀 지정. 추가 실행 계층 없이(A13) 브라우저에서 즉시 응답해야 한다 |
| **더 단순한 대안을 왜 배제했나** | ① Express → `predict.py` 자식 프로세스 호출: 경로가 하나로 유지되나 A12 지정이 아니고 요청마다 인터프리터 기동 비용이 붙는다 ② Python 예측 서버 프록시: 실행 계층이 늘어 헌장 "실행 환경" 조항에 어긋난다 |
| **어떻게 안전한가** | 화살표가 `model_params.json` 하나뿐이고, 홀드아웃 전량 1e-9 파리티가 **배포 관문**이다. 실패 시 서버가 스스로 예측을 막는다 |
| **폴백** | 파리티가 반복 실패하면 대안 ①로 전환한다 — 시연은 늦출 수 있어도 두 답이 갈라진 채 배포할 수는 없다 |

### 2. 보안 — `Intent-Plan.md` 에 DB 비밀번호 평문 커밋 ⚠️

| 항목 | 내용 |
|---|---|
| **위반** | 헌장 "보안": 접속 정보를 저장소에 평문으로 담지 않는다(MUST NOT). `Intent-Plan.md` 와 그 백업본이 비밀번호를 평문으로 담고 있었고 커밋 대상이었다 |
| **영향 범위** | 이 계획이 만드는 코드는 모두 환경 변수를 쓰므로 **구현 산출물은 위반이 아니다**. 플랫폼 템플릿에서 유래한 문서의 문제다 |
| **조치** | 별도 작업으로 분리. 저장소 공개(결과 확산 계획)가 있으므로 **외부 공개 전 필수 처리**. 값을 지우고 `.env.example` 참조로 대체 + 비밀번호 교체 |
| **왜 지금 고치지 않았나** | 팀 공용 자격 증명 교체가 필요해 다른 이용자에게 영향을 준다. 사용자 확인이 필요하다 |
| **진행 상황 (2026-09-01)** | `Intent-Plan.md` 의 평문 4곳을 `.env` 참조로 되돌려 저장소에서 제거했다. 이 문서에 인용돼 있던 값도 함께 삭제했다. **비밀번호 교체는 팀 공용 자격 증명이라 미처리** — 외부 공개 전 필수 |

### 3. 15분 비교 미실행 — 위반 아님, 이관 확정

001-Q1=B 로 후속 이관이 확정되었고 001·002 명세가 정합한다. 시점 인자 구조는 구현하므로
원리 3의 표본 통제 규칙은 FR-007 에 보존된다. **데이터 리스크와 구현 일정이 분리된 상태**다.

### 4. View DDL 16종 결손 — 재현 불가 ⚠️ (v1.1 신규)

| 항목 | 내용 |
|---|---|
| **위반** | 헌장 원리 6 "이어받을 수 있게" · NFR-006 "무오류 클린 실행". DB 에 View 28종 + 분석 테이블 `lol_analysis_10min` 이 있는데 `create-views.sql` 은 12종만 정의한다 |
| **영향** | 초기화된 환경에서 **EDA 노트북이 실행되지 않는다** — `v_diff14_all` `v_gold2_*` `v_cluster5_all` 등을 찾지 못한다. 데이터 계층부터 재현한다던 v1.0 의 주장이 현재는 성립하지 않는다 |
| **왜 생겼나** | EDA 진행 중 필요한 View 를 DB 에서 직접 만들었고, DDL 을 저장소로 되가져오지 않았다 |
| **조치** | `create-views.sql` 을 **28종 전량**으로 확장하고 `create-views.js` 검증 항목을 늘린다. **tasks 재생성 시 최우선(Phase 1) 작업**이며, 이것이 끝나기 전에는 어떤 모델도 "재현 가능"하다고 말하지 않는다 |
| **부수 정리** | `lol_analysis_10min` 의 `gameType` 열은 군집 결과를 테이블에 고정한 것이라 아티팩트와 갈라질 수 있다(D2). 학습·예측 경로에서 참조 금지로 못 박는다 |

### 5. 모델 7종 — 범위 확장의 정당성 (v1.1 신규)

| 항목 | 내용 |
|---|---|
| **무엇이 늘었나** | 서빙 모델 1 → 2 (M1·M2), 분석 모델 0 → 5 (M3~M7) |
| **왜 필요한가** | 사용자 지시(2026-09-01): EDA 노트북에서 검토한 모델을 **기능으로 구성**할 것. 현재 군집·보정·구성비교가 노트북 안에만 있어 서비스·문서가 쓸 수 없다 |
| **헌장과 충돌하는가** | 아니다. 늘어난 것은 예측 경로가 아니라 산출물이고(위 원리 7 점검), 전체 재학습이 1분 이내라 자원 제약에 영향이 없다 |
| **2시간 상한과의 관계** | 무관하다. 상한은 **성능 개선 작업**에 걸린 것이고, 이 확장은 기능 구성이다. M7 챌린저는 성능을 올리려는 것이 아니라 **올라가지 않음을 기록**하려는 것이다 |
| **일정 위험** | tasks 가 70 → 약 85~90개로 는다. 4일 예산에서 M3·M4·M7 은 **가장 먼저 잘라낼 후보**다 — 셋 다 서빙 경로 밖이라 잘라도 시연이 성립한다 |

---

## Post-Design Constitution Re-check

설계를 마친 뒤 다시 점검했다. 원리 1~7 모두 ✅ 유지되며, 설계가 원리를 **더 강하게** 만든 지점이 셋이다.

| 지점 | 설계 전 | 설계 후 |
|---|---|---|
| 원리 2 (누수 불가능) | "시점 이후 정보 배제" | 입력 계약이 **닫혀** 있어 계약 밖 키가 거부된다. 중복 제거가 차이 지표 생성의 **부산물**이 되어 별도 단계가 사라졌다 |
| 원리 5 (검증된 점수만) | "평균±표준편차로 보고" | 안정성 기준이 **학습 실패 조건**이 되어, 기준 미달 아티팩트가 생성되지 않는다 |
| 원리 6 (이어받을 수 있게) | "재현 가능한 절차" | DB View DDL 까지 저장소에 들어와, 재현 범위가 **데이터 계층부터** 시작한다 |

Gate 재판정 (v1.0): **통과.**

### v1.1 재점검 — 모델 확장 이후

| 원리 | 판정 | v1.1 에서 달라진 점 |
|---|---|---|
| 1. 기준선 우선 | ✅ 강화 | `comparison.json` 이 6개 구성을 **같은 기준선·같은 분할**로 나란히 적는다. 단일 숫자를 자랑할 자리가 사라졌다 |
| 2. 누수 불가능 | ✅ 유지 | 데이터셋이 6종으로 늘어도 전부 10분 View 에서 파생된다. 시점 이후 지표는 어느 View 에도 이름이 없다 |
| 3. 통제된 비교 | ✅ **크게 강화** | 6개 구성이 `ml_split` 하나를 공유한다. 비교 조건을 사람이 맞추는 것이 아니라 **데이터 계층이 강제**한다. 여기에 외부 비교의 인용 규칙(시점·티어·분할 병기)이 더해졌다 |
| 4. 해석 가능성 > 점수 | ✅ **근거 확보** | M7 챌린저 + 외부 연구 대조로 "로지스틱 채택이 성능 희생이 아님"이 **저장소 안에서 재현 가능한 사실**이 되었다 |
| 5. 검증된 점수만 | ⚠️ 부분 | `plan.md`·`research.md`·응답 계약 예시의 0.7394 인용을 **`ml_split` 기준 0.7136 으로 정정**했다. **`spec.md` 4곳은 미정정** — 명세 개정은 계획의 권한 밖이라 별도 작업으로 남긴다 |
| 6. 이어받을 수 있게 | ⚠️ **현재 미충족** | View DDL 16종 결손으로 노트북이 클린 환경에서 안 돈다. Complexity Tracking 4번, tasks Phase 1 최우선 |
| 7. 모델이 말하게 한다 | ✅ 유지 | 위 「v1.1 추가 점검」 표 참조. 예측 경로는 여전히 하나 |

**Gate 재판정 (v1.1): 조건부 통과.** 원리 6 위반 1건이 열려 있고, **DDL 반입 완료가 그 해소 조건**이다.
이 항목은 침묵으로 넘기지 않고 tasks 의 첫 작업으로 못 박는다(헌장 Governance).

---

## 다음 단계

```
/speckit.tasks
```

**현행 `tasks.md`(70개)는 v1.0 기준이라 M2~M7 과 DDL 반입 작업이 없다. 재생성이 필요하다.**

작업 분해 시 유의할 순서 — 헌장 Workflow 2(기능 → 모델 → 피처 → 데이터)의 역순으로 **구현**한다:

0. **`create-views.sql` 28종 전량 반입 + 컬럼명 통일(D1) — v1.1 신규 최우선.**
   원리 6 위반이 열려 있는 상태라 여기서 시작한다. 이게 끝나야 나머지 모델이 재현 가능해진다
1. `ml/features.py` · `config.py` · `registry.py` — 이름·순서·경로·모델 목록의 단일 출처. **먼저 서야 나머지가 파생된다**
2. `ml/dataset.py` — View 조회 + `ml_split` 로 고정 분할 적재 + 불변식 검사. **데이터셋 인자를 받는다**(6종 공용)
3. `ml/train.py` · `explain.py` · `evaluate.py` — 7개 관문과 아티팩트. **여기서 14피처 실측을 재산출해 evidence 갱신**
4. `ml/predict.py` — 응답 계약 구현(`model_id` 포함). 여기까지가 핵심 경로이며, 웹 없이도 완결된다
5. `ml/calibration.py` (M6) — **4번 직후.** `low_confidence` 경고가 응답 계약에 들어가므로 예측과 붙어 있어야 한다
6. `ml/match_types.py` (M5) — FR-020
7. `backend/` — `model_params.json` 산술 이식
8. `ml/parity.py` — **7번 직후 즉시.** 파리티가 늦으면 갈라진 채 프런트를 쌓게 된다
9. `frontend/` — 화면 (기본/간편 입력 탭, `model_id` 표시)
10. `ml/train.py --dataset gold2` (M2) — 서빙 2번째 모델. **파리티 대상에 추가**
11. `ml/compare.py` (M3·M4) · `ml/challenger.py` (M7) — 리포트 전용. **일정 압박 시 첫 번째 절삭 대상**
12. 노트북 · `README.md` · `model_card.md` — 산출물 마감. 모델 카드에 **외부 비교와 티어 경고**를 반드시 포함

**8번을 7번 바로 뒤에 두는 것이 이 순서의 핵심이다.** 파리티를 마지막에 돌리면
어디서 갈라졌는지 찾는 비용이 커진다. **0번을 맨 앞에 둔 것도 같은 이유다** — DDL 이 없는 채로
모델을 쌓으면, 나중에 "이 숫자가 어느 View 에서 나왔는지" 아무도 재현하지 못한다.
