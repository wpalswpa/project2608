-- =====================================================================
-- 피처셋별 학습용 데이터 뷰
--
-- ※ '모델별'이 아니다. 예측 모델은 로지스틱 회귀 하나뿐이고,
--   아래 뷰들은 그 하나의 모델에 넣을 '재료 묶음'을 바꿔 놓은 것이다.
--   (예외: cluster5 는 예측이 아니라 KMeans 군집용)
--
-- 실행:  mysql -h <서버주소> -P <포트> -u <사용자명> -p <팀DB명> < db/create_ml_views.sql
-- 선행:  python db/load_split.py <user> <pw>   (ml_split 테이블이 먼저 있어야 함)
--
-- 왜 뷰로 만드나:
--   피처 조합을 SQL 한 곳에 고정해 두면, 파이썬·노트북·웹 어디서 읽든
--   같은 피처 정의를 쓴다. 피처 계산식이 여러 군데로 흩어지는 것을 막는다.
--
-- 이름 규칙:  v_<피처셋>_<train|test|all>
--   train = 학습용 7,903행  /  test = 봉인된 시험용 1,976행  /  all = 전체 9,879행
--
-- ⚠️ 학습에는 반드시 _train 뷰만 쓸 것. _test 는 최종 평가에서 딱 한 번만.
-- =====================================================================
--
-- 중복 제거 대상 11개 (9,879행 전수에서 등식 성립 확인)
--
--   1차 9개 — 두 컬럼끼리의 거울 관계
--     redFirstBlood      = 1 - blueFirstBlood        (첫 킬은 한 팀만 가능)
--     redGoldDiff        = -blueGoldDiff             (부호만 반대)
--     redExperienceDiff  = -blueExperienceDiff
--     redKills           = blueDeaths                (내 킬 = 상대 데스)
--     redDeaths          = blueKills
--     blueGoldPerMin     = blueTotalGold / 10        (10분 고정이라 상수배)
--     redGoldPerMin      = redTotalGold / 10
--     blueCSPerMin       = blueTotalMinionsKilled / 10
--     redCSPerMin        = redTotalMinionsKilled / 10
--
--   2차 2개 — 세 컬럼의 합 관계 (2026-08-31 추가 발견)
--     blueEliteMonsters  = blueDragons + blueHeralds
--     redEliteMonsters   = redDragons  + redHeralds
--       -> 1차 검사는 '두 컬럼끼리의 상관 ±1.0' 만 봤기 때문에 이 관계를 놓쳤다.
--          셋을 함께 넣으면 완전한 선형 종속이라 VIF 가 무한대가 되고,
--          세 컬럼의 계수가 유일하게 정해지지 않아 '해석'이 망가진다.
--          제거해도 성능은 그대로다: diff 0.7371 -> 0.7369, clean 0.7334 -> 0.7334.
--          합계 하나보다 구성요소 둘(드래곤·전령)이 해석에 유용하므로
--          EliteMonsters 쪽을 버리고 Dragons·Heralds 를 남긴다.
-- =====================================================================


-- ---------------------------------------------------------------------
-- 0. 기준 뷰 — 원본 + 분할 라벨
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW v_base AS
SELECT m.*, s.split
FROM lol_matches_10min m
JOIN ml_split s ON m.gameId = s.gameId;


-- ---------------------------------------------------------------------
-- 1. diff13 — 차이 피처 13개  ★ 현재 채택된 구성
--
--    아이디어: 게임의 본질은 격차 싸움(스노우볼)이므로
--    양 팀의 절대값보다 '차이'가 승패를 더 직접 표현한다.
--    장점: 피처 수가 절반, 해석이 "양수 = 블루 우세"로 단순해진다.
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW v_diff13_all AS
SELECT
    gameId,
    blueWins                                                    AS y,
    blueFirstBlood                                              AS FirstBlood,
    blueKills                    - redKills                     AS KillsDiff,
    blueGoldDiff                                                AS GoldDiff,
    blueExperienceDiff                                          AS ExpDiff,
    blueWardsPlaced              - redWardsPlaced               AS WardsPlacedDiff,
    blueWardsDestroyed           - redWardsDestroyed            AS WardsDestroyedDiff,
    blueAssists                  - redAssists                   AS AssistsDiff,
    blueDragons                  - redDragons                   AS DragonsDiff,
    blueHeralds                  - redHeralds                   AS HeraldsDiff,
    blueTowersDestroyed          - redTowersDestroyed           AS TowersDestroyedDiff,
    blueAvgLevel                 - redAvgLevel                  AS AvgLevelDiff,
    blueTotalMinionsKilled       - redTotalMinionsKilled        AS TotalMinionsKilledDiff,
    blueTotalJungleMinionsKilled - redTotalJungleMinionsKilled  AS TotalJungleMinionsKilledDiff,
    split
