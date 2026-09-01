# 팀 협업 규칙 — 브랜치 하나(`main`), 포지션별 담당

저장소: `https://github.com/wpalswpa/project2608`

**브랜치 규칙 — 작업은 `team`, 제출은 `main`**

| 브랜치 | 용도 | 누가 올리나 |
|---|---|---|
| `team` | **4명이 공유하는 작업 브랜치.** 매일 여기에 pull/push | 전원 |
| `main` | 발표·제출용 스냅샷. 직접 커밋하지 않는다 | ②가 리허설 통과 후 `team` → `main` 으로 합침 |

clone 한 뒤 반드시 `git checkout team` 부터. 개인 브랜치는 만들지 않는다(브랜치가 늘면 합치는 사람만 고생한다).
팀 서버(맥)도 `team` 을 보고 있어서 `./check_project.sh deploy` 가 `team` 의 최신을 반영한다.
공개 서비스: **https://p4.sumzip.com** (팀 서버 내부망 맥, 프런트 9504 · 백엔드 9524)

## 최종 배치 — 4인 (2026-09-01 확정)

| 사람 | 맡는 것 | 손대는 파일 (서로 안 겹침) |
|---|---|---|
| **팀장(wpalswpa)** | **① 평가지표 + ④ 문서·정성검증** | `reports/` `runs.csv` `src/repeat_check.py` `src/factcheck.py` `docs/experiment_report.md` · `notebooks/visualizations.ipynb` `README.md` `docs/study.md` `model_card.md` `specs/…/spec.md` `plan.md` `tasks.md` `research.md` `data-model.md` |
| **발표자** | **③ 발표자료·시연** | `presentation_draft.pptx` `docs/presentation_script.md`(새로) |
| **팀원 A** | **②-A 서버 운영 + DDBM 사이트** | `check_project.sh` `specs/…/quickstart.md` `docs/deploy.md` `docs/ddbm-intent/` `Intent-*.md` (서버에서 실행하는 명령 전부) |
| **팀원 B** | **②-B 웹 화면** | `web/templates/index.html` **한 파일만** (`web/app.py` `frontend.py` `predict.py` 는 금지 — 숫자는 서버 것) |

②-A 와 ②-B 는 파일이 완전히 갈라져 있다. B 가 화면을 고쳐 push 하면 A 가 서버에서 `./check_project.sh deploy` 로 반영하고 결과(파리티·스모크)를 B 에게 알린다.
데이터·모델 폴더(`db/` `src/day*` `src/finalize_model.py` `artifacts/`)는 **동결** — 건드려야 하면 팀장(①)이 승인한다.

**흐름**: 팀장 ① 지표 표 → 팀장 ④ 문서 대조 · 발표자 ③ 질문 카드 → 팀원 A 사이트·서버 반영 → 발표자 리허설(팀원 A 가 켜둔 서버 위에서, 팀원 B 의 화면으로)

### ① 평가지표 (팀장) — 세부 업무 (순서대로)

1. **지표 한 표** 만들기 → `reports/metrics_summary.md` (새 파일). 열: 지표 · 값 · 근거 파일 · 한 줄 의미
   - 홀드아웃 정확도 0.7394 (`runs.csv`) · 교차검증 0.7315 ± 0.0153 · 시드 10회 **0.7366 ± 0.0081** (`reports/repeat_experimentA.csv`) · 찍기 0.5010 대비 +23.8%p · 연습−검증 격차 +0.0022
   - F1 0.7352 · AUC 0.8150 · Brier 0.1756
   - 승리요인: 골드 > 경험치 > 드래곤, 계수·permutation 순위 일치 (`reports/win_factor_ranking.csv`)
   - 오류 구간: 접전 0.615 → 우세 0.741 → 크게 우세 0.859 → 결정 0.947 (`reports/day4_error_analysis.csv`)
   - 실험 B: +5.25%p, 접전만 +7.8%p (`reports/expB_close_games.csv` `repeat_experimentB.csv`)
