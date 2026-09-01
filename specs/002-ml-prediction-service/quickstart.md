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

## 웹 화면

```bash
python web/app.py                    # 켜기 → 브라우저에서 http://localhost:5000
python web/test_parity.py            # (다른 터미널에서) 화면 숫자 == 모델 숫자 검증
```

화면에서 예시 버튼 3개 중 하나를 누르면 바로 결과가 나온다. 끄려면 Ctrl+C.

## 자주 걸리는 것

- 5000번 포트가 사용 중이면 web/app.py 마지막 줄의 port를 5001로
- DB 없이도 된다 — 접속 정보가 없으면 자동으로 로컬 CSV를 쓴다 (계산식 동일)
- 라이엇 복기 기능은 개발 키가 필요하다 (환경변수 RIOT_API_KEY, 24시간마다 갱신)
