# 팀 서버에 올리기 (배포)

팀원들이 **http://p4.sumzip.com:9504** 로 함께 쓰려면 팀 서버에서 서비스를 띄워야 합니다.
지금은 각자 노트북에서만 돌고 있어서 다른 사람이 못 들어옵니다.

## 우리 팀에 배정된 것

| 항목 | 값 |
|---|---|
| 도메인 | p4.sumzip.com |
| 프론트엔드 포트 | 9504 (팀원이 접속하는 곳) |
| 백엔드 포트 | 9524 (예측 담당, 바깥에 노출 안 함) |
| 서버 | LLM Server (192.168.0.19, 외부 SSH 2225) |
| 서버 계정 | pioneer4 |
| 프로젝트 폴더 | /Users/pioneer4/project2608 |

## 배포 순서

**1. 서버에 접속**

```bash
ssh -p 2225 pioneer4@mis.iptime.org
```

**2. 코드 받기** (처음 한 번)

```bash
cd /Users/pioneer4/project2608
git clone https://github.com/wpalswpa/project2608.git lol-service
cd lol-service
```

이미 받아둔 뒤에 새 버전을 반영할 때는 `git pull` 만 하면 됩니다.

**3. 준비물 설치** (처음 한 번)

```bash
pip install -r requirements.txt
```

**4. 데이터·모델 올리기**

원본 CSV와 학습된 모델은 용량·저작권 때문에 저장소에 없습니다. 둘 중 하나를 하세요.

- **모델만 올리기** (빠름) — 내 노트북에서:
  ```bash
  scp -P 2225 artifacts/model.joblib artifacts/schema.json \
      pioneer4@mis.iptime.org:/Users/pioneer4/project2608/lol-service/artifacts/
  ```
- **서버에서 직접 학습** — `data/README.md` 를 보고 CSV 2개를 서버에 넣은 뒤:
  ```bash
  python src/finalize_model.py
  ```

**5. 서비스 시작**

```bash
./check_project.sh start
./check_project.sh status
```

`status` 에 두 줄 다 초록색 "정상" 이 뜨면 성공입니다.

**6. 브라우저에서 확인**

http://p4.sumzip.com:9504 로 들어가 예시 버튼을 눌러보세요.

## 안 될 때

| 증상 | 확인할 것 |
|---|---|
| 시작은 됐는데 접속이 안 됨 | 서버 방화벽에서 9504 포트가 열려 있는지 (`sudo ufw allow 9504`) |
| 도메인만 안 열리고 IP는 됨 | p4.sumzip.com → 서버 9504 매핑은 학원 인프라 설정입니다. 강사에게 문의하세요 |
| "포트를 다른 프로그램이 쓰고 있습니다" | 학원이 띄워둔 기본 페이지가 9504를 쓰고 있을 수 있습니다. DDBM 사이트에서 기본 페이지를 중지하거나 `lsof -i :9504` 로 확인 |
| 백엔드만 "응답 없음" | `./check_project.sh logs` — 대개 model.joblib 이 없어서 납니다 (4단계) |
| 파이썬을 못 찾음 | `PYTHON=/usr/bin/python3 ./check_project.sh start` 처럼 지정 |

## 코드를 고친 뒤

```bash
git pull
./check_project.sh restart
python web/test_parity.py     # 화면 확률 == 모델 확률 확인
```

## 서버가 재부팅되면

서비스는 자동으로 살아나지 않습니다. 다시 접속해서 `./check_project.sh start` 를 실행하세요.
계속 띄워두려면 강사에게 서비스 등록(systemd) 방법을 문의하는 편이 좋습니다.
