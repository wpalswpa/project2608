[작업 분해 — 완료 A1~A9]
A1 문제 번역·첫점검·EDA — 이진분류·정확도 확정, 중복 11개 목록 ✅
A2 층화 분할 8:2·봉인·베이스라인 — 찍기 0.5009 ✅
A3 차이 피처 13개 — CV 0.7334 → 0.7369 ✅
A4 모델 8종 비교 → 로지스틱 — 정확도 1위 + 과적합 기준 통과 ✅
A5 검증 (5-fold·임계값·시드 10회) — std<0.02, 10/10회 통과 ✅
A6 홀드아웃 평가·해석·오류 분석 — 0.7394, 요인 3개 두 방법 일치 ✅
A7 실험 B (10 vs 15분 통제 비교) — +5.25%p, 접전만 +7.8%p ✅
A8 산출물 6종 + 웹 데모 + 발표자료 — 복원 assert·패리티 3건·PPT 24장 ✅
A9 문서 정리·factcheck·GitHub 업로드 — 0건·main 푸시 ✅

[실행 순서와 의존]
T01~T05 DB 적재·분할·뷰·로더 (선택, CSV 폴백 가능)
→ T10 day1 → T11 day2 → T12 day2b · T13 finalize (T12∥T13)
→ T14 timepoint [P] (별도 데이터, T10 이후) · T15 repeat_check [P] (T13 이후)
→ T20 predict.py → T21 web/app.py [P] · T22 templates [P] · T24 riot_api [P] → T23 test_parity
→ T30~T32 paths·runlog·factcheck [P] · T40~T45 산출물 6종 [P]

[남은 작업 B1~B4]
B1 게임 모르는 사람 스모크 테스트 (SC-7) — 순위표만 보고 관전 포인트를 말하는지 1~2명 ⬜
B2 viz_3_game_types.png 라벨 수정 — 군집 이름-수치 매핑 교정 후 재생성 ⬜
B3 발표 리허설 — presentation_draft.pptx 발표자 노트로 1회 ⬜
B4 팀 서버 배포 — 팀 결정 시 (Flask debug 끄고 WSGI) ⬜

[후속 아이디어 C1~C8 (미확정)]
Oracle's Elixir 20·25분 컬럼 확인 → 실험 B 팀 그룹 분할 재실행 → Riot 타임라인 수집 → 시점별 로지스틱 랭크(M0) → 경과 시간 통합 모델(M1) → 단조 제약 부스팅(M2) → 확률 보정(M3) → 시점별 승리요인 리포트
