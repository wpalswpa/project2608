<!-- ─────────────────────────────────────────────
  팀 서버(맥)에 올리고 확인하는 절차.
  왜 필요한가: 배포는 git push 만으로 안 되고 서버에서 한 번 더 실행해야 한다. 그 순서를 적어둔다.
  주로 보는 사람: 배포 담당
  ───────────────────────────────────────────── -->

# 팀 서버에 올리기 (배포·운영) — ② 서비스·운영 담당

공개 주소 **https://p4.sumzip.com** 은 수업 서버 프록시가 팀 서버(내부망 맥)의 **프런트 9504** 로 넘겨 준다.
프런트가 `/api/*` 를 **백엔드 9524** 로 중계하므로 바깥에 열린 문은 9504 하나뿐이다.

| 항목 | 값 |
|---|---|
| 도메인 | https://p4.sumzip.com (HTTPS, 포트 없이) |
| 프런트엔드 | 9504 — `web/frontend.py` (화면 + /api 프록시) |
| 백엔드 | 9524 — `web/app.py` (예측 API, `predict.py` import) |
| 프로젝트 폴더 (서버) | `~/project2608` (브랜치 `team`) |
| 파이썬 | `venv311/` — Python 3.11 + `requirements.txt` 고정 버전 |

> 서버 접속 정보(호스트·포트·계정)는 저장소에 적지 않는다 — 팀 게시판/강사 안내를 본다. 비밀번호·API 키는 `.env` 에만.

## 처음 한 번 (이미 돼 있음 — 서버를 새로 받을 때만)

```bash
cd ~/project2608 && git checkout team && git pull
/opt/homebrew/bin/python3.11 -m venv venv311 && venv311/bin/pip install -r requirements.txt
cp .env.example .env            # DB_PASSWORD (선택: RIOT_API_KEY) 채우기 — 커밋 금지
venv311/bin/python predict.py --demo    # 51.2% / 94.6% / 16.8%
./check_project.sh start && ./check_project.sh test
```

`artifacts/model.joblib`·`schema.json` 은 저장소에 들어 있어 따로 올릴 필요가 없다. 원본 CSV 는 서비스에 필요 없다(학습을 다시 할 때만 `data/README.md`).

## 매일 / 누가 push 한 뒤

```bash
./check_project.sh status     # 백엔드·프런트·공개 도메인 세 줄 초록이면 정상
./check_project.sh deploy     # team 브랜치 pull → 재시작 → 파리티 6건 + 스모크 11건
./check_project.sh logs       # 이상하면 로그
```

## 발표 당일

```bash
./check_project.sh restart && ./check_project.sh test && ./check_project.sh status
```
발표 노트북에서 https://p4.sumzip.com 을 미리 열어 예시 버튼 3개를 눌러 둔다. 도메인이 죽으면 서버 화면에서 `http://127.0.0.1:9504` 로 대체 시연.

## 안 될 때

| 증상 | 확인 |
|---|---|
| `status` 에서 백엔드/프런트 빨강 | `./check_project.sh logs` — 대개 `venv311` 없음(3.9 로는 모델이 안 열림) 또는 포트 점유. `stop` 뒤 `start` |
| 공개 도메인만 502 | 서비스가 꺼진 것. `start`. 켜져 있는데도 502 면 수업 서버 프록시 문제 → 강사 문의 |
| "포트를 다른 프로세스가 쓰고 있다" | 출력된 pid 확인. DDBM 사이트의 "기본 페이지" 가 9504 를 잡고 있을 수 있음 → 사이트에서 중지 |
| 서버 재부팅 | 자동으로 살아나지 않는다. 접속해서 `./check_project.sh start` |
| 화면 숫자가 이상하다 | `./check_project.sh test` — 파리티가 깨졌으면 `predict.py` 를 누가 고친 것. `git log -- predict.py` |
