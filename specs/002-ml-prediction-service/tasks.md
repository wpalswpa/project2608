# Tasks: LoL 승패 예측·설명 서비스 (시스템 구현분)


## 2026-09-01 갱신 — 실제 구현 결과 반영

이 문서는 계획 시점(2026-08-31) 작성분이며, 아래 4가지가 구현 과정에서 확정·변경되었다.

- **웹 스택** — 계획 Vue 3 / Express → **확정 Flask.** 학습·예측과 같은 Python 스택이라 웹이 `predict.py` 를 직접 import 한다. 예측 로직이 한 곳에만 존재하므로 서빙 파리티가 구조적으로 보장된다.
- **차이 지표** — 계획 14개 → **확정 13개.** `EliteMonsters = Dragons + Heralds` 선형종속을 발견해 제거했다(성능 동일: 0.7371 → 0.7369, 해석 정합성 확보).
- **시점 비교** — 계획 후속 과제 이관 → **확정 실험 B로 완료.** 프로 경기 10,656판 통제 비교, 5분 추가 시 +5.25%p이며 개선은 접전 경기에 집중된다.
- **성능** — 계획 미실측 → **확정 홀드아웃 0.7394** (찍기 기준선 0.5010 대비 +23.8%p), 시드 10회 반복 0.7366 ± 0.0081.

갱신 전 원본은 저장소 `specs/002-ml-prediction-service/_server_backup_2026-09-01/` 에 보존되어 있다.

---

**Feature**: `002-ml-prediction-service` | **Date**: 2026-09-01 | **Branch**: `main` (단일 브랜치 정책)
**Input**: [spec.md](./spec.md) v1.2 · [plan.md](./plan.md) · [research.md](./research.md) · [data-model.md](./data-model.md) · [quickstart.md](./quickstart.md) · [contracts/](./contracts/)

> ℹ️ `.specify/templates/tasks-template.md` 가 부재해(저장소에 `spec-template` · `checklist-template` 만 존재)
> 이 문서를 표준 구조(Setup → Foundational → 사용자 스토리별 → Polish)에 맞춰 직접 작성했다.

---

## 사전 확인 — 이미 서 있는 것

착수 전에 아래가 **완료 상태**임을 전제한다. 다시 만들지 않는다.

| 항목 | 상태 |
|---|---|
| DB View 12종 + `ml_split` 고정 분할 (train 7,903 / test 1,976) | ✅ 적용·검증 완료 (51 PASS) — `node scripts/create-views.js --check` |
| 계약 5종 (`schema.contract.json` · `prediction-result` · `model-params` · `web-api.openapi.yaml` · `db-views.md`) | ✅ 교차 검증 완료 |
| Python 3.9.6 `venv/` · sklearn 1.6.1 · pandas 2.3.3 · numpy 2.0.2 · PyMySQL 1.2.0 | ✅ 설치됨 |
| 모델 구성 (로지스틱 · 차이 지표 13개 · seed 42) | ✅ 확정 — **재탐색 금지**(A1 · 2시간 상한) |

---

## 테스트 포함 여부

**포함한다.** 명세가 자동 검증을 요구했고(R12 "성공 기준이 곧 테스트다"),
SC-003·004·006·012·013·016·017 은 각각 자동 검사로 옮길 수 있다.
자동화 대상이 아닌 것은 **SC-010(제3자 README 실행) 하나뿐**이며 수동 점검으로 남긴다(T062).

도구 — Python `pytest` · Node 내장 `node:test`. 별도 러너를 도입하지 않는다(NFR-005).

---

## 표기

- **[P]** — 다른 파일을 건드리므로 병렬 실행 가능
- **[USn]** — 해당 사용자 스토리 소속
- 파일 경로는 저장소 루트 기준

---

## Phase 1 — Setup (공유 기반)

- [ ] **T001** `requirements.txt` 에 `joblib==1.5.3` · `jupyter` · `nbconvert` · `pytest` 를 버전 고정으로 추가하고 `venv/bin/pip install -r requirements.txt` 로 설치한다. Python 3.9.6 을 올리지 않는다(R10 — 인터프리터를 바꾸면 A1 확정 수치의 재현 근거가 흔들린다)
- [ ] **T002** [P] `ml/__init__.py` · `tests/__init__.py` · `examples/` · `artifacts/.gitkeep` 을 만들어 패키지 뼈대를 세운다
- [ ] **T003** [P] `.gitignore` 에 `artifacts/` · `data/` · `backend/node_modules/` · `frontend/node_modules/` · `frontend/dist/` 를 추가한다. **산출물과 캐시는 커밋하지 않는다**(NFR-009)
- [ ] **T004** [P] `pytest.ini` 를 만들어 `testpaths = tests` · `pythonpath = .` 을 지정한다
- [ ] **T005** [P] `Makefile` 골격을 만든다 — `views` · `train` · `parity` · `notebook` · `all` 타깃 이름만 먼저 고정하고 내용은 각 Phase 에서 채운다

---

## Phase 2 — Foundational (모든 스토리의 선행 조건)

> ⛔ **이 Phase 가 끝나기 전에는 어떤 사용자 스토리도 시작하지 않는다.**
> 헌장 Workflow 2의 역순 구현에서 `features.py` · `config.py` 가 **먼저 서야 나머지가 파생된다**(plan 다음 단계 1).