2. **"왜 이 지표인가"** 한 줄씩: 정확도 1순위 = 승패 50.1:49.9 균형 + 오답 비용 대칭. F1·AUC·Brier는 보조. 임계값 0.5 = 0.40~0.60 훑어 평평함 확인.
3. **방어 카드 5장** — 반드시 답을 준비할 질문:
   - "접전 0.615는 너무 낮지 않나?" → 모델이 아니라 10분 정보의 한계. 증거: 15분 정보로 접전만 +7.8%p
   - "0.7394 · 0.7366 · 0.7136 왜 다 다르냐?" → 분할이 다르다(시드 42 단일 / 시드 10회 평균 / 팀 DB `ml_split`). 대표값은 반복 평균
   - "킬 계수가 음수면 킬하면 진다는 뜻?" → 골드에 이미 반영(상관 0.92). 킬은 골드로 바뀔 때만 의미
   - "더 좋은 모델 안 써봤나?" → 8종 비교, 복잡할수록 낮았음. RF는 연습 1.0000 과적합
   - "다른 티어·패치에도 되나?" → 안 된다. 다이아·해당 패치 한정, 재학습 절차는 남김
4. 문서 숫자를 바꿨거나 남이 바꿨으면 `python src/factcheck.py` → **0건** 확인 (③④에게 표 공유 후에도 한 번 더).
5. **완료 기준**: ③이 이 표와 카드만 보고 예상 질문에 답할 수 있다.

### ②-A 서버 운영 + DDBM 사이트 (팀원 A) — 세부 업무

