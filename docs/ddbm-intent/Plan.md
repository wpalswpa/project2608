[기술 스택 — 확정]
· 언어 Python 3.11 (학습·예측·웹 단일 언어) · pandas · scikit-learn(Pipeline) · joblib · matplotlib · pymysql — 버전 고정
· 웹 Flask (계획의 Vue/Express에서 8/31 변경 — 예측 로직을 lolwin 한 곳에 두어 화면·모델 패리티 보장)
· 데이터 팀 MariaDB <팀DB명> — 피처 뷰 4종(v_diff13 · v_clean27 · v_gold2 · v_cluster5, 각 _train/_test/_all)이 피처 정의의 정본. CSV 폴백 동일 계산식
· 실행 Windows 네이티브 · 1코어(n_jobs=1) · Docker 미사용 · 브랜치 main 단일

[데이터베이스 설정]
· 접속 정보는 .env의 DB_PASSWORD 환경변수로만 (문서·코드에 평문 금지). 호스트·포트·계정은 .env.example 참조
· 학습에는 _train 뷰만. _test는 최종 평가 1회
· 분할 고정: 층화 8:2, 시드 42, gameId 정렬 (연습 7,903 / 시험 1,976)

[4일 단계]
Day1 문제 번역·첫점검·EDA·층화 분할·베이스라인(찍기 0.5009)
Day2 중복 11개 제거(27) → 차이 피처 13개 · PCA · 사이드 중립 군집 (CV 0.7334 → 0.7369)
Day3 모델 8종 비교 → 로지스틱 · 5-fold · 임계값 0.5 확인 · 튜닝 생략 근거(2피처=전체)
Day4 홀드아웃 1회 평가(0.7394) · 해석·오류 분석 · 아티팩트·문서
추가 실험 B(10 vs 15분) · 시드 10회 · 웹 데모 · 정렬 버그 수정

[헌법 — 어기면 안 되는 원칙 7]
1 분할이 전처리보다 먼저 2 전처리는 Pipeline 내부 3 기준선(찍기) 먼저 4 예측은 모델만(규칙 하드코딩·확률 수동 보정·외부 API 금지) 5 예측 로직은 lolwin 패키지 단일 지점(predict.py 는 호환 진입점) 6 재현성 규약 8항목(시드 42·분할 저장·절대경로 금지·버전 고정·순차 실행·Pipeline 전처리·runs.csv·gameId 정렬) 7 실험 A/B 절대 수치 비교 금지

[API 계약]
predict(payload: dict[13 diff 피처]) → {win_prob_blue, pred, top_factors[5], warnings[]}. Flask /predict 는 이 함수를 그대로 호출. 입력 범위·형식은 artifacts/schema.json