- [ ] **T006** `ml/config.py` — `SNAPSHOT_MINUTE = 10` · `SNAPSHOT_SOURCES[minute]` · `DIFF_SPEC[minute]` · `ARTIFACT_DIR = artifacts/<minute>min/` · `SEED = 42` · `SnapshotUnavailableError` 정의. **시점 분기가 존재하는 유일한 파일**이며 다른 모듈에 `10` 리터럴을 두지 않는다(R2)
- [ ] **T007** `ml/features.py` — `FEATURE_ORDER` 13개 단일 상수(data-model ②의 순서 그대로), 지표별 `dtype`, `SIDE_NEUTRAL_FEATURES` 4개(R7). **schema·model_params·JS 계수 배열의 순서가 전부 여기서 파생된다.** 순서가 어긋나면 확률이 조용히 틀린다
- [ ] **T008** `ml/db.py` — PyMySQL 접속 헬퍼. `.env` 를 읽어 `DB_PASSWORD` 를 주입하고, **없으면 README 준비 절차를 인용한 메시지로 즉시 중단**한다(E8). 접속 정보를 코드에 적지 않는다. 기존 `scripts/_db.js` 의 규약과 동일하게 맞춘다
- [ ] **T009** `ml/dataset.py` — `v_snapshot_train` / `v_snapshot_test` 를 조회해 고정 분할을 **읽는다(다시 뽑지 않는다)**. 결과를 `data/`(gitignore) 에 CSV 캐시한다. 원천 테이블 직접 조회 금지 — View 를 통해서만 읽는다(R11)
- [ ] **T010** `ml/dataset.py` 불변식 검사 — 행수(train 7,903 / test 1,976) · `gameId` 전수 유니크 · NULL 0건 · 타깃 균형(49.90/50.10) · 피처 수 14. **하나라도 깨지면 학습을 중단**한다. 데이터가 조용히 바뀐 채 학습이 도는 것이 재현성 실패의 가장 흔한 경로다(data-model ①)
- [ ] **T011** [P] `tests/test_snapshot_axis.py` — `ml/` 하위에서 `config.py` 를 제외한 파일에 `10`·`15` 시점 리터럴이 0건인지 정적 검사한다(R2 검증)
- [ ] **T012** [P] `tests/test_feature_contract.py` — `FEATURE_ORDER` 가 `contracts/schema.contract.json` · `contracts/web-api.openapi.yaml` 의 `Snapshot` · DB `v_feature_axis` 세 곳과 **같은 순서**인지 대조한다

**체크포인트** — `venv/bin/python -c "from ml.dataset import load_split; load_split(10)"` 가 불변식 검사를 통과하며 데이터를 적재한다.

---

## Phase 3 — US1 [P1] 단건 예측·근거·경고 (MVP)

**대응 시나리오**: S1 단건 예측 · S2 근거 동시 수신 · S3 신뢰도 경고 · S5 모델 복원 재현
**대응 요구사항**: FR-001 · FR-002 · FR-004 · FR-005 · FR-006 · FR-007 · FR-008 · FR-010 · FR-011
**목표**: 스냅샷 1건 → 승리 확률 · 근거 지표 · 경고를 **한 번의 호출로** 반환한다. **웹 없이도 완결된다**(E12 · A11).

**독립 테스트 기준** — `from ml.predict import predict` 로 quickstart 3절의 예시 입력을 넣으면
응답 계약 5키가 모두 채워진 사전이 나오고, 범위 밖·접전 입력에는 경고가, 컬럼 누락에는 예외가 나온다.

### 학습 파이프라인

- [ ] **T013** [US1] `ml/train.py` — `--minute` 인자, `dataset` 적재, `Pipeline([StandardScaler, LogisticRegression])` 학습. **전처리를 파이프라인에 내장**해 예측 시 별도 전처리 호출이 필요 없게 한다(FR-004 · AS4)
- [ ] **T014** [US1] `ml/evaluate.py` — 기준선(무학습 다수 클래스) · 홀드아웃 · 5-fold `cv_mean`/`cv_std` · `train_accuracy`/`train_cv_gap` · `improvement_pp` · `auc` · `brier` 를 산출해 `artifacts/10min/performance.json` 으로 쓴다. **정확도를 단독으로 내보내는 경로를 만들지 않는다**(원리 1)
- [ ] **T015** [US1] `ml/evaluate.py` 오류 구간 집계 — 골드차 구간별 `{label, lower, upper, count, share, accuracy}` 와 `weakest_bin` 을 `artifacts/10min/errors.json` 으로 쓴다(FR-011). 이 값이 `close_game` 경고의 `segment_accuracy` 원천이다
- [ ] **T016** [US1] `ml/explain.py` — ① 표준화 계수(방향+크기) ② 순열 중요도(`n_repeats=30`, seed 고정) 를 각각 산출하고 **양쪽 상위 8개의 공통 지표만** 반환한다. 방향(+/−)은 **계수 부호에서만** 가져온다. 공통이 5개 미만이면 **학습 실패**(SC-003 · R6)
- [ ] **T017** [US1] `ml/train.py` 관문 7종 — 통과하지 못하면 **아티팩트를 만들지 않는다**. 사람이 나중에 확인하는 방식은 반드시 새어나간다

  | 관문 | 기준 | 근거 |
  |---|---|---|
  | 홀드아웃 정확도 | ≥ 0.70 | SC-001 |
  | 기준선 대비 | ≥ +20%p | SC-002 |
  | 교차검증 표준편차 | < 0.02 | SC-005 |
  | 학습–검증 격차 | < 0.03 | NFR-004 |
  | 공통 상위 요인 | ≥ 5개 | SC-003 |
  | 피처 수 | 정확히 14 | SC-012 |
  | 저장·복원 예측 일치 | 완전 일치 | SC-004 · FR-008 |

