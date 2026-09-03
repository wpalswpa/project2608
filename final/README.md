# 제출물 6종

계획서 §6.2 의 필수 산출물입니다. **원본을 복사해 모아둔 것**이라,
고칠 때는 원본을 고치고 `python scripts/build_submission.py` 를 다시 돌리세요.
(원본을 옮기면 코드가 경로로 찾지 못해 프로젝트가 깨집니다)

| # | 제출물 | 원본 위치 | 무엇이 들어가는가 |
|---|---|---|---|
| 1 | `1_README.md` | `README.md` | 문제 정의 · 실행 방법 · 구조 |
| 2 | `2_최종_노트북.ipynb` | `reports/model_report.ipynb` | 클린 런타임에서 무오류 실행 |
| 3 | `3_model.joblib` | `artifacts/model.joblib` | 전처리 포함 Pipeline 전체 |
| 4 | `4_schema.json` | `artifacts/schema.json` | 입력 컬럼 · 타입 · 허용 범위 |
| 5 | `5_predict.py` | `predict.py` | predict(payload) -> dict |
| 6 | `6_model_card.md` | `model_card.md` | 용도 · 성능 · 사용 금지 상황 |

## 무결성 확인

복사본이 원본과 같은지 확인하려면 아래 값을 대조하세요 (SHA-256 앞 8자리).

| 파일 | 해시 |
|---|---|
| `1_README.md` | `110cc9ed` |
| `2_최종_노트북.ipynb` | `e96dc6c3` |
| `3_model.joblib` | `75438aa6` |
| `4_schema.json` | `b83f9541` |
| `5_predict.py` | `1d7d287d` |
| `6_model_card.md` | `0c5bb6ca` |

생성 시각: 2026-09-03 16:15
