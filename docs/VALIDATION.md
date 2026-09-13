# v0.1.0 검증 기록

## 로컬 검증 (2026-09-13)

- 빈 공식 저장소를 clone하고 `main`에서 1차 구현.
- 원천 HWPX SHA-256: `b5a36563644d1d1e343d49c470fb11512cbbffba226d352c670742cc80f5614a`.
- `python scripts/build_data.py <원천 HWPX> --check`: 50개 XML 발췌 및 전체 생성 JSON이 실제 첨부 원본과 일치.
- `python -m unittest discover -s tests -v`: 10개 테스트 통과. 12개 업무·51개 조치의 근거 연결, 원문 조건 누락 여부, 변조 거부, 검색/필터, HTTP 및 경로 접근 제어 확인.
- 실행한 Python 서비스에 대한 `scripts/smoke.py`: health·12개 상세·근거·한국어 검색·UI 진입 통과.
- `node --check web/app.js`: JavaScript 구문 검증 통과.
- `docker compose config --quiet`: Compose v2.39.2 구성 검증 통과.

## Docker 실행 환경 제한

이 작업 환경에서 Docker CLI 28.3.3과 Compose v2.39.2를 사용해 `docker compose up --build -d`를 실제 시도했으나, Docker daemon 소켓 연결이 `socket: operation not permitted`로 차단되었습니다. 이 결과는 컨테이너 빌드·기동 성공을 의미하지 않습니다. 사용자의 Windows/macOS Docker Desktop 자체는 이 환경에서 직접 실행할 수 없습니다.

원격 브라우저의 localhost 접속도 `ERR_BLOCKED_BY_CLIENT`로 제한되어 로컬 화면 검증에 사용할 수 없었습니다.

`.github/workflows/ci.yml`은 `main` push 뒤 실제 Ubuntu Docker 환경에서 이미지 빌드 → health 대기 → smoke test → 12개 워크플로우/51개 조치·검색·필터·그래프·모바일 E2E를 실행합니다. 원격 검증의 성공 여부는 해당 commit의 GitHub Actions 실행 결과를 기준으로 판단합니다. Docker 실기동 검증 전 로컬 커밋이 필요한 환경 제약이며, 로컬 구성 검증과 원격 실기동 검증을 구분합니다.

## 원격 검증 진행 기록

- GitHub Actions 실행 `34743896810`: 실제 Docker 이미지 빌드, `docker compose up --build -d --wait`, healthcheck, 서비스 smoke test 통과.
- 같은 실행에서 12개 업무·51개 노드의 원문 표시 및 검색·단계/기관 필터·빈 결과·초기화·탭·확대·문서 정보 검증 통과.
- 기관 필터 상태에서 다른 업무로 이동하는 해시 링크 문제를 발견하여, 외부 링크로 지정한 업무가 필터 밖에 있으면 검색 조건을 초기화하고 해당 업무를 불러오도록 수정. E2E는 같은 문서 내 비동기 이동 완료를 기다리도록 보완.
- 최종 전체 E2E 및 태그 생성 상태는 최종 커밋에 연결된 Actions 실행에서 확인.

## 재현 명령

```sh
docker compose config --quiet
docker compose up --build -d --wait --wait-timeout 90
python scripts/smoke.py
npm ci
npx playwright install --with-deps chromium
npm run test:e2e
docker compose down
```

`docker compose up --build` 호환 구성: 단일 Linux 컨테이너, Python 다중 아키텍처 기본 이미지, 호스트 절대경로/바인드 마운트 없음, shell entrypoint 없음, LF 파일, 비관리자 UID, 읽기 전용 파일시스템, loopback 포트 바인딩. Windows는 Docker Desktop의 Linux containers 모드가 필요합니다.