- [ ] **T018** [US1] `ml/train.py` → `artifacts/10min/schema.json` 생성 — `snapshot_minute` · `feature_order` · `features[{name,dtype,min,max,description}]` · `generated_at` · `source_rows`. `min`/`max` 는 **학습 데이터 관측 최소·최대**이며 거부 기준이 아니라 **범위 밖 경고의 유일한 근거**다
- [ ] **T019** [US1] `ml/train.py` → `artifacts/10min/model.joblib` 저장 + **복원 대조**. 저장 직후 (a) 원본 파이프라인 (b) 디스크에서 다시 읽은 파이프라인에 **가공하지 않은 원본 형태 입력**(차이 지표 13개 딕셔너리)을 넣어 확률을 비교하고, 불일치 시 **저장 파일을 지우고 실패**시킨다(FR-008 · E9 · R8)
- [ ] **T020** [US1] `ml/train.py` → `artifacts/10min/model_params.json` 내보내기 — `feature_order` · `coef[13]` · `intercept` · `mean[13]` · `scale[13]` · `cross_validated_factors[]` · `warning_rules{ranges, close_game{feature,threshold,accuracy}}` · `model{artifact,sha256,snapshot_minute,trained_at}`. **웹 계층이 읽는 유일한 파일**이며, 화면이 필요로 하는 수치 전부가 여기를 지나간다(원리 7)

### 예측 진입점

- [ ] **T021** [US1] `ml/predict.py` 입력 검증 — `schema.json` 대조로 **컬럼 누락 · 이름 불일치 · 자료형 불일치 · 계약에 없는 여분 키**를 예외로 **거부**한다(응답 사전을 반환하지 않는다). 여분 키 거부가 시점 이후 정보 유입을 구조적으로 막는다(E5 · E6)
- [ ] **T022** [US1] `ml/predict.py` 본체 — `predict(payload) -> dict` 로 `win_probability` · `predicted_class`(임계 0.5) · `factors[]` 를 만든다. `factors` 는 `contribution[i] = coef[i] × z[i]` 로 `direction=sign` · `magnitude=abs` · `rank`(크기 내림차순) · `cross_validated` 를 채우고 **공통 상위 지표만 노출**한다. SHAP 등 별도 설명기를 얹지 않는다(원리 4 · R6)
- [ ] **T023** [US1] `ml/predict.py` 경고 — `out_of_range`(schema `[min,max]` 밖: 지표명·입력값·학습 관측 범위 동봉) 와 `close_game`(`abs(goldDiff) ≤ threshold`: 구간 실측 정확도 동봉). **임계값과 정확도를 코드에 적지 않고** `model_params.warning_rules` 에서 읽는다(R5). 해당 없으면 빈 배열
- [ ] **T024** [US1] `ml/predict.py` `ModelIdentity`(artifact 경로 · `sha256` · `snapshot_minute` · `trained_at`) 부착 + 명령행 진입점 `python -m ml.predict --input examples/sample.json`
- [ ] **T025** [US1] `examples/sample.json` — quickstart 3절의 예시 스냅샷을 그대로 담는다(문서와 코드가 갈라지지 않게)

### 검증

- [ ] **T026** [P] [US1] `tests/test_response_contract.py` — 응답 5키 100% 충족(SC-013 · A9)
- [ ] **T027** [P] [US1] `tests/test_factors.py` — 근거 지표 5개 이상, 방향·크기·순위 보유, 크기 내림차순, `cross_validated=true` 만 노출(SC-003)
- [ ] **T028** [P] [US1] `tests/test_warnings.py` — 범위 밖·접전 입력에 **100% 경고 발동**하고 예측은 정상 반환. 반대로 누락·이름·자료형·여분 키는 **거부**(SC-006 · AS3 이분법)
- [ ] **T029** [P] [US1] `tests/test_schema_contract.py` — `schema.json` 컬럼 수 == 파이프라인 입력 차원 == 14, 모든 컬럼이 dtype·min·max 보유(SC-012)
- [ ] **T030** [P] [US1] `tests/test_persistence.py` — 학습 코드를 import 하지 않은 상태에서 `model.joblib` 만 복원해 **원본 형태 입력**으로 예측했을 때 저장 이전과 완전 일치(SC-004 · AS5)
- [ ] **T031** [US1] **14피처 실측 재산출** — 최초 학습 결과(홀드아웃·cv 평균±표준편차·격차·공통 상위 개수)를 `specs/001-lol-win-prediction/evidence/measured-facts.md` 에 갱신하고, **어느 분할(`ml_split`) 기준인지 함께 적는다**. 재산출값이 명세와 다르면 **문서가 실측을 따른다**(원리 5 · research 미해소 1)

**체크포인트 — MVP 완료.** `make train` → `artifacts/10min/` 에 5종(`model.joblib` · `schema.json` · `model_params.json` · `performance.json` · `errors.json`)이 생기고 `predict()` 가 동작한다. 여기서 멈춰도 예측·평가는 성립한다.

---

## Phase 4 — US2 [P2] 일괄 예측

**대응 시나리오**: S4 · **요구사항**: FR-003 · **독립 테스트**: 같은 입력에 대해 단건 결과와 일괄 결과가 완전히 일치한다.

