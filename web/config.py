# 서비스 설정 — 팀 서버 배포 규격 (DDBM 팀 설정과 일치)
#
#   도메인      p4.sumzip.com
#   프론트엔드  9504  (브라우저가 접속하는 곳. 도메인이 여기로 매핑된다)
#   백엔드      9524  (예측 API. 프론트엔드가 대신 호출한다)
#
# 환경변수로 덮어쓸 수 있다. 로컬에서 포트가 겹칠 때만 쓰면 된다.
#   FRONTEND_PORT=8504 BACKEND_PORT=8524 python web/frontend.py
import os

DOMAIN = os.environ.get("SERVICE_DOMAIN", "p4.sumzip.com")
FRONTEND_PORT = int(os.environ.get("FRONTEND_PORT", 9504))
BACKEND_PORT = int(os.environ.get("BACKEND_PORT", 9524))

# 프론트엔드가 백엔드를 부를 주소. 같은 서버 안에서만 오가므로 127.0.0.1 로 고정한다
# (백엔드를 바깥에 직접 노출하지 않는다 — 들어오는 문은 프론트엔드 하나뿐)
BACKEND_HOST = os.environ.get("BACKEND_HOST", "127.0.0.1")
BACKEND_URL = f"http://{BACKEND_HOST}:{BACKEND_PORT}"

# 0.0.0.0 = 서버 밖에서도 접속 허용 (팀원들이 도메인으로 들어와야 하므로 필요)
BIND_HOST = os.environ.get("BIND_HOST", "0.0.0.0")
