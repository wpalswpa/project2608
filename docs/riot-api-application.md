<!-- ─────────────────────────────────────────────
  Riot Developer Portal 의 Personal API Key 신청서에 붙여넣을 내용.
  왜 필요한가: 개발용 키는 24시간마다 죽어 시연·수집이 계속 끊긴다.
  Personal Key 를 받으면 만료가 없어진다. 심사에서 가장 흔한 탈락 사유가
  "설명이 부실함" 이라, 호출하는 엔드포인트와 용도를 코드와 일치시켜 적었다.
  주로 보는 사람: 신청서를 제출하는 사람 (이제민)
  ───────────────────────────────────────────── -->

# Riot Personal API Key 신청서 — 붙여넣을 내용

제출처: https://developer.riotgames.com → **Register Product** → Personal App

> 심사는 영어로 진행되므로 **영문으로 제출**한다. 각 항목 아래에 한국어 뜻을 달아
> 무엇을 제출하는지 알 수 있게 했다.

---

## Product Name

```
LOL.EX
```

## Product Game Focus

```
League of Legends
```

## Product URL

```
https://p4.sumzip.com
```

> ⚠️ **제출 전에 반드시 배포할 것.** 심사관이 이 주소를 열어 본다.
> **2026-09-02 실측한 라이브 상태 — 지금 제출하면 불리하다:**
>
> | 확인 | 결과 |
> |---|---|
> | `/api/matches` | 200 ✅ (경기 복기는 동작) |
> | `/api/coach` | **404** ❌ (감독 기능 미배포) |
> | `/api/health` 의 `riot_ready` | **true** — 그런데 실제 소환사 조회는 "키가 만료됐습니다" 오류 |
>
> 즉 **화면이 "소환사 검색"을 권하는데 누르면 실패한다.** 심사관이 이걸 먼저 눌러 볼
> 가능성이 높다. 서버가 `key_works()` 이전 버전이라 죽은 키를 걸러내지 못하는 상태다.
>
> **`./check_project.sh deploy` 로 최신(27d3438 이상)을 올리면** 죽은 키가 자동으로
> 걸러져 화면이 "경기 번호로 찾기"만 권하고, 심사관이 눌러 보는 모든 것이 동작한다.

## Product Group

> 이건 내가 정해줄 수 없다. 포털에서 본인 계정의 그룹 목록을 보고 고른다.
> Default Group 이외의 그룹이 없으면 그대로 두면 된다.

## Product Description

**아래 블록 전체를 붙여넣는다.**