- [ ] **T032** [US2] `ml/predict.py` 에 `predict_batch(payloads) -> list[dict]` 추가. **단건 경로를 재사용**한다(별도 벡터화 구현을 두지 않는다 — 두 경로가 갈라지면 SC-013 이 깨진다)
- [ ] **T033** [P] [US2] `examples/batch.json` 작성 + CLI `--batch` 플래그
- [ ] **T034** [P] [US2] `tests/test_batch.py` — 단건 == 일괄 전건 일치(SC-013)

**체크포인트** — `python -m ml.predict --input examples/batch.json --batch` 가 동일 계약의 결과 목록을 낸다.

---

## Phase 5 — US3 [P2] 시점 교체 가능 구조

**대응 시나리오**: S6 · **요구사항**: FR-009 · SC-009 · **독립 테스트**: `--minute 15` 가 학습 코드를 타기 전에 사유를 지목해 중단한다.

> 이번 범위의 실행 시점은 **10분 하나**다. 15분 비교는 후속 과제로 이관 확정(A4 · 001-Q1=B).
> 여기서 만드는 것은 **비교가 아니라 구조**다.

- [ ] **T035** [US3] `ml/config.py` 의 시점 분기를 완결한다 — `SNAPSHOT_SOURCES` 미등록 시점 요청 시 `SnapshotUnavailableError`, 산출물 경로를 `artifacts/<minute>min/` 으로 분리해 두 시점 결과가 같은 저장소에 공존할 수 있게 한다
- [ ] **T036** [US3] `train.py` · `parity.py` 가 `--minute` 을 받아 그대로 전달하고, **데이터 소스 조회 단계에서** 미확보를 판정해 중단하도록 배치한다(전처리·학습 코드 진입 전 — AS8)
- [ ] **T037** [P] [US3] `tests/test_minute_switch.py` — `--minute 15` 실행이 `SnapshotUnavailableError` 로 끝나고 예측 로직 파일이 수정 없이 그대로임을 확인(SC-009)
- [ ] **T038** [P] [US3] `scripts/create-views.sql` 의 `v_snapshot_features` UNION ALL 블록에 **"15분 확보 시 여기 한 곳만 고친다"** 주석을 명시한다. FR-009 의 확장성이 Python 이 아니라 SQL 구조 수준에서 성립함을 코드가 말하게 한다

**체크포인트** — 시점 축이 `config.py` 한 곳 + SQL 한 블록으로 닫힌다.

---

## Phase 6 — US4 [P2] 경기 유형 프로파일

**대응 시나리오**: S12 · **요구사항**: FR-020 · SC-017 · AS14 · **독립 테스트**: `match_types.json` 에 2개 이상 유형이 있고 각 유형에 경기 수와 10분 리드팀 최종 승률이 모두 있다.

- [ ] **T039** [US4] `ml/match_types.py` — `v_lol_10min_neutral` 조회 후 `SIDE_NEUTRAL_FEATURES` 4개(`absGoldDiff` · `absExperienceDiff` · `totalKills` · `totalObjectives`)로 KMeans. `k ∈ {2,3,4}` 를 실루엣 계수로 선택하고 seed 고정(R7)
- [ ] **T040** [US4] 유형별 `{id, count, lead_team_win_rate, centroid, label}` 과 `neutral_features[]` · `k` · `silhouette` 를 `artifacts/10min/match_types.json` 으로 쓴다. `lead_team_win_rate` 는 `sign(goldDiff)` 가 최종 승자와 일치한 비율이다
- [ ] **T041** [P] [US4] `tests/test_match_types.py` — ① 블루/레드를 통째로 뒤집은 데이터로 재분류했을 때 **같은 배정**이 나오는지(진영 불변성) ② `len(types) ≥ 2`, 모든 유형이 `count`·`lead_team_win_rate` 보유, `neutral_features` 에 `blue`/`red` 접두 컬럼 0건(SC-017 · AS14). **눈으로 확인하지 않고 불변성 테스트로 강제**한다

**체크포인트** — A14 가 요구한 근거가 **저장소 안에서 재산출**된다(외부 세션 산출물 반입 대기 불필요).

---

## Phase 7 — US5 [P2] 서빙 파리티 (배포 관문)

> **9/1 갱신 — 이 Phase 는 Flask 로 대체 구현됨.** 아래 Vue/Express 전제 작업(T042~T053)은 실행하지 않았다.
> 실제로 한 일: `web/app.py`(Flask, `predict.py` 를 직접 import) · `web/templates/index.html`(입력 폼·승률 막대·요인 표시)
> · `web/test_parity.py`(서빙 파리티 자동 검증 — 데모 3건 소수점까지 일치).
> 예측 로직이 한 프로세스에 하나뿐이라 **JS 사본·파라미터 재현이 아예 필요 없어졌다.**

**대응 시나리오**: S11 · **요구사항**: FR-019 · NFR-008 · SC-016 · E10 · E11
**독립 테스트**: `python -m ml.parity --minute 10` 이 `passed: true` 를 내고, 1건이라도 어긋나면 종료 코드 1 이다. **서버를 띄우지 않아도 돌아간다.**

> ⚠️ **이 Phase 를 US6(화면)보다 먼저 끝낸다.** 파리티를 마지막에 돌리면 어디서 갈라졌는지
> 찾는 비용이 커지고, 그 사이에 갈라진 채로 프런트를 쌓게 된다(plan 다음 단계 7).

