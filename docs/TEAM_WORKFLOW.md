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

## 역할 배치 (2026-09-01 2차 개정 — 발표자 합류)

**저장소를 만지는 사람은 3명.** 충돌은 권한 문제가 아니라 여럿이 **같은 파일**을 만질 때 생기므로,
사람마다 손대는 파일을 완전히 갈라놨다.

### git 을 쓰는 3명

| 사람 | 맡는 것 | 손대는 파일 (완전히 갈라짐) |
|---|---|---|
| **팀장 (wpalswpa)** | 분석 · 지표 · 문서 전부 | `reports/` `docs/` `notebooks/` `README.md` `model_card.md` `runs.csv` `specs/` `src/repeat_check.py` `src/factcheck.py` |
| **서비스 담당** | 웹 · 서버 · 배포 | `web/` `check_project.sh` `docs/deploy.md` `docs/ddbm-intent/` |
| **발표자** | 발표자료 · 대본 · 리허설 2회 | **`presentation_draft.pptx` 이 파일 하나만** |

발표자는 `.pptx` 외 다른 파일을 절대 커밋하지 않는다. 바이너리라 충돌이 나면
병합이 불가능하므로, **이 파일은 발표자만 만진다**(팀장도 손대지 않는다).

데이터·모델(`db/` `src/day*` `src/finalize_model.py` `artifacts/` **`predict.py`**)은 **동결**
— 숫자가 바뀌므로 팀장 승인 후에만. 서비스는 `predict.py` 를 **읽기만** 한다.

### git 을 쓰지 않는 1명

| 사람 | 맡는 것 | 전달 방법 |
|---|---|---|
| **검증 담당** | 정성 테스트(SC-7) · 문서에서 안 읽히는 곳 찾기 | 확인 결과를 **메시지로 전달** → 팀장이 문서에 반영 |

### 남은 일과 담당

| 할 일 | 담당 | 상태 |
|---|---|---|
| 지표 한 표 (`reports/metrics_summary.md`) | 팀장 | ✅ **완료** — 지표 표 + 방어 카드 5장 |
| `viz_3_game_types.png` 라벨 버그 수정 | 팀장 | ✅ **완료** — 데이터로 매핑 검증 후 재생성 |
| 문서 숫자 정합성 | 팀장 | ✅ **완료** — `factcheck` 0건 |
| 서비스가 발표 순간까지 살아 있기 | 서비스 담당 | ⬜ https://p4.sumzip.com 접속 · 예시 버튼 동작 |
| 화면 다듬기 | 서비스 담당 | ⬜ 처음 보는 사람이 설명 없이 써본다 |
| `team` → `main` 병합 (제출 스냅샷) | 서비스 담당 | ⬜ 리허설 통과 후 |
| 발표자료 + 대본 + 리허설 | 발표자 | ⬜ 12~15장 · 시연 3단계 · 리허설 2회 |
| 정성 테스트 (SC-7) | 검증 담당 | ⬜ 게임 모르는 1~2명이 순위표만 보고 관전 포인트를 말한다 |

**발표자에게** — 대본은 `reports/metrics_summary.md` 하나만 보면 된다.
발표에 나갈 모든 숫자가 근거 파일과 함께 정리돼 있고, **예상 질문 5개의 답(방어 카드)** 까지 들어 있다.

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

## 제출 시점에 `team` → `main` 합치기 (팀장만, 리허설 통과 후)

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

## 처음 합류할 때 — **git 쓰는 2명만** (Windows·macOS 공통)

발표자·검증 담당은 아래를 할 필요가 없다. 서비스는 https://p4.sumzip.com 에서 보면 되고,
결과물은 팀장에게 파일이나 메시지로 전달하면 팀장이 커밋한다.

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

### push 가 403 이면

우리 팀은 **공유 계정(wpalswpa)** 을 함께 쓰므로 그 계정으로 로그인돼 있으면 push 가 된다.
다른 계정으로 로그인돼 있으면 403 이 난다 — `git config user.name` 으로 확인하고 공유 계정으로 맞춘다.
(계정을 공유하니 Collaborator 초대는 필요 없다.)
