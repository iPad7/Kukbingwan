# Kukbingwan Dummy App – 설치 및 실행 가이드

공모전 제출용 더미 스켈레톤을 로컬에서 기동하기 위한 절차입니다. 실데이터 없이도 컨테이너/엔드포인트가 동작하는 수준입니다.

## 사전 준비
- Docker / Docker Compose
- 포트 여유: Airflow UI `8080`, Web Viewer `8000` (Postgres SoT `5433`은 로컬 노출)

## 환경 변수 설정
1) `.env.example`을 복사해 `.env` 생성:
   ```bash
   cp .env.example .env
   ```
2) 기본값만으로 더미 실행 가능하며, 필요 시 아래를 수정:
   - `SOT_DB_*`: SoT Postgres 접속 (컨테이너 내부는 `postgres-sot`)
   - `QDRANT_URL`, `QDRANT_COLLECTION`
   - `OPENAI_API_KEY`, `NOTION_TOKEN`, `NOTION_DATABASE_ID` (더미 단계에선 placeholder 가능)
   - `ARTIFACT_DIR=/artifacts` (agent-batch/web-viewer 공유)

## 실행
```bash
docker compose up --build
```

## 확인 포인트
- Airflow UI: http://localhost:8080
- Health: http://localhost:8000/health
- 플랫폼 리스트: `curl "http://localhost:8000/platforms"`
- 랭킹 샘플: `curl "http://localhost:8000/rankings?dt=2024-09-01"`
- xlsx 다운로드: http://localhost:8000/downloads/rankings.xlsx

## 기본 구성 요소
- 컨테이너: `airflow-webserver`, `airflow-scheduler`, `airflow-meta-db`, `postgres-sot`, `qdrant`, `agent-batch`, `web-viewer`
- 볼륨: `airflow_meta_data`, `postgres_sot_data`, `qdrant_data`, `artifacts`
- 초기 스키마/시드: `migrations/0001_init.sql`, `seed/seed.sql` (Postgres SoT)
- 샘플 아티팩트: `artifacts/sample_rankings.xlsx` (앱 시작 시 생성)
- DAG 스텁: `airflow/dags/*.py` (BashOperator에서 추후 `docker exec agent-batch ...`로 교체 예정)

## 트러블슈팅
- Airflow 메타 DB가 init 오류(`.../var/lib/postgresql/data exists but is not empty`) 시: `docker volume rm kukbingwan_airflow_meta_db_data` 후 재기동.
- Airflow 로그 퍼미션 오류 시: `docker compose down` 후 재기동 (컨테이너는 root로 실행됨). 로그 디렉터리를 호스트에 직접 만들지 마세요.
- agent-batch 컨테이너는 기본적으로 대기(`sleep infinity`) 상태입니다. 필요 시 아래로 실행:
  ```bash
  docker compose exec agent-batch python -m app ranking_etl --date 2024-09-01
  ```
- 컨테이너가 바로 내려가면: `docker compose logs <service>`로 확인 (예: `postgres-sot`, `agent-batch`).
- 포트 충돌 시: `docker-compose.yml`의 `8080:8080`, `8000:8000`, `5433:5432` 등을 변경 후 재기동.
- 스키마/시드 재적용이 필요하면: `postgres_sot_data` 볼륨을 삭제 후 재기동 (데이터 초기화 주의).
- Airflow 메타 DB/초기화 문제 시: `docker compose down` 후 `docker volume rm kukbingwan_airflow_home kukbingwan_airflow_meta_db_data || true` 실행 뒤 `docker compose up --build`.
- Airflow 관리자 계정 생성: 컨테이너가 뜬 후 아래 실행  
  - Mac/Linux/WSL: `./scripts/create_airflow_admin.sh`  
  - Windows PowerShell: `powershell -ExecutionPolicy Bypass -File scripts/create_airflow_admin.ps1`  
  (기본 admin/admin, 환경변수 `AIRFLOW_ADMIN_USER/EMAIL/PASSWORD`로 변경 가능).
