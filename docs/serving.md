<!-- ─────────────────────────────────────────────
  서빙 계약 — 무엇을 넣으면 무엇이 나오는가.
  왜 필요한가: 여기 적힌 것이 바뀌면 쓰는 쪽이 깨진다. tests/test_contract.py 가 이 문서대로 도는지 검사한다.
  주로 보는 사람: 서비스 연동 · Claude(검수)
  ───────────────────────────────────────────── -->

# 서빙 계약 — 무엇을 넣으면 무엇이 나오나

이 문서가 **약속**이다. 여기 적힌 것이 바뀌면 쓰는 쪽이 깨지므로,
바꾸려면 버전을 올리고 `tests/test_contract.py` 를 함께 고친다.

배포·운영 절차는 [deploy.md](deploy.md), 왜 이렇게 만들었는지는 [../README.md](../README.md).

---

## 1. 부르는 방법 세 가지

셋 다 **같은 함수**(`lolwin.predict`)를 부른다. 그래서 답이 갈릴 수 없다.

| 방법 | 쓰는 곳 |
|---|---|
| `from lolwin import predict` | 파이썬 코드·노트북 |
| `POST /api/predict` | 웹 화면, 외부 연동 |
| `lolwin-predict '{...}'` | 터미널에서 한 건 확인 |

계산은 `lolwin` 안에서만 일어난다 — 구조는 **6장**에서 자세히 본다.

## 2. 입력

**13개 피처가 전부 있어야 한다.** 하나라도 빠지면 거부한다.
전부 `블루 − 레드` 차이값이고 **양수면 블루 우세**다.

| 피처 | 뜻 | 형 |
|---|---|---|
| `FirstBlood` | 첫 킬을 블루가 가졌나 | 0 또는 1 |
| `KillsDiff` | 킬 차이 | 정수 |
| `GoldDiff` | 골드 차이 | 정수 |
| `ExpDiff` | 경험치 차이 | 정수 |
| `AssistsDiff` | 어시스트 차이 | 정수 |
| `DragonsDiff` | 드래곤 차이 | 정수 |
| `HeraldsDiff` | 전령 차이 | 정수 |
| `TowersDestroyedDiff` | 타워 파괴 차이 | 정수 |
| `AvgLevelDiff` | 평균 레벨 차이 | 실수 |
| `TotalMinionsKilledDiff` | 미니언(CS) 차이 | 정수 |
| `TotalJungleMinionsKilledDiff` | 정글 몬스터 차이 | 정수 |
| `WardsPlacedDiff` | 와드 설치 차이 | 정수 |
| `WardsDestroyedDiff` | 와드 제거 차이 | 정수 |

허용 범위는 `artifacts/schema.json` 의 `train_min`~`train_max`.
**범위를 벗어나도 막지 않는다** — 이례적인 경기를 아예 못 보게 되기 때문이다.
대신 `warnings` 에 담아 돌려준다.

## 3. 출력

```json
{
  "win_prob_blue": 0.8183,
  "pred": 1,
  "pred_label": "블루 승리 예측",
  "top_factors": [
    {"feature": "GoldDiff", "name": "골드(돈) 차이", "value": 2000.0,
     "contribution": 0.9901, "direction": "블루에 유리"}
  ],
  "warnings": [],
  "meta": {"model": "...", "version": "1.0", "time_point_min": 10,
           "holdout_accuracy": 0.7394}
}
```

| 필드 | 보장 |
|---|---|
| `win_prob_blue` | 0~1 실수, 소수 **4자리 반올림** |
| `pred` | `win_prob_blue >= 0.5` 이면 1, 아니면 0 |
| `top_factors` | **정확히 5개**, 기여도 절대값 내림차순 |
| `contribution` | 계수 × 표준화값. **양수 = 블루에 유리** |
| `warnings` | 문자열 목록. 비어 있으면 정상 |

**`contribution` 해석 주의** — 이 값은 "다른 지표를 통제한 뒤" 남은 몫이다.
킬은 골드와 상관 +0.92라 음수로 나올 수 있는데, **"킬을 하면 진다"는 뜻이 아니다.**
화면에 그대로 띄우지 말고 설명을 함께 붙인다 ([../STUDY.md](../STUDY.md) 10번).

## 4. 에러 규약

