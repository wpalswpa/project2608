# Phase 1 — Data Model: ML 승패예측·설명 서비스


> ### 2026-09-01 갱신 — 실제 구현 결과 반영
> 이 문서는 계획 시점(8/31) 작성분이며, 아래 4가지가 구현 과정에서 확정·변경되었다.
>
> | 항목 | 계획(8/31) | **확정(9/1)** |
> |---|---|---|
> | 웹 스택 | Vue 3 / Express | **Flask** — 학습·예측과 같은 Python 스택이라 `predict.py` 를 직접 import, 서빙 파리티가 구조적으로 보장됨 |
> | 차이 지표 | 14개 | **13개** — `EliteMonsters = Dragons + Heralds` 선형종속을 발견해 제거(성능 동일 0.7371→0.7369, 해석 정합) |
> | 시점 비교 | 후속 과제 이관 | **실험 B로 완료** — 프로 경기 10,656판 통제 비교, 5분 추가 시 +5.25%p(개선은 접전에 집중) |
> | 성능 | 미실측 | **홀드아웃 0.7394**(찍기 0.5010 대비 +23.8%p) · 시드 10회 반복 0.7366 ± 0.0081 |
>
> 갱신 전 원본은 저장소 `specs/002-ml-prediction-service/_server_backup_2026-09-01/` 에 보존되어 있다.

**Feature**: `002-ml-prediction-service` | **Date**: 2026-08-31
**출처**: [spec.md](./spec.md) `Key Entities` · [research.md](./research.md)

이 프로젝트에는 **영속 저장이 없다**(Out of Scope: "사용자 계정·권한 관리, 데이터 영속 저장").
따라서 여기서 말하는 데이터 모델은 DB 테이블이 아니라 **① 읽기 전용 원천 · ② 파일 산출물 ·
③ 메모리 상 자료구조** 세 층의 계약이다.

```
[① 원천]        [② 산출물]                                   [③ 런타임]
View 12종       artifacts/10min/                              predict(payload)
(diff13 등)──▶    model.joblib      전처리+추정기 파이프라인   ──▶  PredictionResult
 (읽기전용)       schema.json       입력 계약 13개
                  model_params.json 웹 계층 재현용 수치        ──▶  웹 화면
                  performance.json  성능 리포트
                  errors.json       오류 리포트
                  match_types.json  경기 유형 프로파일
                  parity_report.json 파리티 검증 결과
```

---

## ① 원천 — `lol_matches_10min` + View 12종 (읽기 전용)

**학습은 원천 테이블을 직접 읽지 않는다. View 를 통해서만 읽는다** —
차이 지표 정의를 SQL 한 곳에 못박아 Python·Node·노트북이 같은 정의를 쓰게 하기 위해서다.

| View | 컬럼 | 쓰임 | 상태 |
|---|---|---|---|
| `v_lol_10min_diff13` | 16 | 학습·예측 기본 입력 | ✅ 적용·검증 완료 |
| `v_lol_10min_clean29` | 31 | 대조군 (원리 3) | ✅ |
| `v_lol_10min_simple2` | 4 | 간편 입력 (FR-012) | ✅ |
| `v_lol_10min_neutral` | 15 | 경기 유형 (FR-020) | ✅ |

그 위에 **시점 축**과 **요인 분석** 두 층이 얹혀 있다 ([contracts/db-views.md](./contracts/db-views.md)):

| View | 컬럼 | 쓰임 | 상태 |
|---|---|---|---|
| `v_feature_axis` | 2 | 피처 순서 계약을 DB 에 명시 | ✅ |
| `v_snapshot_features` | 18 | **시점별 학습·예측 입력** (`snapshotMinute` + split + 타깃 + 피처 13) | ✅ |
| `v_snapshot_train` / `_test` | 18 | 고정 분할(`ml_split`) | ✅ |
| `v_snapshot_feature_long` | 7 | 언피벗 — 요인 집계 원자료 | ✅ |
| `v_win_factor_stats` | 12 | 시점 × scope × 지표 집계 | ✅ |
| `v_win_factors` | 16 | **핵심 승리요인 순위** (FR-002·FR-007) | ✅ |
| `v_win_factor_bins` | 7 | 골드 격차 구간별 승률 (FR-011 · close_game 근거) | ✅ |