- [x] **T042** [US5] ~~backend/package.json~~ → **9/1 Flask 로 대체.** `web/app.py` 가 `predict.py` 를 직접 import 하므로 별도 Node 계층 없음. `requirements.txt` 에 Flask 고정
- [ ] **T043** [US5] `backend/src/predictor.js` — `model_params.json` 만 읽어 `z = (x−mean)/scale` → `logit = intercept + Σ coef·z` → `sigmoid` 산술을 옮긴다. **수치 리터럴 0건 · 조건문 기반 판단 0건 · 확률 보정 0건.** `factors`·`warnings` 도 같은 파일의 `cross_validated_factors`·`warning_rules` 로 산출한다(A12 · NFR-008). 연산 순서를 `feature_order` 로 고정한다(R4 부동소수)
- [ ] **T044** [US5] `backend/src/parity-run.js` — 입력 벡터를 받아 확률 배열을 출력하는 CLI. **Express 라우트가 쓰는 바로 그 `predictor.js` 를 호출**한다(별도 사본 금지)
- [ ] **T045** [US5] `ml/parity.py` — 홀드아웃 전량(1,976행)을 `predict.py` 로 통과시킨 뒤 같은 입력을 `node backend/src/parity-run.js` 에 넘겨 대조한다. `max_abs_diff ≤ 1e-9` 전건 확인, **1건이라도 벗어나면 종료 코드 1**
- [ ] **T046** [US5] `artifacts/10min/parity_report.json` 저장 — `compared` · `max_abs_diff` · `tolerance` · `passed` · `verified_at` · `model_sha256`
- [ ] **T047** [P] [US5] `tests/test_parity.py` — ① SC-016 전건 일치 ② `backend/src/predictor.js` 정적 검사: 숫자 리터럴(0·1·0.5 등 산술 항등원 제외)이 0건인지. **표시 계층이 자체 상수를 갖는 순간 원리 7 위반**이므로 사람 눈 대신 테스트가 지킨다

**체크포인트 — 배포 관문 통과.** 파리티가 반복 실패하면 **폴백은 튜닝이 아니라 구조 전환**이다(plan Complexity Tracking 1: Express → `predict.py` 자식 프로세스 호출). 시연은 늦출 수 있어도 두 답이 갈라진 채 배포할 수는 없다.

---

## Phase 8 — US6 [P2] 브라우저 시연 화면

> **9/1 갱신 — 이 Phase 는 Flask 로 대체 구현됨.** 아래 Vue/Express 전제 작업(T042~T053)은 실행하지 않았다.
> 실제로 한 일: `web/app.py`(Flask, `predict.py` 를 직접 import) · `web/templates/index.html`(입력 폼·승률 막대·요인 표시)
> · `web/test_parity.py`(서빙 파리티 자동 검증 — 데모 3건 소수점까지 일치).
> 예측 로직이 한 프로세스에 하나뿐이라 **JS 사본·파라미터 재현이 아예 필요 없어졌다.**

**대응 시나리오**: S10 · **요구사항**: FR-018 · SC-015 · AS12
**독립 테스트**: 브라우저에서 예시 경기를 고르거나 지표를 입력하면 **승률·근거·경고가 한 화면에** 뜨고, 근거 목록이 `predict.py` 반환값과 동일한 목록·순서다.

- [ ] **T048** [US6] `backend/src/routes.js` — [`web-api.openapi.yaml`](./contracts/web-api.openapi.yaml) 의 7개 경로 구현: `/api/health` · `/api/schema` · `/api/examples` · `/api/predict` · `/api/predict/batch` · `/api/match-types` · `/api/report`. `/api/report` 는 **성능과 기준선을 항상 함께** 반환한다(원리 1 — 정확도 단독 경로를 두지 않는다)
- [ ] **T049** [US6] `backend/src/server.js` — 기동 시 `parity_report.json` 의 `passed` 를 확인하고 **없거나 실패면 `/api/predict` 를 503 으로 막는다**. 검증되지 않은 확률이 화면에 뜨지 않게 하는 장치다(A12)
- [ ] **T050** [P] [US6] `backend/test/routes.test.js` (`node:test`) — 응답이 OpenAPI 계약을 준수하는지, `parity_report.json` 을 치웠을 때 실제로 503 이 나오는지
- [ ] **T051** [US6] `frontend/` 스캐폴딩 — Vite 5 + Vue 3.4 + Pinia 2 + TypeScript 5. `npm --prefix frontend install`
- [ ] **T052** [US6] 입력 화면 — **폼을 `/api/schema` 로 동적 생성**한다(지표 목록을 프런트에 손으로 적지 않는다). `/api/examples` 로 예시 경기 선택 제공
- [ ] **T053** [US6] 결과 화면 — 승리 확률 · 근거 지표(방향과 크기) · 경고를 **한 화면에** 표시한다. 반올림·백분율 변환은 **렌더링에서만** 하고 판단에 쓰이는 값은 변형하지 않는다(E11 · NFR-008)
- [ ] **T054** [P] [US6] 서버 기동 상태에서 **HTTP 표본 대조 20건** — 라우트의 직렬화·파싱이 값을 바꾸지 않음을 확인한다. 전건을 HTTP 로 돌리지 않는 이유는 CI 없이 로컬에서 반복 실행할 절차이기 때문이다(R4 · NFR-005)

**체크포인트** — `npm --prefix backend run dev` + `npm --prefix frontend run dev` 로 시연이 성립한다. **서버가 내려가도 예측·평가·산출물은 모두 성립한다**(E12).

---

## Phase 9 — US7 [P3] 최종 노트북 클린 재실행

**대응 시나리오**: S8 · **요구사항**: FR-016 · NFR-006 · SC-011 · AS10
**독립 테스트**: 초기화된 커널에서 전량 재실행 시 **오류 0건 완주** + 노트북 수치와 `artifacts/` 리포트 값 일치.

