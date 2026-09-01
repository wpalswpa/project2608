<style>
.speckit-viewer-inline, .speckit-viewer-inline h1, .speckit-viewer-inline h2, .speckit-viewer-inline h3, .speckit-viewer-inline h4, .speckit-viewer-inline p, .speckit-viewer-inline li, .speckit-viewer-inline td, .speckit-viewer-inline th, .speckit-viewer-inline strong, .speckit-viewer-inline em, .speckit-viewer-inline blockquote { color: #111111 !important; font-style: normal; }
.speckit-viewer-inline { background: #ffffff !important; }
.speckit-viewer-inline pre, .speckit-viewer-inline pre * { color: #e2e8f0 !important; }
</style>

# 작업 목록 (tasks)

실제로 만든 파일과 각각의 역할. 전부 완료됐고, 위에서부터 순서대로 실행하면 재현된다.

## 학습 파이프라인

- [x] **src/day1_baseline.py** — 데이터 확인(빈칸·중복·승패비율) · 연습/시험 나누고 봉인 · 찍기 점수 0.5009
- [x] **src/day2_features_cluster.py** — 중복 11개 정리 · 차이값 13개로 압축 · 경기 성격별 묶기
- [x] **src/day2b_game_types.py** — 경기 유형 4가지 정리 (운영전 42 · 난타전 32 · 일방적 19 · 시야전 7%)
- [x] **src/finalize_model.py** — 최종 학습 · 봉인 시험지 개봉(0.7394) · 이유 분석 · 오류 정리 · 모델 저장+복원 검증
- [x] **src/timepoint_compare.py** — 10분 vs 15분 실험 (프로 경기 10,656판, +5.25%p)
- [x] **src/repeat_check.py** — 데이터를 10가지로 다시 나눠 10번 재학습 (0.7366 ± 0.0081)

## 서비스

- [x] **predict.py** — 예측 담당 단 하나의 파일. 확률 + 이유 상위 5 + 경고 반환
- [x] **web/app.py** — Flask 화면 서버. 예측하지 않고 predict.py 결과를 전달만
- [x] **web/templates/index.html** — 입력 폼 · 승률 막대 · 이유 · 경고
- [x] **web/test_parity.py** — 화면 숫자 == 모델 숫자 자동 대조 (3건 소수점까지 일치)
- [x] **src/riot_api.py** — 라이엇에서 끝난 경기 불러와 10분 시점 복기

## 실수를 막는 장치

- [x] **src/paths.py** — 어느 폴더에서 실행해도 경로가 안 꼬이게
- [x] **src/runlog.py** — 실험 기록 파일 형식을 한 곳에서만 정의
- [x] **src/factcheck.py** — 문서 숫자와 실제 결과가 다르면 잡아냄 (현재 0건)

## 제출물 6종

- [x] **README.md** — 전체 이야기
- [x] **notebooks/final_analysis.ipynb** — 처음부터 끝까지 오류 없이 도는 재현 코드
- [x] **artifacts/model.joblib** — 전처리 포함 모델 (복원 후 예측 일치 확인)
- [x] **artifacts/schema.json** — 입력 13개의 이름·형식·허용 범위
- [x] **model_card.md** — 사용설명서 + 쓰면 안 되는 상황 6가지
- [x] **requirements.txt** — 패키지 버전 고정

## 아직 안 한 것

- [ ] 게임 모르는 사람에게 순위표만 보여주고 관전 포인트를 말할 수 있는지 확인 (1~2명)
- [ ] 팀 서버 배포 (지금은 로컬 데모)
- [ ] 경기 유형 그림(viz_3) 라벨이 뒤섞인 버그 수정

## 계획에서 빠진 작업

Vue/Express 관련 작업 전부(화면 뼈대 만들기, 자바스크립트로 계산 다시 만들기, 별도 대조 프로그램).
Flask 전환으로 필요 자체가 없어졌다.