15분 확보 시 고치는 곳은 `v_snapshot_features` 의 UNION ALL 한 곳뿐이며, 아래 층은 자동 확장된다(FR-009).

DDL: [`scripts/create-views.sql`](../../scripts/create-views.sql) · 검증: `node scripts/create-views.js` (51 PASS)

### 원천 테이블

9,879행 × 40컬럼, 적재 2026-08-28. **이 프로젝트는 이 테이블에 쓰지 않는다.**

| 구분 | 컬럼 | 비고 |
|---|---|---|
| 식별자 | `gameId` | 전수 유니크(중복 0건) |
| 정답 | `blueWins` | 1=블루 승 / 0=블루 패. 균형 49.90 / 50.10 |
| 지표 | 나머지 38개 (blue 19 · red 19) | 결측 0건 |

**불변식** — 결측 0 · `gameId` 중복 0 · 39피처 완전중복 행 0 (measured-facts §2).
`dataset.py` 는 적재 직후 이 셋을 재확인하고, 깨지면 **학습을 중단**한다.
데이터가 조용히 바뀐 채 학습이 도는 것이 재현성(NFR-001)의 가장 흔한 실패 경로다.

---

## ② 파생 — 경기 스냅샷 (`MatchSnapshot`)

원천 1행 → 차이 지표 13개 + 정답 1개. **예측의 기본 단위이자 `schema.json` 이 계약하는 형태**다.

| 필드 | 자료형 | 허용범위 | 설명 |
|---|---|---|---|
| `wardsPlacedDiff` | int | 학습 관측 [min, max] | 와드 설치 차 |
| `wardsDestroyedDiff` | int | 〃 | 와드 파괴 차 |
| `firstBloodDiff` | int | `-1 … 1` | 선취점 차 |
| `killsDiff` | int | 학습 관측 | 처치 차 |
| `assistsDiff` | int | 〃 | 어시스트 차 |
| `eliteMonstersDiff` | int | 〃 | 대형 몬스터 차 |
| `dragonsDiff` | int | 〃 | 드래곤 차 |
| `heraldsDiff` | int | 〃 | 전령 차 |
| `towersDestroyedDiff` | int | 〃 | 타워 파괴 차 |
| `goldDiff` | int | 〃 | **골드 차 — 최상위 요인** |
| `avgLevelDiff` | float | 〃 | 평균 레벨 차 |
| `experienceDiff` | int | 〃 | 경험치 차 |
| `totalMinionsKilledDiff` | int | 〃 | CS 차 |
| `totalJungleMinionsKilledDiff` | int | 〃 | 정글 CS 차 |

**순서가 계약의 일부다.** 위 13개의 나열 순서가 `schema.json` · 파이프라인 학습 · JS 산술의
계수 배열 순서와 **모두 같아야 한다**. 순서가 어긋나면 확률이 조용히 틀린다 — 파리티 검증이
잡아내지만, 애초에 `ml/features.py` 의 단일 상수에서 모든 순서가 파생되게 한다.

**정답** — `blueWins` (0/1). 스냅샷에는 예측 입력으로 포함되지 않는다(원리 2).

**시점 의존성** — 이 13개는 `SNAPSHOT_MINUTE = 10` 의 정의다. 15분 확보 시
`DIFF_SPEC[15]` 가 별도로 정의되며, 두 정의가 섞이지 않도록 산출물 디렉터리가 분리된다.

---

## ③ 입력 명세 — `schema.json` (FR-010 · SC-012)

