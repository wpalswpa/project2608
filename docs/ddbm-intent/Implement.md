[구현 범위]
tasks 의도의 A1~A9를 전부 구현했다 (2026-09-01 완료). 코드는 GitHub `8wghw74rd2-coder/project2608`, 문서는 `specs/002-ml-prediction-service/`.

[무엇을 만들었나]
· 학습 파이프라인 6개 — src/day1_baseline → day2_features_cluster → day2b_game_types → finalize_model → timepoint_compare → repeat_check
· 예측 진입점 1개 — predict.py (확률 + 요인 상위 5 + 범위 밖 경고). 예측 로직은 이 파일 한 곳에만 있다
· 웹 데모 — Flask (web/app.py). 화면은 predict.py를 그대로 불러 보여주기만 한다. 화면 숫자 == 모델 숫자를 web/test_parity.py로 자동 대조 (3건 일치)
· 데이터 계층 — 팀 MariaDB에 피처 뷰 4종(v_diff13 · v_clean27 · v_gold2 · v_cluster5). 피처 계산식은 SQL 뷰 한 곳에만 두고 파이썬에 중복 구현하지 않는다. DB가 없으면 같은 계산식의 CSV 폴백
· 산출물 6종 — README · final_analysis.ipynb(무오류 실행) · model.joblib(복원 후 예측 일치 assert) · schema.json · predict.py · model_card.md(사용 금지 상황 6가지)
· 덤 — src/riot_api.py 로 끝난 경기 복기 (키는 환경변수 RIOT_API_KEY)

[구현 중 바뀐 것과 이유]
· 웹스택 Vue/Express → Flask (8/31). 예측 계산이 파이썬·자바스크립트 두 곳에 생기면 화면 확률과 모델 확률이 달라져도 아무도 모른다. Flask면 계산이 한 곳뿐이라 어긋날 수 없다. Docker 미사용, 네이티브 실행
· 피처 14개 → 13개. EliteMonstersDiff = DragonsDiff + HeraldsDiff 라 같은 정보가 두 번 들어가 제거 (점수 0.7371 → 0.7369, 차이 없음)
· 재현성 규약 7항목 → 8항목. 시드가 같아도 행 순서가 다르면 분할이 달라지는 걸 재실행 중 발견 → gameId 정렬 고정 추가

[구현 결과 — 실측]
· 홀드아웃 정확도 0.7394 (찍기 0.5010 대비 +23.8%p) · 교차검증 0.7315 ± 0.0153 · 시드 10회 0.7366 ± 0.0081 (10/10회 0.70 통과)
· F1 / AUC / Brier = 0.7352 / 0.8150 / 0.1756
· 승리요인 골드차 > 경험치차 > 드래곤 — 계수·permutation 두 방법 순위 일치, 10회 반복에서도 동일
· 오류 분석 — 접전(골드차 <1k, 34%) 0.615 ↔ 사실상 결정(4.2k+, 9%) 0.947. 73~74%는 모델이 아니라 10분 정보의 한계
· 실험 B (프로 경기, 10 vs 15분) — +5.25%p, 접전 구간만 +7.8%p, 벌어진 경기 ±0

[검증 장치]
· src/factcheck.py — 문서 숫자 ↔ 실제 결과 자동 대조 (현재 0건)
· web/test_parity.py — 화면 ↔ 모델 확률 일치
· model.joblib 저장 → 복원 → 예측 일치 assert
· notebooks/final_analysis.ipynb 클린 런타임 무오류 실행

[아직 안 한 것]
B1 viz_3 경기유형 그림 라벨 수정(완료) · B2 발표 리허설 · B3 팀 서버 배포(Flask debug 끄고 WSGI)