| 상황 | 함수 | HTTP |
|---|---|---|
| 피처 누락 | `ValueError` | **400** + 빠진 피처 목록 |
| 값이 학습 범위 밖 | 정상 반환 | **200** + `warnings` |
| JSON 형식 오류 | — | **400** |
| 없는 경로 | — | **404** |
| 모델 파일 없음 | `FileNotFoundError` | **500** |

**범위를 벗어난 입력을 400으로 막지 않는 것이 의도된 설계다.** 막으면
"프로 경기라 골드차가 12,000" 같은 경우를 아예 예측할 수 없게 된다.
믿을지 말지는 `warnings` 를 보고 쓰는 쪽이 정한다.

## 5. 그 밖의 엔드포인트

| 경로 | 돌려주는 것 |
|---|---|
| `GET /api/health` | 모델 메타 + 서빙 파리티 실측 |
| `GET /api/schema` | 피처 13개와 허용 범위 |
| `GET /api/examples` | 예시 입력 3건 |
| `GET /api/report` | 구간별 정확도·승리요인·시점 비교 |
| `GET /api/match-types` | 경기 유형 4가지 프로파일 |
| `POST /api/predict/batch` | 여러 건 한 번에 |
| `POST /api/coach` | **감독** — 지금 상태에서 무엇을 했다면 승률이 얼마나 올랐나. 13개 피처(+선택 `verdict`)를 넣으면 상승폭 큰 순으로 조언 |
| `GET /api/champions` | 챔피언 x 라인 승률표 (`position` 으로 라인 필터). 마스터 이상 솔로랭크 **관찰 승률**이지 모델 예측이 아니다 |
| `GET /api/matches` | **시험셋 복기 (검증·재현용 — 사용자 화면에서는 쓰지 않는다)** — 예측 vs 실제, `top_factors` 에 실제 격차 `value` 포함, 필터(`band`·`correct`)·페이징·번호 조회(`id`) |
| `POST /api/summoner` | Riot ID 로 최근 솔로랭크 경기를 10분 시점 복기 (`count` 1~10 · `start` 로 페이지) (`RIOT_API_KEY` 필요, 없으면 503). 경기마다 `band`·`my_win_prob`·`my_won`·`verdict`·`played_at`, 전체 `summary`(판정별 건수·`period`) 포함 |
| `GET /figures/<이름>` | `reports/` 의 그림 (사본을 두지 않는다) |

## 6. 구현 구조 — 누가 계산하나

```
브라우저 → web/frontend.py (9504) → web/app.py (9524) → lolwin.predict → artifacts/model.joblib
            화면·중계만              예측 API            예측 전담        학습된 모델 (2.2KB)
```

**각 계층이 무엇을 import 하는지**가 곧 "누가 계산하는가"다.

| 파일 | import 하는 것 | 하는 일 |
|---|---|---|
| `web/frontend.py` | `flask` · `urllib` | 화면을 내려주고 `/api/*`를 백엔드로 **중계만**. 예측 코드 0줄 |
| `web/app.py` | `flask` · **`from lolwin import predict`** | 입력을 받아 `predict()`에 넘기고 결과를 JSON으로 반환 |
| `lolwin/predict.py` | **`joblib` · `pandas` · `numpy`** | 모델을 불러 확률과 승리요인을 계산 — **계산은 이 파일뿐** |
| `predict.py` (루트) | `from lolwin.predict import …` | 명령행·기존 코드용 호환 진입점. 계산 없음 |

**`web/` 어디에도 `sklearn`·`joblib` import 가 없다.** 웹은 계산하지 않고 `predict()` 를 부를 뿐이다.
계산이 두 곳에 있으면 화면 확률과 모델 확률이 갈라져도 아무도 모르기 때문이다.

### model.joblib 안에는 무엇이 들어 있나

```
Pipeline
 ├─ scaler → StandardScaler      평균 13개 · 표준편차 13개
 └─ model  → LogisticRegression  계수 13개 + 절편 −0.0043
```

**딱 이게 전부다(2,209 bytes).** 파이프라인을 통째로 저장했기 때문에
예측할 때 **표준화를 빠뜨릴 수가 없다.** 스케일러와 회귀식이 한 덩어리로 묶여 있어서다.

### /api/summoner 응답 — 화면이 계산하지 않도록 서버가 주는 것