FROM v_base;
-- ※ EliteMonstersDiff 는 = DragonsDiff + HeraldsDiff 라 제외 (위 2차 중복 참고)

CREATE OR REPLACE VIEW v_diff13_train AS
SELECT * FROM v_diff13_all WHERE split = 'train';

CREATE OR REPLACE VIEW v_diff13_test AS
SELECT * FROM v_diff13_all WHERE split = 'test';


-- ---------------------------------------------------------------------
-- 2. clean27 — 중복 11개를 제거한 27피처 (차이 변환의 대조군)
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW v_clean27_all AS
SELECT
    gameId,
    blueWins AS y,
    -- 블루 16개
    blueWardsPlaced, blueWardsDestroyed, blueFirstBlood,
    blueKills, blueDeaths, blueAssists,
    blueDragons, blueHeralds, blueTowersDestroyed,
    blueTotalGold, blueAvgLevel, blueTotalExperience,
    blueTotalMinionsKilled, blueTotalJungleMinionsKilled,
    blueGoldDiff, blueExperienceDiff,
    -- 레드 11개
    redWardsPlaced, redWardsDestroyed, redAssists,
    redDragons, redHeralds, redTowersDestroyed,
    redTotalGold, redAvgLevel, redTotalExperience,
    redTotalMinionsKilled, redTotalJungleMinionsKilled,
    split
FROM v_base;

CREATE OR REPLACE VIEW v_clean27_train AS
SELECT * FROM v_clean27_all WHERE split = 'train';

CREATE OR REPLACE VIEW v_clean27_test AS
SELECT * FROM v_clean27_all WHERE split = 'test';


-- ---------------------------------------------------------------------
-- 3. gold2 — 골드차 + 경험치차 2개뿐
--
--    실측: 이 2개(0.7328)가 전체 피처(0.7303)를 이긴다.
--    "튜닝할 여지가 없다"의 근거이자, 최소 모델 비교용 기준.
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW v_gold2_all AS
SELECT
    gameId,
    blueWins           AS y,
    blueGoldDiff       AS GoldDiff,
    blueExperienceDiff AS ExpDiff,
    split
FROM v_base;

CREATE OR REPLACE VIEW v_gold2_train AS
SELECT * FROM v_gold2_all WHERE split = 'train';

CREATE OR REPLACE VIEW v_gold2_test AS
SELECT * FROM v_gold2_all WHERE split = 'test';


-- ---------------------------------------------------------------------
-- 4. cluster5 — 군집 분석용 사이드 중립 피처 5개
--
--    "누가 이기는지"를 지운 피처들. 승패 정보가 들어가면
--    군집이 정답을 그대로 재현해 버려 의미가 없어진다.
--    ※ 비지도 학습용이라 y 를 넣지 않는다.
--    ※ 오브젝트는 여기서 '양 팀 합' 하나로만 쓰므로 공선성 문제가 없다.
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW v_cluster5_all AS
SELECT
    gameId,
    ABS(blueGoldDiff)                                          AS 일방성_골드차,
    blueKills                    + redKills                    AS 난타전_총킬,
    blueDragons + blueHeralds    + redDragons + redHeralds     AS 오브젝트_총획득,
    blueWardsPlaced              + redWardsPlaced              AS 시야전_총와드,
    blueTotalMinionsKilled       + redTotalMinionsKilled       AS 성장_총CS,
    split
FROM v_base;

CREATE OR REPLACE VIEW v_cluster5_train AS
SELECT * FROM v_cluster5_all WHERE split = 'train';


-- ---------------------------------------------------------------------
-- 확인용 질의 (실행 후 눈으로 검증)
-- ---------------------------------------------------------------------
-- SELECT TABLE_NAME FROM information_schema.VIEWS
--  WHERE TABLE_SCHEMA = '<팀DB명>' ORDER BY TABLE_NAME;
--
-- SELECT split, COUNT(*) n, ROUND(AVG(y),4) 승률
--   FROM v_diff13_all GROUP BY split;
