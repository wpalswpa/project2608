<style>
.speckit-viewer-inline, .speckit-viewer-inline h1, .speckit-viewer-inline h2, .speckit-viewer-inline h3, .speckit-viewer-inline h4, .speckit-viewer-inline p, .speckit-viewer-inline li, .speckit-viewer-inline td, .speckit-viewer-inline th, .speckit-viewer-inline strong, .speckit-viewer-inline em, .speckit-viewer-inline blockquote { color: #111111 !important; font-style: normal; }
.speckit-viewer-inline { background: #ffffff !important; }
.speckit-viewer-inline pre, .speckit-viewer-inline pre * { color: #e2e8f0 !important; }
</style>

# 데이터는 어떻게 생겼나 (data-model)

## 전체 흐름

```
원본 한 줄(경기 1판, 40컬럼)
  → 중복 정리 후 "파랑 − 빨강" 차이값 13개
    → 모델(전처리 + 로지스틱, 파일 하나로 저장)
      → 답: 확률 · 예측 · 이유 · 경고
```

## 모델에 넣는 숫자 13개

전부 "파란 팀 값 − 빨간 팀 값"이다. **양수면 파란 팀이 앞선다**는 뜻.

| 이름 | 뜻 | 중요도 |
|---|---|---|
| GoldDiff | 돈 차이 | ★ 1위 |
| ExpDiff | 경험치 차이 | ★ 2위 |
| DragonsDiff | 드래곤 차이 | ★ 3위 |
| KillsDiff | 킬 차이 | 돈에 이미 반영됨 |
| AssistsDiff | 어시스트 차이 | 낮음 |
| AvgLevelDiff | 평균 레벨 차이 | 경험치와 거의 같은 정보 |
| TotalMinionsKilledDiff | 미니언 처치 차이 | 낮음 |
| TotalJungleMinionsKilledDiff | 정글 몬스터 차이 | 낮음 |
| HeraldsDiff | 전령 차이 | 낮음 |
| TowersDestroyedDiff | 타워 차이 (10분엔 거의 0) | 낮음 |
| WardsPlacedDiff | 와드 설치 차이 | 거의 무의미 (발견!) |
| WardsDestroyedDiff | 와드 제거 차이 | 낮음 |
| FirstBlood | 첫 킬을 파랑이 했나 (0/1) | 낮음 |

※ 원래 14개였는데, 엘리트몬스터 = 드래곤 + 전령이라 같은 정보가 두 번 들어가서 뺐다.

## 저장되는 파일

| 파일 | 내용 |
|---|---|
| artifacts/model.joblib | 전처리+모델 한 덩어리. 다시 불러도 같은 답이 나오는지 자동 확인 |
| artifacts/schema.json | 입력 13개의 이름·형식·허용 범위. 범위 밖 입력이면 경고의 근거 |
| data/splits/ | 연습/시험을 어떻게 나눴는지 기록 (누가 돌려도 같은 시험지) |
| runs.csv | 실험 기록 |

## 답의 형태 (predict.py가 돌려주는 것)

| 항목 | 예 |
|---|---|
| win_prob_blue | 0.732 (파란 팀 승률 73.2%) |
| pred | 1 (파랑 승 예측) / 0 (빨강 승 예측) |
| top_factors | 이 판을 움직인 요인 상위 5개 (어느 팀에 유리했는지 포함) |
| warnings | "학습 범위 밖 입력" 등 — 비어 있으면 안심 |
