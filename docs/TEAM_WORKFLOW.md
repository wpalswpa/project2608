# 팀 협업 규칙 — 브랜치 하나(`main`), 포지션별 담당

저장소: `https://github.com/wpalswpa/project2608` · 브랜치는 **`main` 하나만** 쓴다.
공개 서비스: **https://p4.sumzip.com** (팀 서버 = 맥 192.168.0.19, 프런트 9504 · 백엔드 9524)

## 포지션 4개와 담당 폴더 (4인)

| # | 포지션 | 책임 | 담당 폴더·파일 | 담당자 |
|---|---|---|---|---|
| 1 | **데이터·피처** | DB 적재·분할 고정·뷰 4종, 중복 제거·차이 피처, 경기 유형 군집, 입력 허용 범위 | `db/` · `data/` · `src/day1_baseline.py` `day2_features_cluster.py` `day2b_game_types.py` `load_from_db.py` · `specs/…/data-model.md` | |
| 2 | **모델·해석** | 8종 비교→로지스틱, 승리요인(계수×permutation), 실험 B(10 vs 15분), 모델 저장·복원 | `src/finalize_model.py` `timepoint_compare.py` · `artifacts/` · `model_card.md` · `specs/…/research.md` | |
| 3 | **평가지표·검증** | 정확도·F1·AUC·Brier, 5-fold·시드 10회, 오류 구간(접전 0.615↔결정 0.947), 캘리브레이션, 찍기 대비 개선 폭, SC-1~6 채점표 관리, 파리티·스모크 테스트, `factcheck` 0건 유지 | `src/repeat_check.py` `factcheck.py` · `web/test_parity.py` `test_api.py` · `reports/*.csv` · `runs.csv` · `specs/…/spec.md` 채점표 · `/api/report` 내용 | |
| 4 | **서비스·문서·발표** | 백엔드/프런트 운영·배포(p4.sumzip.com), DDBM 사이트(캔버스·시스템 의도·설계 문서), README·PPT, SC-7 스모크 테스트 | `predict.py` · `web/` · `check_project.sh` · `README.md` · `docs/` · `specs/…/plan.md` `quickstart.md` `tasks.md` · `presentation_draft.pptx` · `Intent-*.md` | |

- **평가지표 담당(3)**이 "숫자의 최종 책임자"다: 문서·발표·API에 나가는 모든 성능 수치는 3번이 `reports/`·`runs.csv`로 근거를 갖고 있어야 하고, 대표값은 **반복 평균 0.7366 ± 0.0081**(단일 분할 0.7394는 표본)로 통일한다.
- 1→2→3 순서로 산출물이 흐른다(뷰 → 모델 → 평가). 4는 셋의 결과를 사이트·문서·발표로 내보낸다.
- 담당 폴더 밖을 고칠 땐 게시판/메신저로 먼저 알린다. 같은 파일을 두 사람이 동시에 고치지 않는다.

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
