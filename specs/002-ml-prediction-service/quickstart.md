<style>
.speckit-viewer-inline, .speckit-viewer-inline h1, .speckit-viewer-inline h2, .speckit-viewer-inline h3, .speckit-viewer-inline h4, .speckit-viewer-inline p, .speckit-viewer-inline li, .speckit-viewer-inline td, .speckit-viewer-inline th, .speckit-viewer-inline strong, .speckit-viewer-inline em, .speckit-viewer-inline blockquote { color: #111111 !important; font-style: normal; }
.speckit-viewer-inline { background: #ffffff !important; }
.speckit-viewer-inline pre, .speckit-viewer-inline pre * { color: #e2e8f0 !important; }
</style>

# 바로 실행하기 (quickstart)

## 준비

```bash
pip install -r requirements.txt
```

데이터 2개는 용량·저작권 때문에 저장소에 없다. data/README.md 의 링크에서 받아 data/ 에 넣는다.

## 전체 재현 (위에서부터 순서대로)

```bash
python src/day1_baseline.py          # 데이터 확인 · 나누기 · 찍기 0.5009
python src/day2_features_cluster.py  # 중복 정리 · 차이값 13개 · 경기 유형
python src/day2b_game_types.py       # 유형 4가지 정리
python src/finalize_model.py         # 최종 학습 · 채점 0.7394 · 모델 저장
python src/timepoint_compare.py      # 10분 vs 15분 실험 (+5.25%p)
python src/repeat_check.py           # 10번 반복 검증 (0.7366 ± 0.0081)
python src/factcheck.py              # 문서 숫자 자동 점검 (0건이어야 정상)
```

또는 notebooks/final_analysis.ipynb 하나를 처음부터 끝까지 실행해도 같다.

## 예측 써보기

```bash
python predict.py --demo             # 예시 3건: 접전 51.2% / 파랑 우세 94.6% / 빨강 우세 16.8%
```

## 웹 서비스 (팀 서버 · 포트 F9504 / B9524 · p4.sumzip.com)

```bash
python3.11 -m venv venv311 && venv311/bin/pip install -r requirements.txt   # 처음 한 번 (Python 3.11 필수)
./check_project.sh start      # 백엔드 9524 + 프런트 9504 기동
./check_project.sh status     # pid · 포트 · health · 공개 도메인(https://p4.sumzip.com) 확인
./check_project.sh test       # 서빙 파리티(6건) + API 스모크(11건)
./check_project.sh logs       # logs/backend.log · logs/frontend.log
./check_project.sh restart    # 코드·모델을 바꾼 뒤
./check_project.sh stop
```

- 공개 주소 **https://p4.sumzip.com** → 수업 서버 프록시 → 이 서버의 프런트 9504. 프런트가 `/api/*` 를 백엔드 9524 로 중계하므로 화면 JS 는 상대경로만 쓴다.
- 포트·도메인을 바꾸려면 환경변수: `FRONTEND_PORT=… BACKEND_PORT=… DOMAIN=… ./check_project.sh start`
- 화면에서 예시 버튼 3개 중 하나를 누르면 바로 결과가 나온다. 아래 "서버 리포트" 를 펼치면 성적표·승리요인·경기 유형이 보인다.

## 자주 걸리는 것

- 5000번 포트가 사용 중이면 web/app.py 마지막 줄의 port를 5001로
- DB 없이도 된다 — 접속 정보가 없으면 자동으로 로컬 CSV를 쓴다 (계산식 동일)
- 라이엇 복기 기능은 개발 키가 필요하다 (환경변수 RIOT_API_KEY, 24시간마다 갱신)