```
LOL.EX is a non-commercial, educational post-game analysis tool built by a four-person
student team in a Korean MLOps bootcamp. It answers a question that existing stats sites
do not: not "what happened in this game", but "WHEN was this game decided".

WHAT IT DOES

We trained a logistic regression model on a public dataset of 9,879 ranked games
(Kaggle "League of Legends Diamond Ranked Games 10min"), using only the game state at
the 10-minute mark: gold difference, experience difference, kill/assist difference,
CS difference, jungle CS difference, wards placed/destroyed, dragons, heralds, towers,
average level difference, and first blood. The model reaches 73.9% holdout accuracy
(0.7366 +- 0.0081 across 10 re-splits) versus a 50.1% coin-flip baseline.

Because the model is linear, every prediction can be decomposed into the contribution of
each individual statistic. This is the core of the product: we do not just show a
probability, we show WHY.

We use this model to give a player three things about their own recent ranked games:

1. VERDICT. We cross the 10-minute win probability with the actual result, producing four
   categories: "snowballed" (ahead at 10 min, won), "comeback win" (behind, won),
   "early collapse" (behind, lost), and "threw the lead" (ahead at 10 min, lost).
   The prescription for each is completely different - "early collapse" means the player
   needs to fix laning, while "threw the lead" means they need to learn to close out games.
   Existing stats sites cannot separate these two, because doing so requires a model of the
   10-minute game state.

2. CAUSE. For each game we show which statistics moved the prediction and by how much,
   derived directly from the model's standardized coefficients.

3. COACHING. We run the model backwards to answer "what if". For example: "your win
   probability at 10 minutes was 43%; with 20 more CS it would have been 53%, with one
   more dragon 60%." Players see which improvement is worth the most, ranked by impact.

WHICH APIS WE USE AND WHY

- ACCOUNT-V1 (/riot/account/v1/accounts/by-riot-id/{gameName}/{tagLine})
  To resolve the Riot ID a user types into a PUUID. This is the entry point of the product.

- MATCH-V5 (/lol/match/v5/matches/by-puuid/{puuid}/ids?queue=420)
  To list the player's recent ranked solo queue matches. We filter to queue 420 only,
  because our model was trained on ranked solo queue data and would not be valid elsewhere.

- MATCH-V5 (/lol/match/v5/matches/{matchId})
  For the final result, the player's champion, their team side, and game duration. We skip
  games shorter than 11 minutes, since a 10-minute snapshot of a surrendered game is not
  meaningful.

- MATCH-V5 (/lol/match/v5/matches/{matchId}/timeline)
  This is essential and cannot be substituted. Our model needs the game state at exactly
  10 minutes, and the timeline is the only source of per-frame gold, experience, level,
  CS and jungle CS, plus the events (kills, wards, dragons, heralds, towers) before the
  600,000 ms mark. We aggregate these into the same 13 team-difference features the model
  was trained on.

- LOL-STATUS-V4 (/lol/status/v4/platform-data)
  A single lightweight call at server startup to verify that our API key is still valid.
  Development keys expire every 24 hours, and we would rather disable the feature in our
  UI than show users a button that fails.

- LEAGUE-V4 (planned, not yet implemented)
  If approved, we would like to sample Challenger/Grandmaster/Master players to compute
  per-champion "lead conversion rate" - how often a champion converts a 10-minute lead
  into a win versus throwing it. This is a statistic that only our verdict model can
  produce, and it would be aggregate-only, never tied to an individual player.

HOW WE RESPECT THE RATE LIMITS

All calls go through a single wrapper function that honours the Retry-After header on
HTTP 429 and backs off before retrying. A user request analyses at most 5 recent matches,
which is roughly 12 calls. If we implement the champion aggregation above, it will run as
an offline batch job that is resumable, appends results incrementally, and skips match IDs
it has already fetched, so that it stays well within limits and can survive interruptions.

DATA HANDLING

We do not create accounts, we do not store personal data, and we do not sell or share
anything. Riot IDs are used transiently to resolve a PUUID for the current request and are
not persisted. Match data is fetched on demand and not redistributed. The product carries
the required "isn't endorsed by Riot Games" legal notice on every page, and champion images
are loaded from the official Data Dragon CDN.

WHAT WE DO NOT DO

We do not offer betting, gambling, odds, or wagering of any kind, and we never predict
live or in-progress matches. Our analysis is strictly retrospective, applied to games that
have already finished. We are aware that live in-game state is not available through the
public API, and we have deliberately scoped the product to post-game review.

WHY WE NEED A PERSONAL KEY

The 24-hour expiry of development keys breaks the product for our users and our team every
single day, and it makes the multi-hour offline aggregation described above impossible to
complete. This is a student project and remains free and non-commercial.

The source code is open: https://github.com/wpalswpa/project2608
```

---

## 붙여넣기 전 확인 3가지

1. **서버를 최신으로 배포한다.** 심사관이 Product URL 을 연다. 지금 라이브는
   저장소보다 뒤처져 있다 — 맥 세션에 `./check_project.sh deploy` 를 요청할 것.
2. **저장소가 공개인지 본다.** 설명 마지막 줄에 GitHub 주소를 넣었다.
   비공개라면 그 줄을 지우거나 저장소를 공개로 바꾼다.
3. **LEAGUE-V4 문단** — 챔피언 집계를 안 할 생각이면 그 항목을 지운다.
   안 쓸 API 를 적으면 심사에서 되묻는다.

## 심사에서 떨어지는 흔한 이유

| 이유 | 이 신청서에서 어떻게 막았나 |
|---|---|
| 설명이 짧고 모호함 | 무엇을·왜·어떤 API 를·어떻게 쓰는지 항목별로 적었다 |
| 어떤 API 를 쓰는지 안 적음 | 엔드포인트 경로까지 코드와 일치시켜 적었다 |
| 도박·베팅 의심 | "하지 않는 것" 문단에서 명시적으로 부정했다 |
| 실시간 예측 주장 | 공개 API 로 불가능함을 알고 있으며 사후 복기로 한정했다고 적었다 |
| 개인정보 처리 불명확 | 저장하지 않고 재배포하지 않는다고 적었다 |
| URL 이 비어 있거나 안 열림 | 배포 후 제출하도록 위에 경고를 달았다 |