- [ ] **T055** [US7] `notebooks/final_analysis.ipynb` — **얇게 만든다.** 분석 로직은 `ml/` 모듈에 두고 노트북은 호출·표·그림만 담는다. 로직이 노트북 안에만 있으면 `predict.py` 와 갈라진다(원리 7의 실패 경로)
- [ ] **T056** [US7] 클린 실행을 깨는 4가지를 구조로 막는다(R9) — ① 각 셀은 앞 셀의 **파일 산출물**만 참조(전역 변수 가로지르기 금지) ② 첫 셀에서 `artifacts/10min/` 을 비우고 시작 ③ 절대 경로 금지(노트북 위치 기준 상대 경로) ④ 첫 셀이 `DB_PASSWORD` 등 필수 환경 변수를 검사하고 없으면 **README 준비 절차를 인용한 메시지**로 중단
- [ ] **T057** [US7] 표·그림 — 성능(기준선 병기) · 요인 순위 · 격차 구간별 정확도 · 경기 유형 프로파일. **셀 순서가 quickstart 절 순서와 같아야 한다**(A8: README·노트북·quickstart 셋이 어긋나면 재현이 깨진다)
- [ ] **T058** [P] [US7] `make notebook` — `venv/bin/jupyter nbconvert --to notebook --execute --inplace notebooks/final_analysis.ipynb` 실행 후 종료 코드 0 + 수치 대조(SC-011)

**체크포인트** — 채점자·검토자가 저장소만 받아 재실행할 수 있다.

---

## Phase 10 — US8 [P3] 모델 카드 단독 판단

**대응 시나리오**: S9 · **요구사항**: FR-017 · SC-008 · SC-014 · AS11
**독립 테스트**: 제3자가 `model_card.md` 만 읽고 자기 사례에 써도 되는지 결정할 수 있다.

- [ ] **T059** [US8] `docs/model_card.md` 4개 절(A10) — **용도** · **성능**(기준선 대비 개선 폭 · 홀드아웃 · cv 평균±표준편차 · 학습–검증 격차를 함께) · **사용 금지 상황**(최소 4가지: 베팅·도박, 학습 범위 밖 입력, 실력 수준·리그 교차 적용, 게임 버전 상이) · **한계**(정확도 상한 0.73~0.74, 접전 구간 34.4%에서 0.61, 단일 시점·단일 실력 구간 한정). **목록 나열이 아니라 판단 근거가 드러나는 문장**으로 쓴다
- [ ] **T060** [US8] **한계 절을 성능 절과 분리해 별도로 쓴다.** 성능 수치만 읽고 접전 구간의 취약성을 놓치는 것이 이 모델의 가장 현실적인 오용 경로다(A10). 수치는 T031 의 재산출값을 인용하고 **어느 분할 기준인지 함께 적는다**
- [ ] **T061** [P] [US8] `tests/test_model_card.py` — 4개 절 존재, 금지 상황 4건 이상, 한계 절이 성능 절과 분리(SC-008 · SC-014)

---

## Phase 11 — US9 [P3] README 단독 인수인계 (최종 산출물)

**대응 시나리오**: S7 · **요구사항**: FR-015 · SC-007 · SC-010 · AS9
**독립 테스트**: 프로젝트를 처음 접한 사람이 `README.md` 만 읽고 추가 질문 없이 학습·예측을 완주한다.

- [ ] **T062** [US9] `README.md` 6개 절(A8) — ① 문제 정의 ② 실행 방법(사전 준비·학습·예측·**웹 데모**) ③ 구조(원본 → 전처리 → 학습 → 예측 → 화면) ④ 결과(정확도·개선 폭·승리요인·오류 집중 구간·경기 유형) ⑤ 한계와 사용 금지 상황 ⑥ 재현 절차(**파리티 검증 실행법 포함**). **"실행 방법"은 quickstart·노트북 셀 순서와 동일해야 한다**
- [ ] **T063** [US9] 산출물 9종 링크 연결 + `make check` 존재 점검 — README · 최종 노트북 · `model.joblib`(전처리 포함) · `schema.json` · `predict.py` · 성능/오류 리포트 · `model_card.md` · 웹 데모 · 파리티 검증 결과(SC-007)
- [ ] **T064** [US9] **SC-010 수동 점검** — 팀 내 1인이 초기화된 환경에서 README 만 보고 예측 실행까지 도달하는지 확인한다. **자동화 대상이 아니다**(research 미해소 2). 막힌 지점이 나오면 그 문장을 고친다

---

## Phase 12 — Polish & 선택 요구사항

- [ ] **T065** `Makefile` 완성 — `all: views train parity notebook check`. quickstart 7절의 "전체를 한 번에"가 실제로 동작해야 한다
- [ ] **T066** [P] **FR-012 간편 입력 모드**(선택) — `v_lol_10min_simple2` 기반. 핵심 지표 2개로 홀드아웃 0.73 수준이 나오므로 구현은 가볍다(A7)
- [ ] **T067** [P] **FR-013 실험 로그**(선택) — 표 형태 이력
- [ ] **T068** [P] **FR-014 임계값 탐색**(선택) — 0.3~0.7 구간을 훑어 **조정 불필요를 근거로 남긴다**(조정하는 것이 목적이 아니다)
- [ ] **T069** [P] **FR-021 정보량 통제 실험**(선택) — 특정 시각에 존재할 수 없는 지표를 제외하고 성능 측정. 시점 비교 이관으로 생긴 공백을 메운다
- [ ] **T070** ⚠️ **보안 — 팀 공용 DB 비밀번호 교체.** 저장소의 평문은 제거했으나(2026-09-01) 자격 증명 자체는 그대로다. **GitHub 공개 전 필수**이며 다른 이용자에게 영향을 주므로 **팀 합의 후 수행**한다(plan Complexity Tracking 2)

