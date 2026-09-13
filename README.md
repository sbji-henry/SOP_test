# 산불재난 SOP_test (산림청)

산림청 「산불 재난」 위기대응 실무매뉴얼 **2026. 6.**의 업무를 탐색하고, 조치 원문을 확인하는 1차 서비스입니다.

## 실행 — Docker Desktop

Docker Desktop을 실행하고 **Linux containers** 모드에서 다음 명령을 실행합니다. Windows PowerShell, macOS 및 Linux에서 같은 명령을 사용합니다.

```sh
git clone https://github.com/sbji-henry/SOP_test.git
cd SOP_test
docker compose up --build
```

브라우저에서 **http://localhost:8080** 접속. 최초 빌드 시 Python 기본 이미지를 내려받으므로 인터넷 연결이 필요합니다. 빌드 이후 서비스는 외부 API, CDN, AI 모델, API 키 없이 실행합니다.

```sh
# 백그라운드 기동 및 health 확인 (Compose v2.20 이상)
docker compose up --build -d --wait
docker compose ps
docker compose logs -f

# 종료
docker compose down
```

8080 포트를 다른 프로그램이 사용 중이면 프로젝트 루트에 `.env` 파일을 만들고 `SOP_PORT=8081`을 넣은 뒤 다시 실행합니다. 이 경우 접속 주소는 http://localhost:8081 입니다. 기본 바인딩은 로컬 PC 전용 `127.0.0.1`입니다.

## 1차 구현 범위

- WF-001~WF-012 / **51개 조치**, 원문 발췌 50개와 연결.
- 업무명·기관·조치 원문 통합 검색. 업무 단계·관련 기관 필터를 AND 조건으로 결합.
- Workflow Graph: 업무 포함 관계, 원문에 명시된 순서/조건, 노드 선택, 확대·축소·화면 맞춤·드래그.
- 조치 목록과 원문 패널. 업무·조치 단위 URL 링크 복사 및 재접속.
- 원문 발췌 XML 다운로드, 근거 JSON API, 원천 파일 SHA-256 추적.
- 반응형 한국어 UI, 키보드 조작, 로딩·빈 결과·오류 표시.
- Docker 이미지 빌드 중 데이터/API 테스트, healthcheck, GitHub Actions의 Docker·브라우저 검증.

## 원문 우선 원칙

**조치 본문은 원문에서 추출하며 AI가 절차를 생성하지 않습니다.** 줄바꿈/공백만 정규화하고 조건·기호를 보존합니다. WF 번호·업무명·단계 및 기관 검색 분류는 서비스 탐색용 편집 매핑이며, 공식 매뉴얼 코드나 새 지휘·책임 체계가 아닙니다.

이전 WF 번호별 정의는 빈 저장소와 제공된 대화 자료에서 확인되지 않아, 이번 버전의 매핑을 [docs/WORKFLOWS.md](docs/WORKFLOWS.md)에 명시했습니다.

그래프의 실선은 **업무에 포함된 조치**이며 실행 선후 관계가 아닙니다. 화살표는 원문에 명시된 `잔불 진화 후` 및 `추가피해 가능성에 따라` 관계에만 사용합니다. 병렬로 수행할 수 있는 신고·전파·진화·대피를 임의의 직렬 절차로 연결하지 않습니다. 원문 속 `필요시`, `산불발생 시`, `대피 권고 시`, `대피 명령 시` 조건을 유지합니다.

모든 노드와 연결선은 근거 ID를 가집니다. 근거는 문서명·발행기관·판본·원천 파일 해시·HWPX 내부 XML 파일·요소 위치·문단 ID·원문 인용을 포함합니다. 인쇄 쪽수는 검증되지 않아 만들어 넣지 않았습니다.

서비스와 저장소에는 관련 업무의 **원문 XML 발췌**만 수록합니다. 전체 HWPX 및 업무와 무관한 비상연락망은 포함하지 않습니다. 원천 HWPX는 별도 보관하고 아래 명령으로 동일성을 재검증할 수 있습니다.

```sh
python scripts/build_data.py "/path/to/산불재난위기대응실무매뉴얼산림청260625.hwpx" --check
```

원천 파일명까지 기록하므로 첨부 파일의 이름을 유지합니다. 매뉴얼 변경 시 `scripts/build_data.py`의 매핑을 원문과 대조한 후 `--check` 없이 생성하고 테스트합니다.

## 로컬 개발·테스트

Python 3.12 이상, 서비스 실행에 별도 Python 패키지 설치는 필요 없습니다.

```sh
python -m app.server
python -m unittest discover -s tests -v
python scripts/smoke.py
```

브라우저 E2E 테스트는 실행 중인 서비스가 필요합니다. Node.js 22 및 Playwright를 테스트 용도로만 사용합니다.

```sh
npm ci
npx playwright install chromium
npm run test:e2e
```

Linux CI에서는 브라우저 시스템 라이브러리를 설치하도록 `npx playwright install --with-deps chromium`을 사용합니다. `BASE_URL`로 테스트 대상 주소를 변경할 수 있습니다. 테스트 스크린샷은 `test-results/`에 생성됩니다.

## 구조 및 API

| 경로 | 역할 |
|---|---|
| `app/server.py` | 읽기 전용 HTTP 서비스, 검색/필터 API, 데이터 무결성 검사 |
| `web/` | 기본 UI, SVG Workflow Graph, 원문 조회 |
| `data/workflows.json` | 12개 업무·51개 조치·원문 근거 데이터 |
| `data/source-excerpts.xml` | 원천 HWPX에서 추출한 실제 XML 문단 |
| `scripts/build_data.py` | 원문 매핑·추출·원본 대조 |
| `tests/`, `scripts/smoke.py` | 원문/검색/API/브라우저 및 실제 서비스 테스트 |
| `Dockerfile`, `compose.yaml` | Docker Desktop용 단일 서비스 구성 |
| `.github/workflows/ci.yml` | main/tag push 시 Docker 빌드·기동·브라우저 검증 |

| API | 설명 |
|---|---|
| `GET /health` | 서비스 상태·버전 |
| `GET /api/meta` | 문서 메타데이터·필터 옵션·수록 수량 |
| `GET /api/workflows?q=...&phase=...&agency=...` | 검색 및 교집합 필터 |
| `GET /api/workflows/WF-007` | 업무·노드·연결선·근거 |
| `GET /api/evidence/S3-E1302` | 개별 근거 및 원천 문서 정보 |
| `GET /source-excerpts.xml` | 원문 XML 발췌 |

## 후속 버전

| 버전 | 계획 |
|---|---|
| v0.2.0 | 기관 Swimlane, 상세 노드 모델, 원문 근거 탐색 고도화 |
| v0.3.0 | 산불 CCTV 이벤트 → SOP 자동 진입 |
| v0.4.0 | RAG 기반 매뉴얼 검색 및 AI Agent |
| v1.0.0 | 조치 체크·담당자 확인·상황보고 초안 |

1차는 매뉴얼 조회 서비스입니다. 실시간 사고 현황·경보 자동발령·기관 통보·조치 실행·완료 상태 저장은 구현 범위에 포함하지 않습니다.

지정한 구현 커밋 메시지로 `main`에 반영된 경우, CI가 Docker·브라우저 검증에 성공한 뒤 `v0.1.0` 태그를 생성합니다. 기존 태그를 다른 커밋으로 이동하지 않습니다.
