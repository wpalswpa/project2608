# 팀 협업 규칙 — 브랜치 하나(`main`), 포지션별 담당

저장소: `https://github.com/wpalswpa/project2608` · 브랜치는 **`main` 하나만** 쓴다.
공개 서비스: **https://p4.sumzip.com** (팀 서버 = 맥 192.168.0.19, 프런트 9504 · 백엔드 9524)

## 포지션과 담당 폴더

| 포지션 | 담당 폴더·파일 | 담당자 |
|---|---|---|
| 데이터·DB | `db/` · `data/` · DB 뷰(`v_diff13_*` 등) · `src/load_from_db.py` | |
| 모델·분석 | `src/day*.py` `finalize_model.py` `repeat_check.py` `timepoint_compare.py` · `artifacts/` · `reports/` · `notebooks/` | |
| 서비스(웹·API) | `predict.py` · `web/` · `check_project.sh` · `requirements.txt` | |
| 문서·발표 | `README.md` · `docs/` · `specs/002-ml-prediction-service/` · `model_card.md` · `presentation_draft.pptx` | |

담당 폴더 밖을 고칠 땐 게시판/메신저로 먼저 알린다. 같은 파일을 두 사람이 동시에 고치지 않는다.

## 매번 이 순서로 (하나의 브랜치를 안전하게 공유하는 법)

```bash
git pull                      # 1. 시작 전 항상 최신으로 (pull.rebase=true 라 내 커밋이 위로 올라간다)
# ... 작업 ...
./check_project.sh test       # 2. 서비스·predict.py 를 건드렸으면 파리티·스모크 통과 확인
git add -A && git commit -m "포지션: 무엇을 왜"   # 3. 작게, 자주
git pull && git push          # 4. 올리기 직전에 한 번 더 pull
```

- 충돌이 나면 **내 담당 폴더는 내 것, 남의 폴더는 남의 것**으로 푼다. 모르겠으면 덮어쓰지 말고 물어본다.
- 커밋하지 않는 것: `.env`(비밀번호·API 키) · `venv*/` · `data/*.csv`(라이선스·97MB) · `run/` `logs/` — `.gitignore`가 막아주지만 `git status`로 확인.
- 문서 숫자를 바꿨으면 `python src/factcheck.py` 가 0건인지 본다.

## 팀 서버(공개 서비스)에 반영하기

`main`에 push 했다고 사이트가 바뀌지 않는다. 팀 서버에서 한 번 실행한다:

```bash
ssh pioneer4@192.168.0.19        # 또는 서버에 앉은 사람이
cd ~/project2608 && ./check_project.sh deploy    # git pull → 재시작 → 테스트
./check_project.sh status        # https://p4.sumzip.com 200 확인
```

DDBM 사이트의 "시스템 설계 구현 상태"도 이 폴더(`specs/002-ml-prediction-service/`)를 읽으므로 같은 명령으로 갱신된다.

## 처음 합류할 때 (Windows·macOS 공통)

```bash
git clone https://github.com/wpalswpa/project2608.git && cd project2608
python3.11 -m venv venv311            # Windows: py -3.11 -m venv venv311
venv311/bin/pip install -r requirements.txt     # Windows: venv311\Scripts\pip install -r requirements.txt
cp .env.example .env                  # DB_PASSWORD 만 채운다 (커밋 금지)
venv311/bin/python predict.py --demo  # 51.2% / 94.6% / 16.8% 가 나오면 환경 OK
```

줄바꿈은 `.gitattributes`로 LF 통일돼 있어 Windows에서도 그대로 쓰면 된다. Python은 **3.11** (모델이 scikit-learn 1.9.0 저장본).
