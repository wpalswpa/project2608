# Quickstart — ML 승패예측·설명 서비스

**Feature**: `002-ml-prediction-service` | **Date**: 2026-08-31

초기화된 환경에서 **학습 → 예측 → 검증 → 화면**까지 도달하는 최단 경로다.
이 문서의 순서가 그대로 `README.md` 의 "실행 방법"과 최종 노트북의 셀 순서가 된다 —
셋이 어긋나면 재현이 깨지기 때문에(A8), **한 곳을 고치면 셋을 함께 고친다**.

> 📌 아래 `⬜` 표시된 단계는 아직 구현 전이다. `✅` 는 지금 실행하면 동작한다.

---

## 0. 사전 준비 (5분)

**필요한 것** — Python 3.9+ · Node.js 20+ · 팀 DB 접근 권한. **Docker 는 쓰지 않는다.**

```bash
git clone <저장소> && cd project2608

# 접속 정보는 환경 변수로만 주입한다. .env 는 커밋되지 않는다(.gitignore).
cp .env.example .env
$EDITOR .env            # DB_PASSWORD 채우기

# Python
python3 -m venv venv
venv/bin/pip install -r requirements.txt        # ⬜ 파일 생성 예정

# Node
npm install                                      # 루트: mysql2 (DB 스크립트용)
npm --prefix backend install                     # ⬜
npm --prefix frontend install                    # ⬜
```

**막히면 여기부터 본다** — `DB_PASSWORD` 가 없으면 모든 스크립트가 안내 메시지를 내고
즉시 멈춘다. "왜 안 되는지 모르겠는" 상태로 진행되지 않게 하려는 의도다(E8).

---

## 1. 데이터 계층 확인 ✅ (이미 동작)

```bash
node scripts/create-views.js          # View 12종 적용 + 51항목 검증
node scripts/create-views.js --check  # 검증만 (DB 변경 없음)
```

기대 출력 — `51 PASS / 0 FAIL`. 하나라도 FAIL 이면 **학습으로 넘어가지 않는다.**

| 층 | View | 쓰임 |
|---|---|---|
| 피처 | `v_lol_10min_diff14` · `clean29` · `simple2` · `neutral` | 학습 입력 · 대조군 · 간편 입력 · 경기 유형 |
| 시점 | `v_feature_axis` · `v_snapshot_features` · `v_snapshot_train`/`_test` · `v_snapshot_feature_long` | FR-009 시점 축 + 고정 분할 |
| 요인 | `v_win_factor_stats` · `v_win_factors` · `v_win_factor_bins` | 승리요인 순위 · 격차 구간 |

분할은 `ml_split` 테이블에 고정되어 있다(train 7,903 / test 1,976).
원천 테이블에는 쓰지 않는다. 멱등이라 몇 번을 실행해도 같다.

---

## 2. 학습 ⬜

```bash
venv/bin/python -m ml.train --minute 10
```

**약 1초**에 끝난다(실측 0.1초). 오래 걸리면 뭔가 잘못된 것이다.

산출 → `artifacts/10min/`

| 파일 | 내용 |
|---|---|
| `model.joblib` | **전처리 포함 파이프라인 전체** (추정기만 저장 금지 — E9) |
| `schema.json` | 입력 계약 14개, 컬럼·자료형·허용범위 |
| `model_params.json` | 웹 계층이 읽을 계수·절편·정규화 통계·근거 목록·경고 규칙 |
| `performance.json` | 기준선 대비 개선 폭, 교차검증 평균±표준편차, 학습–검증 격차 |
| `errors.json` | 골드차 구간별 정확도 |
| `match_types.json` | 경기 유형별 경기 수 + 10분 리드팀 최종 승률 |

**학습이 스스로 실패하는 조건** — 아래 중 하나라도 깨지면 아티팩트를 만들지 않는다.
사람이 나중에 확인하는 방식은 반드시 새어나가기 때문이다.

