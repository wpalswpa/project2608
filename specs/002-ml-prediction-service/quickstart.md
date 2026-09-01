<style>
.speckit-viewer-inline, .speckit-viewer-inline h1, .speckit-viewer-inline h2, .speckit-viewer-inline h3, .speckit-viewer-inline h4, .speckit-viewer-inline p, .speckit-viewer-inline li, .speckit-viewer-inline td, .speckit-viewer-inline th, .speckit-viewer-inline strong, .speckit-viewer-inline em, .speckit-viewer-inline blockquote { color: #111111 !important; font-style: normal; }
.speckit-viewer-inline { background: #ffffff !important; }
.speckit-viewer-inline pre, .speckit-viewer-inline pre * { color: #e2e8f0 !important; }
</style>

# 왜 그렇게 결정했나 (research)

주요 결정과 그 이유를 문답으로 정리했다.

**Q. 왜 로지스틱 회귀인가? 더 좋은 모델도 많지 않나**
8종을 똑같은 조건에서 붙여본 결과가 근거다. 로지스틱이 점수 1등이었고,
복잡한 모델일수록 오히려 점수가 낮았다. 랜덤포레스트는 연습 만점(1.0000)인데
검증에서 떨어졌다 — 문제집을 외운 것이다. 그리고 이 프로젝트의 목표가 "왜까지 설명"인데,
로지스틱만 요인별 가중치를 숫자로 보여준다. 점수가 비슷하면 설명되는 쪽이 맞다.

**Q. 왜 13개만 넣나? 컬럼을 더 만들면 점수가 오르지 않나**
안 오른다. 돈 차이·경험치 차이 딱 2개만 넣어도 0.7328로 전체와 거의 같다.
돈·경험치·킬·레벨 등이 전부 "성장 격차"라는 하나의 이야기를 다르게 재고 있어서,
컬럼을 늘려도 같은 정보가 반복될 뿐이다. 그래서 튜닝도 하지 않았다 — 짜낼 게 없다.

**Q. 왜 화면을 Flask로 바꿨나**
계획(Vue/Express)대로면 예측 계산이 파이썬과 자바스크립트 두 군데에 생긴다.
화면 확률과 모델 확률이 달라져도 모르는 구조다. Flask는 화면도 파이썬이라
예측 파일을 그대로 불러 쓴다. 계산이 한 곳뿐이면 어긋날 수가 없다.

**Q. 왜 점수를 정확도로 재나**
승패가 정확히 반반(50.1 : 49.9)이고, 어느 쪽으로 틀려도 손해가 같아서다.
만약 한쪽으로 치우쳐 있었다면 정확도는 속기 쉬운 지표라 다른 것(F1)을 썼을 것이다.
치우쳤을 때의 계획도 미리 세워뒀지만 실측 결과 필요 없었다.

**Q. 시험지를 정말 안 봤다고 어떻게 믿나**
모델과 재료를 고르는 모든 판단은 연습용 데이터의 교차검증으로만 했다.
시험지는 마지막 채점과 "언제 틀리나" 분석에만 썼다. 그리고 채점 한 번의 값(0.7394)만
믿지 않고, 데이터를 10가지로 다시 나눠 10번 재학습한 범위(0.7366 ± 0.0081)를 함께 보고한다.

**Q. 킬이 중요하지 않다는 게 말이 되나**
킬만 보면 승패를 잘 가른다(13개 중 3위). 그런데 킬을 하면 돈을 받아서,
킬의 가치가 이미 돈 차이 안에 들어가 있다(둘의 상관 0.92).
돈을 이미 아는 모델에게 킬은 새 정보가 없다.
"킬은 돈으로 바뀌었을 때만 의미가 있다"가 정확한 해석이다.

**Q. 경기 유형은 왜 4가지인가**
지표(실루엣 점수)는 몇 개가 좋은지 정해주지 못했다 — 후보들 점수가 다 비슷했다.
4개일 때 운영전·난타전·일방적·시야전이라는 설명이 성립해서 사람이 골랐다.
자연스러운 경계를 발견한 게 아니라 설명을 위한 구분이라는 점을 한계로 밝힌다.

**Q. 15분 비교는 왜 프로 경기 데이터인가**
팀 DB의 랭크 데이터에는 15분 기록이 없다. 프로 경기 공개 데이터에는 10분·15분이
같이 있어서 이걸 썼다. 대신 실력대가 달라서 랭크 결과와 절대 수치를 섞지 않고,
10분과 15분끼리만 비교했다. 남은 문제 하나 — 같은 팀의 경기가 연습용과 시험용에
섞여 있어 점수가 실제보다 좋게 나왔을 수 있다. 두 시점을 비교한 결론은 영향받지 않는다.

**Q. 이 결과를 다른 시즌에도 쓸 수 있나**
못 쓴다. 데이터를 모은 시점의 게임 버전에 한정된 결론이다.
게임이 바뀌면 같은 절차로 다시 학습하면 된다 — 그래서 절차를 남기는 데 공을 들였다.

# 바로 실행하기 (quickstart)

## 준비

```bash
pip install -r requirements.txt      # Python 3.11 기준 고정 버전 (모델이 scikit-learn 1.9.0 저장본)
```

데이터 2개(Kaggle 10분 스냅샷 · Oracle's Elixir 프로 경기)는 용량·라이선스 때문에 저장소에 없다.
`data/README.md`의 링크에서 받아 `data/`에 넣는다. **서비스만 켤 때는 데이터·DB 둘 다 필요 없다** (`artifacts/model.joblib`만 있으면 된다).

**DB는 선택이다.** 접속 정보가 없으면 자동으로 로컬 CSV를 쓴다(계산식 동일).
DB를 쓰려면 비밀번호를 **환경변수로만** 준다 — 문서·코드에 적지 않는다.

```powershell
$env:DB_PASSWORD = '<비밀번호>'        # Windows PowerShell
```
```bash
export DB_PASSWORD='<비밀번호>'         # macOS / Linux  (또는 .env 파일 — 커밋 금지)
```

## 웹 서비스 (팀 서버 · 포트 F9504 / B9524 · https://p4.sumzip.com)

```bash
python3.11 -m venv venv311 && venv311/bin/pip install -r requirements.txt   # 처음 한 번 (Python 3.11 필수)
./check_project.sh start      # 백엔드 9524 + 프런트 9504 기동
./check_project.sh status     # pid · 포트 · health · 공개 도메인(https://p4.sumzip.com) 확인
./check_project.sh test       # 서빙 파리티(6건) + API 스모크(11건)
./check_project.sh logs       # logs/backend.log · logs/frontend.log
./check_project.sh restart    # 코드·모델을 바꾼 뒤
./check_project.sh stop
```

- 공개 주소 **https://p4.sumzip.com** → 수업 서버 프록시 → 이 서버의 프런트 9504. 프런트가 `/api/*`를 백엔드 9524로 중계하므로 화면 JS는 상대경로만 쓴다.
- 포트·도메인을 바꾸려면 환경변수: `FRONTEND_PORT=… BACKEND_PORT=… DOMAIN=… ./check_project.sh start`
- 화면에서 예시 버튼 3개 중 하나를 누르면 바로 결과가 나온다. "서버 리포트"를 펼치면 성적표·승리요인·경기 유형이 보인다.
- 백엔드 API: `GET /api/health · /api/schema · /api/examples · /api/report · /api/match-types` · `POST /api/predict · /api/predict/batch · /api/summoner`

## DB 처음 세팅 (선택 · 한 번만)

```bash
python db/load_mysql.py <user> <pw>              # 원본 적재 (9,879판 × 40컬럼)
python db/load_split.py <user> <pw>              # 연습/시험 분할 고정
mysql -h <host> -P <port> -u <user> -p <db> < db/create_ml_views.sql   # 피처 뷰 4종
python db/build_analysis_table.py <user> <pw>    # 경기 유형 테이블
python src/load_from_db.py                       # 뷰 연결 확인
```

## 전체 재현 (위에서부터 순서대로)

```bash
python src/day1_baseline.py          # 데이터 확인 · 나누기 · 찍기 0.5009
python src/day2_features_cluster.py  # 중복 정리 · 차이값 13개 · PCA · 경기 유형
python src/day2b_game_types.py       # 유형 4가지 정리
python src/finalize_model.py         # 최종 학습 · 채점 0.7394 · 이유·오류 분석 · 모델 저장
python src/timepoint_compare.py      # 10분 vs 15분 실험 (+5.25%p)
python src/repeat_check.py           # 시드 10번 반복 검증 (0.7366 ± 0.0081)
python src/factcheck.py              # 문서 숫자 자동 점검 (0건이어야 정상)
```

또는 `notebooks/final_analysis.ipynb` 하나를 처음부터 끝까지 실행해도 같다(무오류 실행 검증됨).
그림·EDA는 `notebooks/eda_visualization.ipynb` · `notebooks/visualizations.ipynb`.

## 예측 써보기 (서버 없이)

```bash
python predict.py --demo             # 예시 3건: 접전 51.2% / 파랑 우세 94.6% / 빨강 우세 16.8%
```

## 자주 걸리는 것

- **Python 3.9로는 안 된다** — `artifacts/model.joblib`이 scikit-learn 1.9.0에서 저장돼 예측 시 오류. `venv311`을 쓸 것
- 포트가 사용 중이면 `check_project.sh start`가 어떤 pid가 쓰는지 알려준다 — `./check_project.sh stop`으로 잔여 프로세스까지 정리
- 학습에는 `_train` 뷰만 쓴다. `_test`는 최종 평가 때 한 번만 — 미리 보면 점수가 가짜로 오른다
- 피처 계산식은 SQL 뷰에만 있다. 파이썬에 같은 식을 만들지 말 것
- 같은 시드여도 **행 순서가 다르면 분할이 달라진다** — DB든 CSV든 `gameId`로 정렬한 뒤 나눈다
- 라이엇 복기 기능은 개발 키가 필요하다 — `.env`에 `RIOT_API_KEY=RGAPI-...`를 넣고 `restart` (24시간마다 갱신)