| 필드 | 내용 |
|---|---|
| `snapshot_minute` | 10 |
| `feature_order` | 13개 컬럼명 배열 — **순서가 곧 계약** |
| `features[]` | `{ name, dtype, min, max, description }` |
| `generated_at` · `source_rows` | 생성 일시 · 학습 표본 수 |

**불변식** — `len(features) == 13 == 학습 파이프라인의 입력 차원`. 이 등식이 SC-012이며,
학습 종료 시 assert 로 검사한다. `min`/`max` 는 **학습 데이터 관측 최소·최대**이고,
거부 기준이 아니라 **범위 밖 경고(FR-006)의 유일한 근거**다.

**판정 규칙**

| 상황 | 처리 |
|---|---|
| 컬럼 누락 / 이름 불일치 / 자료형 불일치 | **거부** — 예외, 응답 사전 반환 안 함 |
| 값이 `[min, max]` 밖 | **경고** — 예측은 정상 반환 |
| 계약에 없는 키가 추가로 들어옴 | **거부** — 시점 이후 정보 유입 차단(E5) |

---

## ④ 응답 계약 — `PredictionResult` (A9 · SC-013)

```
{
  "win_probability": 0.0 ~ 1.0,          # 블루 팀 승리 확률
  "predicted_class": "win" | "loss",     # 임계값 0.5
  "factors": [ Factor, ... ],            # 5개 이상, 크기 내림차순
  "warnings": [ Warning, ... ],          # 없으면 빈 배열
  "model": ModelIdentity
}
```

**`Factor`** — 근거 지표 (FR-002 · FR-007)

| 필드 | 자료형 | 설명 |
|---|---|---|
| `name` | str | 지표명 (`feature_order` 의 원소) |
| `direction` | `"+"` \| `"−"` | 이 경기에서 승리에 유리/불리. `sign(coef × z)` |
| `magnitude` | float | `abs(coef × z)` — 로그오즈 기여의 절대 크기 |
| `rank` | int | 1부터. 크기 내림차순 |
| `cross_validated` | bool | 두 해석 방법 공통 상위 여부 — **true 인 것만 노출** |

**`Warning`** — 신뢰도 고지 (FR-006)

| 필드 | 설명 |
|---|---|
| `type` | `out_of_range` \| `close_game` |
| `reason` | 사람이 읽는 사유 (범위 밖 지표명·입력값, 또는 접전 구간 해당) |
| `segment_accuracy` | 해당 구간 실측 정확도 (`close_game` 은 약 0.61) |

**`ModelIdentity`** — 재현성 추적 (NFR-001)

| 필드 | 설명 |
|---|---|
| `artifact` | `model.joblib` 경로 |
| `sha256` | 아티팩트 해시 — 같은 확률이 같은 모델에서 나왔음을 증명 |
| `snapshot_minute` | 10 |
| `trained_at` | 학습 일시 |

**불변식** — 다섯 키가 항상 존재한다. 하나라도 빠지면 실패로 간주(A9).
일괄 처리(FR-003)는 **동일한 `PredictionResult` 의 배열**이며, 같은 입력에 대해 단건 결과와
완전히 일치해야 한다(SC-013). 따라서 일괄 경로는 단건 경로를 재사용한다.

---

## ⑤ 모델 파라미터 산출물 — `model_params.json` (A12 · FR-019)

웹 계층이 확률·근거·경고를 **자체 상수 없이** 재현하기 위한 유일한 입력이다.

| 필드 | 설명 | 소비처 |
|---|---|---|
| `feature_order` | 13개 순서 | 배열 인덱스 정합 |
| `coef[13]` · `intercept` | 로지스틱 파라미터 | 확률 계산 |
| `mean[13]` · `scale[13]` | StandardScaler 통계 | 정규화 |
| `cross_validated_factors[]` | 두 방법 공통 상위 지표명 | 근거 필터 (SC-015) |
| `warning_rules` | `{ ranges: schema min/max, close_game: { feature, threshold, accuracy } }` | 경고 발동 |
| `model` | `ModelIdentity` 와 동일 | 응답의 모델 식별 |