| 관문 | 기준 | 근거 |
|---|---|---|
| 홀드아웃 정확도 | ≥ 0.70 | SC-001 |
| 기준선 대비 | ≥ +20%p | SC-002 |
| 교차검증 표준편차 | < 0.02 | SC-005 |
| 학습–검증 격차 | < 0.03 | NFR-004 |
| 공통 상위 요인 | ≥ 5개 | SC-003 |
| 피처 수 | 정확히 14 | SC-012 |
| 저장·복원 예측 일치 | 완전 일치 | SC-004 · FR-008 |

마지막 관문이 특히 중요하다 — 저장 직후 **원본 형태 입력**으로 복원본과 대조하고,
어긋나면 **저장 파일을 지우고 실패**시킨다. 통과하지 못한 산출물이 남지 않게 하려는 것이다.

---

## 3. 예측 ⬜

**함수로** (S1 · 단일 진입점)

```python
from ml.predict import predict

result = predict({
    "wardsPlacedDiff": -12, "wardsDestroyedDiff": 2, "firstBloodDiff": 1,
    "killsDiff": 4, "assistsDiff": 5, "eliteMonstersDiff": 1,
    "dragonsDiff": 1, "heraldsDiff": 0, "towersDestroyedDiff": 0,
    "goldDiff": 2944, "avgLevelDiff": 0.4, "experienceDiff": 3092,
    "totalMinionsKilledDiff": 18, "totalJungleMinionsKilledDiff": 3,
})

result["win_probability"]   # 0.841...
result["predicted_class"]   # "win"
result["factors"][0]        # {"name": "goldDiff", "direction": "+", ...}
result["warnings"]          # []  — 접전·범위 밖이면 채워진다
result["model"]["sha256"]   # 어느 모델이 낸 값인지
```

**명령행으로**

```bash
venv/bin/python -m ml.predict --input examples/sample.json
venv/bin/python -m ml.predict --input examples/batch.json --batch
```

**경고와 거부는 다르다**

| 상황 | 결과 |
|---|---|
| 값이 학습 관측 범위 밖 | 예측 **반환** + `out_of_range` 경고 |
| 접전 구간(`abs(goldDiff) ≤ 1000`) | 예측 **반환** + `close_game` 경고 (구간 정확도 0.61 동봉) |
| 컬럼 누락 · 이름 불일치 · 자료형 불일치 | **거부** — 예외. 결과 사전을 반환하지 않는다 |
| 계약에 없는 키 추가 | **거부** — 시점 이후 정보 유입 차단 |

---

## 3-1. 부가 모델 ⬜ (plan v1.1)

핵심 경로(2~4절)가 끝난 뒤에 돈다. **전부 합쳐 1분 이내**다.

```bash
# M2 간편 입력 모델 — 서빙 대상이므로 파리티에도 포함된다
python -m ml.train --dataset gold2

# M5 경기 유형 군집 · M6 확신도 밴드
python -m ml.match_types
python -m ml.calibration

# M3·M4 구성 대조 (6구성 동일 분할) · M7 챌린저 (참조 전용, ~52초)
python -m ml.compare
python -m ml.challenger
```

| 산출 | 어디에 쓰이나 |
|---|---|
| `model_params.simple.json` | 화면 "간편 입력" 탭 · 파리티 대상 |
| `match_types.json` | `GET /api/match-types` |
| `calibration.json` | `low_confidence` 경고의 수치 |
| `comparison.json` · `challenger.json` | `GET /api/comparison` · `model_card.md` |

> **M3·M4·M7 은 서빙 경로에 없다.** `model_params` 를 만들지 않으므로 웹이 읽을 파일이 없고,
> 일정이 압박되면 **가장 먼저 잘라낼 수 있다.** 잘라도 시연은 성립한다.

---

## 4. 파리티 검증 ⬜ — 웹을 켜기 전에 반드시