---

## 의존 관계

```
Phase 1 Setup
    │
Phase 2 Foundational  ← 여기까지는 순차. config/features 가 서야 나머지가 파생된다
    │
    ├─▶ Phase 3  US1 [P1] 단건 예측·근거·경고 ★ MVP — 여기서 멈춰도 성립
    │       │
    │       ├─▶ Phase 4  US2 일괄 예측        (predict.py 재사용)
    │       ├─▶ Phase 5  US3 시점 교체 구조   (config 확장)
    │       ├─▶ Phase 6  US4 경기 유형        (dataset 재사용, US1 과 독립 실행 가능)
    │       │
    │       └─▶ Phase 7  US5 파리티 ⛔ 배포 관문
    │                 │        (model_params.json 필요 → T020)
    │                 └─▶ Phase 8  US6 화면   (parity 통과 후에만 의미 있음)
    │                                          /api/match-types 는 Phase 6 산출물 필요
    │
    ├─▶ Phase 9  US7 노트북      (US1·US4 산출물 필요)
    ├─▶ Phase 10 US8 모델 카드   (US1 성능·오류 리포트 필요)
    └─▶ Phase 11 US9 README      (전 산출물 링크 — 마지막)
            │
        Phase 12 Polish & 선택
```

**스토리 간 독립성** — US2·US3·US4 는 서로 의존하지 않으며 US1 완료 후 **병렬 착수 가능**하다.
US5 → US6 만 순서가 강제된다(파리티가 화면의 선행 관문).

---

## 병렬 실행 기회

| 구간 | 동시 실행 가능 |
|---|---|
| Phase 1 | T002 · T003 · T004 · T005 (T001 이후) |
| Phase 2 | T011 · T012 (T006·T007 이후) |
| Phase 3 검증 | T026 · T027 · T028 · T029 · T030 (T024 이후) |
| Phase 4~6 | **US2 · US3 · US4 를 3인이 동시 진행** (Phase 3 완료 후) |
| Phase 8 | T050 · T054 (라우트 구현 이후) |
| Phase 12 | T066 · T067 · T068 · T069 |

4인 팀 기준 권장 배치 — Phase 3 완료 후 **① US2+US3 ② US4 ③ US5→US6 ④ US7~US9** 로 나눈다.

---

## 구현 전략

### MVP = Phase 1 → 2 → 3 (US1 하나)

`predict()` 가 승률·근거·경고를 반환하는 지점이 **프로젝트가 성립하는 최소 단위**다.
웹 계층이 없어도 예측·평가·산출물은 모두 성립하므로(E12 · A11), 여기까지가 핵심 경로다.

### 일정이 압박되면 무엇을 줄이는가

**웹 계층(US5·US6)만 축소한다.** ML 산출물은 영향받지 않는다(A11).
그 경우 US7~US9(노트북·모델 카드·README)를 먼저 마감한다 — 산출물 9종(SC-007)과
인수인계(A8)가 프로젝트의 완료 정의이기 때문이다. **P3 은 "선택"이 아니라 "순서상 나중"이다.**
진짜 선택 항목은 Phase 12 의 FR-012·013·014·021 넷뿐이다.

### 하지 말 것

| 금지 | 근거 |
|---|---|
| 하이퍼파라미터 탐색·앙상블로 성능 올리기 | 실측 상한 0.73~0.74(A2). **개선 작업 2시간 상한**, 도달 시 즉시 중단 |
| 학습이 관문에서 실패했을 때 튜닝부터 시도 | 데이터·전처리를 **되짚는다**. 튜닝 먼저는 금지(quickstart 문제 해결표) |
| 웹 계층에 임계값·계수·구간 손으로 적기 | NFR-008 · 원리 7. T047 정적 검사가 잡는다 |
| 새 브랜치 생성 | 단일 브랜치 정책 — `main` 하나만 유지 |
| 15분 비교 실행 | 후속 과제로 이관 확정(A4). **구조만 만든다** |

### 완료 정의

Phase 11 종료 시 아래가 모두 참이어야 한다.

- `artifacts/10min/` 에 7종(`model.joblib` · `schema.json` · `model_params.json` · `performance.json` · `errors.json` · `match_types.json` · `parity_report.json`)
- `parity_report.json` 의 `passed == true`
- `pytest` · `node --test` 전건 통과
- `make all` 이 오류 0건으로 완주
- README 만 읽은 제3자가 예측 실행까지 도달(T064 수동 확인)

---

## 요약

| 구분 | 수 |
|---|---|
| **전체 작업** | **70** (T001~T070) |
| Setup | 5 (T001~T005) |
| Foundational | 7 (T006~T012) |
| US1 [P1] 단건 예측·근거·경고 | 19 (T013~T031) |
| US2 [P2] 일괄 예측 | 3 (T032~T034) |
| US3 [P2] 시점 교체 구조 | 4 (T035~T038) |
| US4 [P2] 경기 유형 프로파일 | 3 (T039~T041) |
| US5 [P2] 서빙 파리티 | 6 (T042~T047) |
| US6 [P2] 브라우저 시연 화면 | 7 (T048~T054) |
| US7 [P3] 최종 노트북 | 4 (T055~T058) |
| US8 [P3] 모델 카드 | 3 (T059~T061) |
| US9 [P3] README | 3 (T062~T064) |
| Polish & 선택 | 6 (T065~T070) |
| **병렬 표시 [P]** | 25 |
| **테스트 작업** | 14 (T011·T012·T026~T030·T034·T037·T041·T047·T050·T054·T061) |

