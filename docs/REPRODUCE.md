<!-- ─────────────────────────────────────────────
  재현 명령어 · 폴더 구조 · 검증 방법 — 기계·개발자용.
  왜 필요한가: README 는 사람이 읽는 감독판 한 장이라 명령어 목록을 두지 않는다.
  직접 돌려볼 사람은 이 문서 하나로 처음부터 끝까지 재현할 수 있다.
  주로 보는 사람: 채점자·직접 재현하려는 사람 · Claude(검수)
  ───────────────────────────────────────────── -->

# 재현 방법 — 처음부터 끝까지

```bash
pip install -r requirements.txt          # Python 3.11 · scikit-learn 1.9.0

pip install -e .                         # 한 번만 — 노트북·다른 폴더에서 lolwin 을 쓰려면 (서비스 자체는 없어도 뜸)
python src/day1_baseline.py              # 데이터 확인 · 분할 · 찍기 점수 0.5009
python src/split_check.py                # 분할 진단 (겹침·층화·분포 4항목)
python src/day2_features_cluster.py      # 중복 정리 · 차이 지표 13개 · 군집
python src/day2b_game_types.py           # 경기 유형 4가지 — 산점도 + 프로파일
python src/finalize_model.py             # 최종 학습 · 채점 0.7394 · 모델 저장
python src/model_compare.py              # 모델 8종 비교 → model_comparison.csv (근거)
python src/model_choice_viz.py           # 위 CSV 로 그림 생성 (06_model_choice.png)
python src/feature_reduction.py          # 페이즈 2 — 히트맵 확인 후 골드 빼고 재학습
python src/phase2_pca.py                 # 페이즈 2 — PCA 가 골드 탓이었는지 확인
python src/supplement_checks.py          # 보충 — 나이브베이즈·군집 비교·차원 축소
python src/twostage_check.py             # 접전 보완 — 2단계 라우팅 검증 (기각 근거)
python src/collect_champion_stats.py     # 챔피언·라인 승률 수집 (Riot 키 필요 · 이어받기)
python src/collect_ranking.py            # 상위 1,000명 랭킹 수집 (Riot 키 필요 · 이어받기)
./run_collectors.sh loop                 # 두 수집기를 무인으로 계속 (Ctrl+C 로 중단)
python src/timepoint_compare.py          # 페이즈 3 — 10분 vs 15분
python src/repeat_check.py               # 분할을 10번 바꿔 재학습
python predict.py --demo                 # 예측 확인 (51.2% / 94.6% / 16.8%)
python src/factcheck.py                  # 문서 숫자 자동 점검 (0건이어야 정상)
./check_project.sh verify                # 위 검사 + 예측 회귀 · 서빙 계약 · 학습 재현성
```

데이터 CSV는 저작권·용량 때문에 저장소에 없습니다. `data/README.md`의 링크에서 받으세요.
DB 접속 정보가 없으면 자동으로 로컬 CSV를 씁니다(계산식 동일).

**재현성 규약 8항목** — 시드 42 · 분할 파일 저장 · 절대경로 금지 · 버전 고정 · 순차 실행 ·
전처리는 Pipeline 안 · 실험 기록 `runs.csv` · **행 정렬 고정(`gameId`)**

마지막 항목은 직접 겪고 추가했습니다. 시드를 고정해도 **읽는 순서가 다르면 분할이 달라집니다.**

*(왜 이런 일이 생기는지 → [../STUDY.md](../STUDY.md) **14번 재현성**)*

---

# 무엇이 어디에 있나

## 사람이 봐야 하는 것 — 이 네 개면 충분합니다

| 폴더·파일 | 역할 | 언제 보나 |
|---|---|---|
| **`README.md`** | 프로젝트 전체 이야기 (이 파일) | 처음 볼 때 · 발표 준비할 때 |
| **`STUDY.md`** | 개념 가이드 — "왜 이걸 하는데?"부터 시작 | 용어가 막힐 때 |
| **`reports/`** | **결과물이 모이는 곳.** 제출용 노트북 · 발표용 지표표 · 그림 | 제출·발표 자료가 필요할 때 |
| **`model_card.md`** | 모델 사용설명서와 **금지 상황** | 남에게 모델을 넘길 때 |

`reports/` 안에서 실제로 열어볼 것은 세 개입니다.

| 파일 | 무엇 |
|---|---|
| `model_report.ipynb` | **제출용** — 채택 모델 · 뷰·분할 상태 · 평가 결과 · 혼동행렬 |
| `metrics_summary.md` | **발표용** — 숫자와 근거 파일, 예상 질문 5개의 답 |
| `phase2_feature_reduction.md` | 페이즈 2 상세 (골드 제외 실험) |

나머지 `reports/figures/` `reports/tables/` 는 그림·표 원본 보관소라 **직접 열 일이 없습니다.**

## 나머지 — 기계가 검증하는 것들

한 줄씩만 알아두면 됩니다. 고칠 일이 생기면 검사가 잡아줍니다.

```
lolwin/        라이브러리 — 피처 정의·모델·예측이 여기 모여 있다 (정본)
predict.py     명령행 진입점 (실제 로직은 lolwin 안)
artifacts/     학습된 모델 파일 + 입력 규격
tests/         회귀·계약·재현성 검사
src/           분석 실험 스크립트 (페이즈 1·2·3 재현)
web/           프론트(9504) · 백엔드(9524)
notebooks/     전 과정 재현 노트북
docs/          기획·명세·계획·배포·서빙 계약
db/            DB 적재와 SQL 뷰
data/          원본 CSV(저장소에 없음) + 분할 인덱스 — 재현성 규약의 실물
specs/         팀 서버 정본 명세 (서버에서 git pull 로 갱신 — 편집 금지)
```

무엇을 고치든 이 한 줄이면 전부 확인됩니다.

```bash
./check_project.sh verify     # 예측 회귀 · 서빙 계약 · 학습 재현성 · 문서 수치
```

**산출물 6종** — README · 재현 노트북 · `model.joblib` · `schema.json` · `predict.py` · `model_card.md`

---