> **서빙 모델이 늘면 파리티 대상도 는다.** M2 를 학습했다면 파리티는 M1·M2 **둘 다** 홀드아웃
> 전량으로 돈다. 레지스트리의 `served == True` 집합과 파리티 대조 집합이 다르면 검증이 실패한다.

```bash
venv/bin/python -m ml.parity --minute 10
```

홀드아웃 **전량**을 `predict.py` 와 `backend/src/predictor.js` 두 경로에 통과시켜
승리 확률이 `1e-9` 이내로 전건 일치하는지 본다. 서버를 띄우지 않아도 돌아간다.

```
compared        1,976
max_abs_diff    3.2e-16
tolerance       1e-9
passed          true                 -> artifacts/10min/parity_report.json
```

**불일치가 1건이라도 있으면 종료코드 1 이고 배포가 중단된다.** 이 리포트 없이
배포된 웹 계층은 산출물로 인정하지 않는다 — 예측 로직이 두 곳에 생기는 순간
두 답이 갈라지고, 갈라져도 아무도 모르기 때문이다.

---

## 5. 웹 데모 ⬜

```bash
npm --prefix backend run dev     # http://localhost:3000
npm --prefix frontend run dev    # http://localhost:5173
```

브라우저에서 예시 경기를 고르거나 지표를 직접 입력하면
**승률 · 근거 지표(방향과 크기) · 경고가 한 화면에** 표시된다(AS12).

서버는 기동 시 `parity_report.json` 의 `passed` 를 확인하고, 없거나 실패면
`/api/predict` 를 **503 으로 막는다**. 검증되지 않은 확률이 화면에 뜨지 않게 하려는 것이다.

**서버가 내려가도 예측·평가·산출물은 모두 성립한다** — 웹은 시연 계층이다(E12).

---

## 6. 클린 재실행 ⬜ — 채점자·검토자용

```bash
venv/bin/jupyter nbconvert --to notebook --execute --inplace \
  notebooks/final_analysis.ipynb
```

초기화된 커널에서 처음부터 끝까지 돌아 **오류 0건으로 완주**하고, 노트북이 기록한
수치가 `artifacts/` 리포트와 일치해야 한다(SC-011).

노트북은 얇다 — 분석 로직은 `ml/` 모듈에 있고 노트북은 호출·표·그림만 담는다.
로직이 노트북 안에만 있으면 `predict.py` 와 갈라진다.

---

## 7. 전체를 한 번에

```bash
make all      # ⬜ views -> train -> parity -> notebook -> 산출물 점검
```

---

## 문제가 생기면

| 증상 | 원인 | 조치 |
|---|---|---|
| `DB_PASSWORD 없음` | `.env` 미생성 | 0단계 |
| `create-views.js` FAIL | 원천 데이터가 바뀜 | 원천 확인 후 `measured-facts.md` 갱신 |
| 학습이 관문에서 실패 | 데이터·전처리 문제 | 성능을 올리려 하지 말고 **되짚는다**. 튜닝 먼저는 금지 |
| `SnapshotUnavailableError: minute=15` | 15분 데이터 미확보 | **정상 동작이다**. 시점 비교는 후속 과제(A4) |
| 파리티 `passed: false` | 웹 계층이 옛 파라미터 보유 | `model_params.json` 재적재. 그래도 어긋나면 JS 산술의 연산 순서 확인 |
| 화면 확률과 `predict.py` 가 다름 | 웹이 값을 보정 중 | **금지 사항**(NFR-008). 보정 코드를 제거한다 |

---

## 실행 시간 예산

| 단계 | 시간 |
|---|---|
| View 적용·검증 | ~3초 |
| 학습 (14피처 · 9,879행) | ~1초 |
| 파리티 (홀드아웃 전량) | ~2초 |
| 노트북 클린 재실행 | ~30초 |

단일 처리 코어 기준이다(NFR-005 · NFR-007). 어느 단계든 분 단위로 늘어나면
설계가 아니라 구현이 잘못된 것이다.