**다음 단계**

```
/speckit.implement          # Phase 1 부터 순차 실행
/speckit.analyze            # (선택) spec·plan·tasks 교차 정합 점검
```


---

## 최종 결과 (2026-09-01 실측)

### 성능 — 봉인 시험지 1,976판

| 지표 | 값 |
|---|---|
| **홀드아웃 정확도** | **0.7394** — 찍기 기준선 0.5010 대비 **+23.8%p** |
| 교차검증 (5-fold) | 0.7315 ± 0.0153 · 학습−검증 격차 +0.0022 |
| **시드 10회 반복** | **0.7366 ± 0.0081** (0.7277~0.7520) · 10/10회 하한 0.70 통과 |
| F1 / AUC / Brier | 0.7352 / 0.8150 / 0.1756 |
| 혼동행렬 | TN 746 · FP 244 / FN 271 · TP 715 — 양방향 오류 대칭 |

> 단일 분할 값 0.7394 는 반복 분포(0.7366 ± 0.0081) 안의 한 표본이다. 두 값을 함께 보고한다.

### 승리요인 — 계수·permutation 두 방법 순위 완전 일치

| 순위 | 요인 | 표준화 계수 | permutation |
|---|---|---|---|
| 1 | 골드 차이 | +1.231 | 0.185 |
| 2 | 경험치 차이 | +0.461 | 0.032 |
| 3 | 드래곤 차이 | +0.267 | 0.011 |

4위 이하는 permutation 중요도가 0 근처(≤0.0001)라 순위가 무의미하다.
킬 차이는 단독 효과크기 1.09(3위)의 강한 신호지만, 킬로 번 돈이 이미 `GoldDiff` 에
포함되어(상관 +0.92) 골드를 통제하면 계수가 음수(−0.11)가 된다 —
**"킬은 골드로 환산됐을 때만 의미가 있다"** 가 정확한 해석이며, 화면에는 계수 대신 효과크기를 쓴다.

### 오류 프로파일 — 정확도는 골드차의 함수

| 10분 골드차 | 비중 | 정확도 |
|---|---|---|
| 접전 (<1,000) | 34.4% | **0.615** |
| 우세 (1,000~2,500) | 36.5% | 0.741 |
| 크게 우세 (2,500~4,200) | 20.4% | 0.859 |
| 사실상 결정 (4,200+) | 8.7% | **0.947** |

접전 구간은 모델의 한계가 아니라 **10분 정보 자체가 승패를 못 가르는** 데이터의 한계다.

### 실험 B — 시점 비교 (프로 경기 10,656판, 통제 완료)

같은 경기·같은 피처 5개·같은 분할에서 시점만 10분 → 15분으로 바꿨다.

**시점별 성능**

| 입력 시점 | 홀드아웃 | AUC |
|---|---|---|
| 10분 | 0.7036 | 0.7729 |
| **15분** | **0.7561** | **0.8344** |
| 찍기 기준선 | 0.5230 | — |

**10분 상황별 5분 추가 효과** — 개선이 접전에만 몰린다

| 10분 상황 | 비중 | 10분 정보 | 15분 정보 | 개선 |
|---|---|---|---|---|
| 접전 (<1,000) | 52.1% | 0.617 | 0.696 | **+7.8%p** |
| 우세 (1,000~2,500) | 37.5% | 0.761 | 0.793 | +3.1%p |
| 크게 우세 (2,500+) | 10.4% | 0.928 | 0.928 | **±0.0%p** |

**이미 크게 벌어진 경기는 5분을 더 봐도 얻을 것이 없고(개선 0.0), 접전만 개선된다.**
10분 접전 경기의 59.3% 가 15분까지 골드차 1,000 이상으로 벌어진다.
시드 10회 반복에서도 10/10회 15분이 우세했다(+4.77 ± 0.89%p).

### 산출물 검증

| 산출물 | 검증 |
|---|---|
| `artifacts/model.joblib` | 전처리 포함 Pipeline · 저장→복원→예측 일치 assert 통과 |
| `artifacts/schema.json` | 13피처 타입 · 학습 범위 min/max · 성능 메타 |
| `predict.py` | `predict(payload)→dict` · 스모크 3건 (51.2% / 94.6% / 16.8%) |
| `model_card.md` | 용도 · 성능 · 사용 금지 상황 6가지 · 한계 |
| `notebooks/final_analysis.ipynb` | 클린 런타임 무오류 실행 |
| 웹 데모 (Flask) | 서빙 파리티 3건 소수점까지 일치 (`web/test_parity.py`) |
| 문서 정합성 | `src/factcheck.py` 자동 점검 0건 |

### 남은 한계

- 접전(골드차 <1,000, 홀드아웃의 34%)은 10분 정보로 예측 불가 — 실험 B가 그 이유를 보였다
- 수집 시점 패치 한정 · 실험 B 결론은 프로 경기 한정
- 실험 B에 팀 단위 그룹 분할(GroupKFold) 미적용 — 절대 수치는 낙관적일 수 있으나 두 시점 간 차이 비교는 유효
- 경기 유형 군집 k=4 는 실루엣이 아니라 해석 편의로 고른 값 (설명을 위한 구획)
- 정성 스모크 테스트(SC-007 계열)와 팀 서버 배포는 미실행