| 필드 | 값 | 왜 서버가 주나 |
|---|---|---|
| `actual` | **문자열** `"블루 승리"` / `"레드 승리"` | 1/0 이 아니다 |
| `model_correct` | bool | 블루 기준 예측이 맞았나 |
| `my_side` | `"블루"` / `"레드"` | 사용자는 자기 팀 기준으로 읽는다 |
| `my_win_prob` | 0~1 실수 | 내가 레드면 `1 - win_prob_blue` — 화면이 뒤집지 않게 |
| `my_won` | bool | 〃 |
| `roster` | 참가자 10명 (이름·챔피언·포지션·KDA·진영·본인여부) | 이미 받은 match 응답에 있어 추가 호출 0회 |
| `band` | 구간 이름 문자열 | 경계 정본은 `lolwin/features.py` — 화면에 숫자를 적지 않기 위해 |
| `verdict` | `우세승` · `역전승` · `역전패` · `열세패` | 10분 유불리 x 실제 결과 |

응답 최상위에 `rank`(솔로랭크 티어, 조회 실패 시 null)와 `next_start` 가 온다.
`summary` 에 `n` · `avg_win_prob_10min` · 판정별 건수 · `model_correct` 가 들어 있어
첫 화면 요약 타일이 세지 않아도 된다.

**`verdict` 가 이 서비스의 존재 이유다.** 다른 전적 사이트는 "무슨 일이 있었나"(KDA·CS)를
보여주지만, 10분 시점 모델이 있어야 **"언제 갈렸나"** 를 말할 수 있다.
특히 `역전패`(10분에 유리했는데 짐)는 복기 가치가 가장 높다.

### /api/coach — 조언이 뒤집히지 않게 하는 장치

계수를 그대로 쓰면 **"킬하지 마라 · CS 먹지 마라"** 가 나온다. `KillsDiff` 계수는
−0.107, `TotalMinionsKilledDiff` 는 −0.157 이기 때문이다(다중공선성).

골드를 고정한 채 CS 만 올리는 것은 **현실에 없는 상황**이다. 그래서 지표를 올릴 때
**따라오는 골드도 함께** 올린다 (`lolwin/coach.py` 의 `GOLD_PER_UNIT`, 학습셋 실측).

```
CS +20 만            41.8% → 39.4%   (틀림)
CS +20 & 골드 +1,018  41.8% → 51.9%   (맞음)
```

`tests/test_coach.py` 가 **모든 조언이 승률을 올리는지** 검사하고, 동시에
골드를 안 올린 순진한 계산은 **실제로 뒤집히는지도** 확인한다 —
검사가 늘 통과하는 무의미한 검사가 아님을 증명하기 위해서다.

**해석 한계** — 이 값은 관찰 데이터의 동반 변화로 계산한 가정 계산이지 개입 효과가 아니다.
응답의 `how_to_read` 필드가 이 읽는 법을 함께 싣는다 — 화면 없이 API 만 쓰는 쪽도 같은 선을 지키게.
화면 문구도 "그랬던 경기들은 이랬다" 수준을 넘지 않는다 ([../STUDY.md](../STUDY.md) 17번).

### 진행 중인 경기의 실시간 승률은 왜 없나

**공개 API 로는 불가능하다.** 모델은 10분 시점의 골드·킬·CS 차이 13개를 요구하는데,
`spectator-v5`(진행 중 경기)는 **참가자·챔피언·밴·시작 시각만** 준다 — 실시간 수치가 없다.
`match-v5` 타임라인에 그 값들이 있지만 **경기가 끝난 뒤에만** 열린다.

가능한 경로는 **Live Client Data API**(`127.0.0.1:2999`)뿐인데, 게임이 돌아가는
**본인 PC 에서만** 접근된다. 즉 웹 서비스가 아니라 오버레이 프로그램이어야 한다.
그래서 지금은 **끝난 경기 복기**로 범위를 정했다.

## 7. 이 계약을 지키는지 확인

```bash
python tests/test_contract.py       # 출력 형식·에러 규약
./check_project.sh test             # 서빙 파리티 + API 스모크
```

파리티 테스트는 **직접 호출·백엔드·프런트 세 경로의 확률이 같은지** 본다.
하나라도 어긋나면 화면이 거짓말을 하고 있다는 뜻이다.