**불변식** — 모든 배열의 길이가 `len(feature_order)` 와 같다. `warning_rules` 의 수치는
`schema.json` · `errors.json` 에서 복사되며 **JS 쪽에 리터럴로 적히지 않는다**(원리 7).

---

## ⑥ 리포트 산출물

**`performance.json`** — 성능 리포트 (FR-005 · SC-001·002·005)

| 필드 | 설명 |
|---|---|
| `baseline_accuracy` | 무학습 기준선 (실측 0.5010) |
| `holdout_accuracy` | 홀드아웃 20% |
| `cv_mean` · `cv_std` | 5-fold 평균 · 표준편차 |
| `train_accuracy` · `train_cv_gap` | 학습 점수와 격차 (원리 5: 항상 병기) |
| `improvement_pp` | `(holdout − baseline) × 100` |
| `auc` · `brier` | 보조 지표 |

**불변식** — `cv_std < 0.02` (SC-005) · `train_cv_gap < 0.03` (NFR-004) ·
`improvement_pp ≥ 20` (SC-002) · `holdout_accuracy ≥ 0.70` (SC-001).
넷 중 하나라도 깨지면 학습이 실패를 반환한다.

**`errors.json`** — 오류 리포트 (FR-011)

| 필드 | 설명 |
|---|---|
| `bins[]` | `{ label, lower, upper, count, share, accuracy }` — 골드차 구간별 |
| `weakest_bin` | 정확도 최저 구간 (실측: 접전 ±1,000, 0.61) |

`weakest_bin` 이 `close_game` 경고의 `segment_accuracy` 원천이다.

**`match_types.json`** — 경기 유형 프로파일 (FR-020 · SC-017)

| 필드 | 설명 |
|---|---|
| `neutral_features[]` | 분류에 쓴 사이드 중립 지표 — **부호 있는 지표 0건** |
| `k` · `silhouette` | 선택된 군집 수와 근거 |
| `types[]` | `{ id, count, lead_team_win_rate, centroid, label }` |

**불변식** — `len(types) ≥ 2` (SC-017) · 모든 유형이 `count` 와 `lead_team_win_rate` 를
가진다 · `neutral_features` 에 `blue`/`red` 접두 컬럼이 없다.

**`parity_report.json`** — 파리티 검증 (FR-019 · SC-016)

| 필드 | 설명 |
|---|---|
| `compared` | 대조 건수 (홀드아웃 전량) |
| `max_abs_diff` | 최대 절대 오차 |
| `tolerance` | `1e-9` |
| `passed` | `max_abs_diff ≤ tolerance` |
| `verified_at` · `model_sha256` | 검증 일시 · 대상 모델 |

**불변식** — `passed == false` 이면 배포 중단(종료 코드 1). 이 파일 없이 배포된 웹 계층은
산출물로 인정하지 않는다(A12).

**`calibration.json`** 🆕 — 확신도 밴드 (M6 · FR-006 확장)

| 필드 | 설명 |
|---|---|
| `bands[]` | `{ lower, upper, count, accuracy }` — 확신도 `abs(p−0.5)×2` 10구간 |
| `low_confidence_band` | 최하위 밴드의 경계와 실측 정확도 |
| `brier` · `reliability[]` | 보정 점수와 신뢰도 곡선 점 |

**불변식** — `bands` 의 `count` 합 = 홀드아웃 행 수(1,976) · `accuracy` 가 확신도에
대해 **단조 증가**해야 한다(깨지면 보정 이상으로 보고 학습 실패). `low_confidence_band`
가 `low_confidence` 경고 문구의 유일한 수치 출처다.

**`comparison.json`** 🆕 — 구성 대조 (M3·M4 · FR-021)

