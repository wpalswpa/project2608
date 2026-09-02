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

```
브라우저 → frontend.py(9504) → app.py(9524) → lolwin.predict → model.joblib
             중계만              얇은 API        계산            학습된 모델
```

**웹 계층에는 `sklearn`·`joblib` import 가 없다.** 계산은 `lolwin` 안에서만 일어난다.

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
| `GET /figures/<이름>` | `reports/` 의 그림 (사본을 두지 않는다) |

## 6. 이 계약을 지키는지 확인

```bash
python tests/test_contract.py       # 출력 형식·에러 규약
./check_project.sh test             # 서빙 파리티 + API 스모크
```

파리티 테스트는 **직접 호출·백엔드·프런트 세 경로의 확률이 같은지** 본다.
하나라도 어긋나면 화면이 거짓말을 하고 있다는 뜻이다.