1. **매일 아침** 서버에서 `./check_project.sh status` → 세 줄 초록(백엔드·프런트·공개 도메인 200). 아니면 `restart`. 재부팅됐으면 `start`.
2. **누가 push 하면** `./check_project.sh deploy` (team pull → 재기동 → 파리티 6건 + 스모크 11건). 실패하면 `logs` 보고 push 한 사람에게 알린다.
3. **DDBM 사이트 갱신** (https://abc.sumzip.com/member): "시스템 의도"의 Plan·Tasks·Implement·Clarify·Report 레코드를 `docs/ddbm-intent/*.md` 내용으로 교체(기존 템플릿 레코드 삭제 후 추가) → "시스템 의도 파일 저장" → 루트 `Intent-*.md` 갱신 확인. Specify(캔버스)는 그대로. "시스템 설계 구현 상태" 6개 전부 켜졌는지 확인.
4. **4명 접속 확인**을 주관: 각자 https://p4.sumzip.com → 예시 3개(51.2 / 94.6 / 16.8%) 스크린샷을 게시판에 모은다.
5. **발표 당일** 30분 전 `restart` + `test` + `status`. 발표 노트북에서 사이트 미리 열어두기. 도메인이 죽으면 서버에서 `http://127.0.0.1:9504` 로 대체.
6. **완료 기준**: 스크린샷 4장 + 사이트 6단계 채움 + 당일 체크리스트 통과. 절차 원문은 `docs/deploy.md`.

### ②-B 웹 화면 (팀원 B) — 세부 업무

1. 파일은 **`web/templates/index.html` 하나만**. 예측 로직·API·서버 파일은 열지도 않는다 — 화면은 서버가 준 숫자를 보여주기만 한다.
2. 고칠 것 (우선순위): ① 첫 화면 3초 안에 "무엇을 넣고 무엇이 나오는지" 보이게(제목·부제·예시 버튼 3개가 맨 위) ② 결과 영역 — 승률 막대·요인 5개·경고가 한눈에 ③ "서버 리포트" 패널 표 가독성(열 이름 한글, 소수 4자리 → 2자리 표시는 JS 에서만) ④ 톤은 밝은 톤 유지, 색은 블루/레드 팀 색만.
3. 고칠 때마다: 로컬에서 `venv311/bin/python web/app.py` + `venv311/bin/python web/frontend.py` 띄워 http://127.0.0.1:9504 확인 → `git pull && git push` → 팀원 A 에게 `deploy` 요청 → A 가 알려준 파리티·스모크 결과가 "전부 통과"인지 확인.
4. 시연 순서(접전 → 블루 우세 → 요인 → 리포트)가 클릭 3~4번으로 되는지 발표자와 한 번 맞춘다.
5. **완료 기준**: 발표자가 "화면만 보고 설명 가능"이라고 OK + 리허설 1회 통과.

### ③ 발표자료·시연 (발표자) — 세부 업무

1. **12~15장으로 압축** (`presentation_draft.pptx` 24장에서): ① 질문 "언제 승부가 결정되나" ② 데이터(9,879판·40컬럼·10분) ③ 방법(분할 먼저·찍기 0.50·8종→로지스틱) ④ 결과(0.74, 요인 3개) ⑤ 언제 틀리나(접전 0.615↔결정 0.947) ⑥ 실험 B(+5.25%p, 접전만) ⑦ 한 줄 결론("골드차 4천이면 끝난 경기, 1천 미만이면 이제 시작") ⑧ 한계 ⑨ 시연.
2. **시연 시나리오 3단계** → `docs/presentation_script.md`: 접전 버튼(51%) → "이건 모델도 모른다" · 블루 우세(95%) → 요인 목록 → "킬이 음수인 이유" 한 마디 · 리포트 패널 펼쳐 오류 구간 표 → ⑤장과 연결.
3. **예상 질문 카드 10장**: ①의 방어 카드 5장 + 도메인 질문 5장(왜 10분·왜 다이아·와드 무관·경기 유형 k=4 한계·실시간 안 되는 이유). 답은 `specs/002-ml-prediction-service/research.md`의 Q&A를 그대로 쓰면 된다.
4. **리허설 2회** — 시간 재기. 1회는 ②가 서버 켜둔 상태에서 실제 사이트로. 넘치면 ③⑥장부터 줄인다.
5. **완료 기준**: 제한 시간 −1분 안에 끝남 + 질문 카드 10장 + 시연이 실제 사이트에서 됨.

### ④ 문서·정성검증 (팀장) — 세부 업무

1. **SC-7 스모크 테스트**: 게임 모르는 사람 1~2명에게 `README.md` 부록(관전 포인트 3개)과 화면만 보여주고 "지금 어느 팀이 왜 유리한지" 말하게 한다. 말했으면 통과, 못 했으면 어디서 막혔는지. **결과를 정직하게** `docs/experiment_report.md` 끝에 기록하고 `specs/…/spec.md` 채점표 SC-7을 ✅/❌로.
2. **`viz_3_game_types.png` 라벨 버그**: `notebooks/visualizations.ipynb`에서 군집 번호↔이름 매핑을 `reports/day2b_game_type_profile.csv` 기준으로 고친다 (0 운영전 41.3% · 3 난타전 32.5% · 1 일방적 19.4% · 2 시야전 6.8%). 재생성 후 PPT용으로 ③에게 전달.
3. **문서 숫자 정합성**: `README.md` · `docs/*.md` · `specs/002-ml-prediction-service/*.md`의 숫자가 ①의 `metrics_summary.md`와 같은지 대조. 다르면 문서를 고친다(숫자 출처는 ①). 끝나면 `python src/factcheck.py` 0건.
4. `model_card.md` 사용 금지 상황 6가지가 캔버스 [부정적 영향]과 맞는지 확인.
5. **GitHub 첫 화면** 정리: `README.md` 맨 위에 공개 주소 · 실행 5줄 · `docs/TEAM_WORKFLOW.md` 링크가 보이게.
6. **완료 기준**: SC-7 기록 + viz_3 수정본 + factcheck 0건 + README 첫 화면.

### 서로 주고받는 것 (마감 순서)

①의 지표 표 → ④(문서 대조)와 ③(질문 카드) → ②가 사이트·서버 반영 → ③ 리허설(②의 서버 위에서). **①이 가장 먼저 끝나야** 나머지가 굴러간다.

## 매번 이 순서로 (하나의 브랜치를 안전하게 공유하는 법)

```bash
git checkout team             # 0. 항상 team 브랜치에서 (처음 한 번, 이후엔 이미 team)
git pull                      # 1. 시작 전 항상 최신으로 (pull.rebase=true 라 내 커밋이 위로 올라간다)
# ... 작업 ...
./check_project.sh test       # 2. 서비스·predict.py 를 건드렸으면 파리티·스모크 통과 확인
git add -A && git commit -m "포지션: 무엇을 왜"   # 3. 작게, 자주
git pull && git push          # 4. 올리기 직전에 한 번 더 pull
```

- 충돌이 나면 **내 담당 폴더는 내 것, 남의 폴더는 남의 것**으로 푼다. 모르겠으면 덮어쓰지 말고 물어본다.
- 커밋하지 않는 것: `.env`(비밀번호·API 키) · `venv*/` · `data/*.csv`(라이선스·97MB) · `run/` `logs/` — `.gitignore`가 막아주지만 `git status`로 확인.
- 문서 숫자를 바꿨으면 `python src/factcheck.py` 가 0건인지 본다.

## 제출 시점에 `team` → `main` 합치기 (②만, 리허설 통과 후)

```bash
git checkout main && git pull && git merge --ff-only team && git push && git checkout team
```

## 팀 서버(공개 서비스)에 반영하기

`main`에 push 했다고 사이트가 바뀌지 않는다. 팀 서버에서 한 번 실행한다:

```bash
# 팀 서버에 접속(접속 정보는 게시판) 하거나, 서버에 앉은 사람이
cd ~/project2608 && ./check_project.sh deploy    # git pull → 재시작 → 테스트
./check_project.sh status        # https://p4.sumzip.com 200 확인
```

DDBM 사이트의 "시스템 설계 구현 상태"도 이 폴더(`specs/002-ml-prediction-service/`)를 읽으므로 같은 명령으로 갱신된다.

## 처음 합류할 때 (Windows·macOS 공통)

```bash
git clone https://github.com/wpalswpa/project2608.git && cd project2608
git checkout team                     # 작업 브랜치로 (main 은 제출본)
python3.11 -m venv venv311            # Windows: py -3.11 -m venv venv311
venv311/bin/pip install -r requirements.txt     # Windows: venv311\Scripts\pip install -r requirements.txt
cp .env.example .env                  # DB_PASSWORD 만 채운다 (커밋 금지)
venv311/bin/python predict.py --demo  # 51.2% / 94.6% / 16.8% 가 나오면 환경 OK
```

줄바꿈은 `.gitattributes`로 LF 통일돼 있어 Windows에서도 그대로 쓰면 된다. Python은 **3.11** (모델이 scikit-learn 1.9.0 저장본).

`predict.py --demo` 까지 나오면 환경 준비 끝이다. **`./check_project.sh start` 는 팀 서버에서 쓰는 명령이라 각자 PC 에서는 실행할 필요가 없다**
(Windows 는 Git Bash 가 있어야 돌고, 각자 9504 를 띄울 이유도 없다). 서비스 확인은 https://p4.sumzip.com 에서 한다.

### push 가 403 이면 — 초대를 못 받은 것이다

저장소가 공개(Public)라 **clone 은 누구나 되지만, `team` 에 push 하려면 Collaborator 초대가 따로 필요하다.**
저장소 주인이 GitHub → Settings → Collaborators → Add people 에서 팀원 3명을 초대하고,
초대받은 사람은 메일이나 https://github.com/notifications 에서 수락해야 push 가 열린다.