| 필드 | 설명 |
|---|---|
| `split_id` | 전 구성이 공유한 분할 (`ml_split`) — **다르면 비교가 아니다** |
| `configs[]` | `{ dataset, n_features, cv_mean, cv_std, holdout, train_gap }` |
| `verdict` | 구성 간 우열 판정 문장 (실측: 유의한 우열 없음) |

**불변식** — 모든 `configs` 의 `split_id` 가 동일 · `n_features` 가 View 실제 컬럼 수와 일치.
분할이 하나라도 다르면 파일 생성을 거부한다(원리 3을 파일 수준에서 강제).

**`challenger.json`** 🆕 — 참조 모델 (M7 · NFR-003)

| 필드 | 설명 |
|---|---|
| `models[]` | `{ name, cv_mean, cv_std, train, holdout, overfit_gap, seconds }` |
| `external_references[]` | `{ source, snapshot_minute, tier, model, accuracy }` — R13 외부 비교 |
| `conclusion` | 로지스틱 채택 근거 문장 |

**불변식** — `external_references` 의 각 항목은 **`snapshot_minute` 와 `tier` 를 반드시 가진다.**
둘 중 하나라도 비면 인용을 거부한다 — 시점·모집단 없는 외부 수치는 비교가 아니라 소음이다(원리 3).
**이 파일은 `model_params` 를 만들지 않는다.** 웹이 읽을 경로가 없어 서빙이 구조적으로 불가능하다.

---

## ⑦ 모델 레지스트리 — `ml/registry.py` (v1.1 신규)

모델이 7종으로 늘면서 "어떤 모델이 어떤 데이터로 학습해 어떤 파일을 만드는가"가
여러 파일에 흩어질 위험이 생겼다. **레지스트리 하나가 그 대응의 단일 출처**다.

| 필드 | 설명 |
|---|---|
| `id` | `M1`~`M7` |
| `dataset` | `diff13` `gold2` `diff13` `clean27` `clean29` `cluster5` |
| `view` | 조회할 View 이름 (train/test 접미 규칙 포함) |
| `algorithm` | `logreg` `kmeans` `stats` `rf` `histgb` |
| `served` | **`True` 인 모델만** `model_params*.json` 을 생성하고 파리티 대상이 된다 |
| `artifacts[]` | 이 모델이 만드는 파일 목록 |
| `gates[]` | 적용되는 관문 (서빙 모델 7종 / 참조 모델 2종) |

**불변식**
- `served == True` 인 항목은 **정확히 M1·M2 두 개**다. 세 번째가 생기면 파리티 계획을 다시 세워야 하므로 테스트로 고정한다
- `served == False` 인 모델의 `artifacts` 에 `model_params` 가 포함되면 **오류**
- 모든 항목의 `view` 가 DB 에 실제로 존재해야 한다 (기동 시 대조 — R15 결손 재발 방지)
- `dataset` 이 같은 두 모델은 **같은 분할**을 본다 (`ml_split` 공유)

**왜 파일이 아니라 코드인가** — 레지스트리는 실행 중에 "이 모델이 서빙 대상인가"를 판정해야 한다.
JSON 으로 두면 웹 계층이 그것을 읽고 스스로 판단할 여지가 생기고, 그 순간 원리 7의 경계에 닿는다.

---

---

## 상태 전이 — 아티팩트 생명주기

```
   (없음)
      │  train.py --minute 10
      ▼
  학습 완료 ──── 성능 불변식 위반 ──▶ 실패 (아티팩트 미생성)
      │
      │  저장 + 복원 대조 (FR-008)
      ▼
  저장 검증 ──── 불일치 ──▶ 실패 (파일 삭제)
      │
      │  parity.py
      ▼
  파리티 합격 ──── 불일치 1건 ──▶ 배포 중단
      │
      ▼
  배포 가능 (웹 데모 실행 허용)
```

각 관문은 **통과해야 다음이 존재한다**. "일단 저장하고 나중에 확인"이 없다 —
검증되지 않은 산출물이 배포 가능 상태로 남는 것을 구조적으로 막는다.
