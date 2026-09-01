<style>
.speckit-viewer-inline, .speckit-viewer-inline h1, .speckit-viewer-inline h2, .speckit-viewer-inline h3, .speckit-viewer-inline h4, .speckit-viewer-inline p, .speckit-viewer-inline li, .speckit-viewer-inline td, .speckit-viewer-inline th, .speckit-viewer-inline strong, .speckit-viewer-inline em, .speckit-viewer-inline blockquote { color: #111111 !important; font-style: normal; }
.speckit-viewer-inline { background: #ffffff !important; }
.speckit-viewer-inline pre, .speckit-viewer-inline pre * { color: #e2e8f0 !important; }
</style>

# 무엇을 만들었나 (spec)

**LoL 경기 10분 시점의 상황을 넣으면, ① 이길 확률 ② 왜 유리한지 ③ 믿어도 되는지를 돌려주는 서비스.**

2026-09-01 구현 완료. 이 문서는 팀원 누구나 읽을 수 있게 간결하게 정리한 판이며,
계획 단계의 상세 원본은 저장소 `specs/002-ml-prediction-service/_server_backup_2026-09-01/` 에 있다.

## 누가 쓰나

| 사용자 | 원하는 것 |
|---|---|
| 관전하는 사람 | 지금 어느 팀이 왜 유리한지 |
| 복기하는 유저 | 진 경기에서 뭐부터 고칠지 |
| 팀원·후속 개발자 | 그대로 다시 실행해서 같은 결과를 얻는 것 |

## 만든 기능

| 기능 | 내용 | 상태 |
|---|---|---|
| 승률 예측 | 13개 숫자를 넣으면 "파란 팀이 이길 확률 73%" | ✅ |
| 이유 설명 | 이 판을 움직인 요인 순위 (돈 차이 1위, 경험치 2위...) | ✅ |
| 경고 | 팽팽한 경기라 잘 틀림 / 학습 범위 밖 입력임 | ✅ |
| 웹 화면 | 입력 폼 → 승률 막대 + 이유 + 경고 한 화면 | ✅ |
| 시점 바꾸기 | 10분 대신 15분 데이터로도 같은 코드로 재학습 가능 | ✅ |
| 10분 vs 15분 비교 | 5분을 더 보면 얼마나 좋아지나 (프로 경기로 실험) | ✅ |
| 경기 유형 분류 | 운영전·난타전·일방적·시야전 4가지 | ✅ |
| 내 경기 복기 | 라이엇에서 끝난 경기를 불러와 10분 시점 승률 계산 | ✅ (덤) |

## 지킨 규칙

- **예측은 전부 학습된 모델이 한다.** "돈 차이 크면 승리" 같은 규칙을 사람이 써넣지 않는다.
  넣는 순간 "데이터가 검증했다"는 말이 거짓이 되기 때문이다.
- **시험지 봉인.** 데이터를 연습용 7,903판 / 시험용 1,976판으로 먼저 나누고,
  시험용은 마지막 채점 때 딱 한 번만 열었다. 미리 보면 점수가 가짜로 오른다.
- **화면은 보여주기만.** 웹은 예측 파일(predict.py)을 그대로 불러 쓴다.
  계산이 한 곳에만 있어서 화면 숫자와 모델 숫자가 어긋날 수 없고, 자동 대조 테스트도 있다.
- **저장한 모델은 복원 검증.** 파일로 저장한 모델을 다시 불러왔을 때
  똑같은 답이 나오는지 자동으로 확인한다.

## 채점표 (성공 기준)

| 기준 | 목표 | 결과 |
|---|---|---|
| 정확도 | 0.70 이상 | ✅ **0.7394** (찍기 0.50 대비 +24점) |
| 점수가 흔들리지 않을 것 | 편차 0.02 미만 | ✅ 0.0153 |
| 외우지 않았을 것 | 연습-검증 격차 0.03 미만 | ✅ +0.0022 |
| 이유가 방법을 바꿔도 같을 것 | 두 방법 일치 | ✅ 돈 > 경험치 > 드래곤, 완전 일치 |
| 언제 틀리는지 말할 수 있을 것 | 수치로 제시 | ✅ 팽팽 0.615 ↔ 결정 0.947 |
| 제출물 6종 | 전부 검증 | ✅ 6/6 |
| 게임 모르는 사람 테스트 | 1~2명 | ⬜ 아직 |

## 하지 않는 것

진행 중 경기의 실시간 연동(라이엇이 데이터를 안 줌) · 개인 실력 평가 · 베팅 등 상업적 이용

# 작업 목록 (tasks)

실제로 만든 파일과 역할. **전부 완료**됐고, 번호 순서로 실행하면 재현된다.
`← Txx` = 그 작업이 먼저 끝나야 함 · `[P]` = 같은 묶음 안에서 서로 병렬 가능.

## 0. 데이터 계층 (선택 — DB가 없으면 CSV 폴백으로 건너뛴다)

- [x] **T01** `db/load_mysql.py` — 원본 CSV를 DB에 적재 (9,879판 × 40컬럼)
- [x] **T02** `db/load_split.py` — 연습/시험 분할 고정 ← T01
- [x] **T03** `db/create_ml_views.sql` — 피처 뷰 4종 생성 (`v_diff13` `v_clean27` `v_gold2` `v_cluster5`) ← T02
- [x] **T04** `db/build_analysis_table.py` — 경기 유형 테이블 (`lol_analysis_10min.gameType`) ← T03
- [x] **T05** `src/load_from_db.py` — 뷰 로더. 접속 정보 없으면 같은 계산식의 CSV 사용 ← T03

## 1. 학습 파이프라인 (순차)

- [x] **T10** `src/day1_baseline.py` — 데이터 확인(빈칸·중복·승패비율) · 연습/시험 나누고 봉인 · 찍기 0.5009 ← T05
- [x] **T11** `src/day2_features_cluster.py` — 중복 11개 정리 · 차이값 13개 · PCA · 경기 성격별 묶기 ← T10
- [x] **T12** `src/day2b_game_types.py` — 경기 유형 4가지 (운영전 42 · 난타전 32 · 일방적 19 · 시야전 7%) ← T11
- [x] **T13** `src/finalize_model.py` — 최종 학습 · 시험지 개봉(0.7394) · 이유 분석 · 오류 정리 · 모델 저장 + 복원 검증 ← T11
- [x] **T14** `[P]` `src/timepoint_compare.py` — 10분 vs 15분 실험 (프로 경기 10,656판, +5.25%p) ← T10 (별도 데이터라 T13과 병렬)
- [x] **T15** `[P]` `src/repeat_check.py` — 분할부터 10번 재학습 (0.7366 ± 0.0081) ← T13

## 2. 서비스 ← T13

- [x] **T20** `predict.py` — 예측 담당 **단 하나의 파일**. 확률 + 이유 상위 5 + 범위 밖 경고 반환
- [x] **T21** `[P]` `web/app.py` — 백엔드 API 서버. 예측하지 않고 `predict.py` 결과를 전달만 ← T20
- [x] **T22** `[P]` `web/templates/index.html` — 입력 폼 · 승률 막대 · 이유 · 경고 · 서버 리포트 패널 ← T20
- [x] **T23** `web/test_parity.py` — 화면 숫자 == 모델 숫자 자동 대조 (백엔드·프런트 두 경로, 6건 일치) ← T21
- [x] **T24** `[P]` `src/riot_api.py` — 라이엇에서 끝난 경기 불러와 10분 시점 복기 (키는 환경변수) ← T20

## 3. 실수를 막는 장치 `[P]`

- [x] **T30** `src/paths.py` — 어느 폴더에서 실행해도 경로가 안 꼬이게
- [x] **T31** `src/runlog.py` — 실험 기록(`runs.csv`) 형식을 한 곳에서만 정의
- [x] **T32** `src/factcheck.py` — 문서 숫자와 실제 결과가 다르면 잡아냄 (현재 0건) ← 문서 전부

## 4. 제출물 6종 `[P]` ← T13

- [x] **T40** `README.md` — 전체 이야기
- [x] **T41** `notebooks/final_analysis.ipynb` — 처음부터 끝까지 오류 없이 도는 재현 코드
- [x] **T42** `artifacts/model.joblib` — 전처리 포함 모델 (복원 후 예측 일치 확인)
- [x] **T43** `artifacts/schema.json` — 입력 13개의 이름·형식·허용 범위
- [x] **T44** `predict.py` — (T20과 동일 파일) 예측 진입점
- [x] **T45** `model_card.md` — 사용설명서 + 쓰면 안 되는 상황 6가지

그 외 함께 낸 것: `requirements.txt`(버전 고정) · `runs.csv` · `presentation_draft.pptx`(24장) ·
`docs/` 8종(planning · spec · plan · intent-task · experiment_report · data_analysis · study.md · study.pdf) ·
`notebooks/eda_visualization.ipynb` · `notebooks/visualizations.ipynb`

## 5. 팀 서버 배포 (2026-09-01, 팀 서버 = 맥 192.168.0.19) ← T20

- [x] **T50** `web/app.py` — 백엔드 API 서버, 포트 **B9524**, 0.0.0.0 바인드. `/api/health · schema · examples · predict · predict/batch · report · match-types · summoner`. 예측은 `predict.py` 를 그대로 import
- [x] **T51** `web/frontend.py` — 프런트 서버, 포트 **F9504**. 화면을 내려주고 `/api/*` 를 백엔드로 중계 (도메인 **p4.sumzip.com** → 여기). 예측 로직 0줄
- [x] **T52** `check_project.sh` — `start | stop | restart | status | logs | health | test`. pid 는 `run/`, 로그는 `logs/`, 파이썬은 `venv311`
- [x] **T53** `web/test_api.py` — 프런트 경유 전 엔드포인트 스모크 11건
- [x] **T54** `venv311/` — Python 3.11 + `requirements.txt` 고정 버전 (3.9 환경에선 sklearn 1.9.0 모델이 로드되지 않음) · 존재하지 않던 핀 `PyMySQL==2.2.8` → `1.2.0`
- [x] 검증 — `https://p4.sumzip.com/` 200 (중지 시 502로 매핑 확인) · 파리티 6/6 · 스모크 11/11 · restart/stop/start 사이클 (2026-09-01 14:16~14:20)

## 6. 아직 안 한 것

- [ ] **B1** 게임 모르는 사람에게 순위표만 보여주고 관전 포인트를 말할 수 있는지 확인 (1~2명, SC-7)
- [ ] **B2** 경기 유형 그림(`reports/viz_3_game_types.png`) 라벨이 뒤섞인 버그 수정 (`visualizations.ipynb`)
- [ ] **B3** 발표 리허설 (`presentation_draft.pptx` 발표자 노트로 1회)
- [x] **B4** 팀 서버 배포 — 완료 (5절). Flask 내장 서버 → WSGI(gunicorn) 전환은 선택

## 계획에서 빠진 작업

Vue/Express 관련 작업 전부(화면 뼈대, 자바스크립트로 계산 다시 만들기, 별도 대조 프로그램).
Flask 전환으로 필요 자체가 없어졌다.
