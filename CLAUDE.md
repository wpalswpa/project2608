# 이 저장소에서 일하는 규칙

## 검수 분담

| 누가 | 무엇을 | 왜 |
|---|---|---|
| **사람 (이제민)** | `README.md` · `STUDY.md` | 밖으로 나가는 글. 눈높이와 말투는 사람이 판단한다 |
| **Claude** | `docs/` · `reports/` · `model_card.md` · `lolwin/` · `src/` · `web/` · `tests/` | 기계로 검증되는 것들. 사람이 다 읽을 필요 없다 |

그래서 루트에는 사람이 볼 두 개만 둔다 — `README.md`, `STUDY.md`.
나머지 문서는 전부 `docs/` 안에 있다.

**Claude 담당 파일을 고쳤으면 사람에게 보고할 것은 "무엇이 왜 바뀌었나" 한 줄이면 된다.**
파일 내용을 다시 읽어달라고 요구하지 않는다.

## 손대면 안 되는 것

| 대상 | 이유 |
|---|---|
| `specs/002-ml-prediction-service/` | 팀 서버 정본. 서버에서 `git pull` 로 갱신된다 |
| `docs/_archive/` · `**/_server_backup_*` | 계획 시점 보존용 스냅샷. 링크가 깨져 있는 게 정상 |
| `artifacts/model.joblib` · `schema.json` | 재학습 없이는 바꾸지 않는다 (바꾸면 골든 정답지도 다시) |

## 무엇을 고치든 통과해야 하는 것

```bash
python tests/test_regression.py    # 예측 50건이 정답지와 완전히 같은가
python src/factcheck.py            # 문서 수치가 근거 파일과 맞는가 (0건이어야 함)
./check_project.sh test            # 서빙 파리티 + API 스모크
```

**규칙을 새로 만들면 반드시 틀린 값을 넣어 잡히는지 확인한다.**
과거에 아무것도 못 잡는 정규식을 두 번 만들었다.

## 숫자를 바꿀 때

문서에 적힌 수치는 전부 `reports/tables/` 의 CSV가 근거다.
수치가 바뀌면 **근거 파일부터 다시 만들고** 문서를 고친다. 반대로 하지 않는다.

`0.7394` 같은 대표 수치는 문서 19곳에 있다. 합칠 수 없으므로(서버 정본 포함)
`factcheck` 가 근거 파일과 대조하는 방식으로 관리한다.

## 피처를 바꿀 때

`lolwin/features.py` 가 유일한 정본이다. 여기만 고치고:

```bash
python lolwin/features.py --sql     # SQL 뷰 다시 뽑기
python -c "from lolwin.features import sql_matches_file; print(sql_matches_file())"
```

DB 뷰와 파이썬이 어긋나면 학습 값이 조용히 달라진다.
