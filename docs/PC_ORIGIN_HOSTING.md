# PC 원본 서버 + 외부 HTTPS 공개 구성

확인일: 2026-09-27. 대상: https://github.com/sbji-henry/SOP_test.
실제 작업 폴더: C:\SOP_test.

## 결론

Northflank 공식 문서에서 localhost를 바로 외부 URL로 전환하는 내장 reverse tunnel은 확인되지 않았다. `northflank forward`는 Northflank의 서비스/DB를 개발 PC에서 접속하는 반대 방향 기능이다.

하지만 **Northflank HTTPS → Caddy 프록시 컨테이너 → Tailscale 사설망 → PC의 Tailscale Serve → PC의 SOP 서버**는 공식 지원 기능들을 조합하여 구현할 수 있다. Northflank에는 작은 프록시 1개만 배포하고 SOP 화면·API·데이터는 PC에 둔다. PC에서 Northflank의 localhost에 접속하는 것이 아니며, Northflank에서 자신의 localhost를 origin으로 지정해서도 안 된다.

기존 프로젝트는 React/Vite/Express가 아니라 Python 3.12 표준 라이브러리 HTTP 서버와 HTML/JS UI이다. 기존 Docker 서비스를 그대로 사용한다. 현재 구현은 읽기 전용 SOP 조회이며 AI Agent·RAG는 README의 후속 계획이다. 이번 작업은 AI 기능을 추가하지 않는다.

## 구성 비교

| 방법 | PC가 실제 원본인가 | Northflank 역할 | 비용·제약 |
|---|---|---|---|
| Northflank + Tailscale Serve | 예 | HTTPS 공개, 인증, 프록시 1개 | Sandbox 무료 서비스 한도 내 가능. Tailscale Personal 무료는 비상업용만 해당. 업무용 0원 보장 불가 |
| Cloudflare Quick Tunnel | 예 | 없음 | 계정·도메인 없이 임시 HTTPS. URL 변경, 동시 진행 요청 200개 제한, SSE 미지원, 운영용 SLA 없음 |
| Cloudflare Named Tunnel | 예 | 없음 | 계정 및 Cloudflare에 등록한 도메인 필요. 터널 무료 제공, 도메인 신규 구매 비용은 별개 |
| Tailscale Funnel | 예 | 없음 | *.ts.net HTTPS, 비상업용 Personal 무료. 대역폭 제한, 업무용 요금 조건 확인 필요 |
| SOP 자체를 Northflank에 배포 | 아니오 | 앱 실행·호스팅 | PC 종료 후에도 운영 가능하지만 이번 PC 원본 요구와 다름 |

Northflank 공식 가격표에는 Sandbox의 상시 실행 서비스 2개, DB 1개, cron job 2개가 기재되어 있다. 계정에서 선택 가능한 무료 리소스와 Tailscale 통합 조건을 배포 전에 확인해야 한다. 무료 인프라가 AI API 비용이나 PC 전기료까지 없애지는 않는다.

## 1. 로컬 서버 — 이미 기동한 구성

Windows PowerShell, Docker Desktop의 Linux containers 모드에서 실행한다.

```powershell
Set-Location C:\SOP_test
.\scripts\start-local.ps1
# 또는
 docker compose up --build -d --wait
Invoke-RestMethod http://127.0.0.1:8080/health
```

접속: http://localhost:8080

기존 compose.yaml은 PC의 127.0.0.1:8080에만 포트를 바인딩한다. 인터넷 공유기·Windows 방화벽에 외부 인바운드 포트를 추가하지 않는다. 컨테이너 내부의 0.0.0.0:8080은 PC 전체 인터페이스 노출과 다르다.

PC 종료·절전, Docker Desktop 종료, 인터넷 단절 시 모든 PC 원본 방식의 서비스가 중단된다. Docker 재시작 시 SOP와 인증 게이트웨이는 자동 재기동하지만 Windows 부팅 후 Docker Desktop 실행은 필요하다. Quick Tunnel은 자동 재시작하지 않으며 다시 켜면 URL을 재확인한다.

## 2. Northflank 사용 — 권장 구조와 정확한 설정

```text
사용자 브라우저
  └─ HTTPS :443 → Northflank 제공 *.code.run 주소
                   └─ HTTP :8080 → Caddy 인증 프록시
                                    └─ HTTPS :443 / Tailscale 사설망
                                         → PC의 Tailscale Serve
                                           → http://127.0.0.1:8080 SOP
```

### PC에 Tailscale 설치·연결

PowerShell에서 실행한다. Tailscale 로그인은 사용자 계정으로 완료한다.

```powershell
winget install --id Tailscale.Tailscale --exact
# 설치 후 새 PowerShell을 열거나 다음 경로 사용
& 'C:\Program Files\Tailscale\tailscale.exe' up
& 'C:\Program Files\Tailscale\tailscale.exe' serve --bg --https=443 http://127.0.0.1:8080
& 'C:\Program Files\Tailscale\tailscale.exe' serve status
```

관리 콘솔에서 MagicDNS·HTTPS를 활성화하고 PC에 `tag:sop-origin`을 부여한다. 위 방식은 **Serve**이므로 origin은 tailnet 내부에서만 접근 가능하다. Northflank 방식에서 Funnel은 켜지 않는다. Windows용 Tailscale은 Windows Docker Desktop이 노출한 localhost:8080에 접근한다.

### Northflank의 Tailscale 연동

1. `deploy/tailscale-policy.example.json`을 참고해 태그와 권한을 설정한다. 기존 정책을 통째로 덮어쓰지 않는다. 기존 `* → *` 허용 규칙이 있으면 새 제한 규칙만 추가해도 접근이 제한되지 않으므로 함께 검토한다.
2. Tailscale OAuth client에 `auth_keys` write 권한과 `tag:northflank-sop`를 부여한다. 공식 문서대로 이 태그의 tagOwners는 빈 배열이다.
3. Northflank 프로젝트 설정에서 Tailscale을 활성화하고 OAuth client ID/secret 및 태그를 입력한다. 자동 키 갱신 시 재배포를 활성화한다.
4. Northflank의 restrict Tailscale 옵션으로 이 프록시 서비스에만 연결 권한을 부여한다. subnet routes 수락은 필요 없다.
5. PC의 전체 이름, 예: `my-pc.tail1234.ts.net`을 origin으로 쓴다. 축약 호스트명·localhost는 사용하지 않는다.

OAuth secret은 저장소 또는 채팅에 넣지 않는다. 계정에서 만든 값을 로컬 `.secrets/tailscale-oauth.json`에만 저장한다.

### 프록시 배포

작성된 `deploy/northflank/` 폴더만 배포한다. 코드와 설정을 본인 저장소 브랜치에 반영한 뒤 Northflank에서 Combined service를 생성한다.

| 설정 | 값 |
|---|---|
| 소스 | sbji-henry/SOP_test의 설정 반영 브랜치 |
| Build context | /deploy/northflank |
| Dockerfile | Dockerfile (위 context 기준) |
| 인스턴스 | 1개, 계정의 Sandbox 무료 서비스 선택 |
| 공개 포트 | HTTP 8080; 외부 HTTPS는 Northflank가 처리 |
| 상태 검사 | HTTP /healthz, 8080 |
| ORIGIN_HOST | PC의 전체 Tailscale 이름; https:// 접두사 제외 |
| SOP_USER | sop |
| SOP_PASSWORD_HASH | .secrets/gateway.env에 저장된 bcrypt 해시 전체, 따옴표 없이 입력 |

비밀번호가 아직 없다면 `scripts/setup-public-password.ps1`로 만든다. `/healthz`는 프록시 생존 여부만 반환한다. origin 도달 여부는 인증 후 `/health`와 `/api/meta`로 별도 검사한다. PC가 꺼지면 프록시는 오류를 반환하며 SOP를 캐시하여 대체하지 않는다.

```powershell
# 배포할 이미지의 로컬 빌드 확인
 docker build -t sop-northflank-proxy:local .\deploy\northflank
# 배포 후 로그인 암호는 curl이 프롬프트로 받는다.
 curl.exe --fail --user sop https://YOUR-SERVICE.code.run/api/meta
```

Caddy는 origin의 TLS 인증서를 검증하며, Host 헤더는 origin 이름으로 설정한다. 인증 정보는 SOP로 전달하지 않는다. 버퍼링을 끄는 설정을 포함하지만 현재 SOP는 SSE/WebSocket 앱이 아니므로 향후 AI 스트리밍 추가 시 전체 경로를 다시 검증해야 한다. 향후 앱 자체 Authorization 토큰이 필요하면 프록시의 Basic 인증 방식과 헤더 제거 정책도 함께 변경한다.

## 3. 지금 바로 쓸 수 있는 임시 HTTPS — Cloudflare

인증 게이트웨이 + Quick Tunnel을 기동하면 임시 HTTPS 주소가 로그에 출력된다. 접속 URL과 비밀번호는 Git에 넣지 않고 별도로 전달한다. 실제 SOP 폴더·비밀 파일을 웹 정적 디렉터리로 노출하지 않는다.

다른 PC에서 새로 설치할 때만 비밀번호 설정 스크립트를 먼저 실행한다. 기존 gateway.env가 있으면 덮어쓰지 않고 중단한다. Compose 2.30 이상이 필요하다(해시의 $ 기호 보존을 위한 raw env_file).

```powershell
Set-Location C:\SOP_test
.\scripts\setup-public-password.ps1  # 최초 1회
.\scripts\start-quick-tunnel.ps1
# 공개 URL 확인
 docker compose -f compose.yaml -f compose.public.yaml logs --tail 50 quick-tunnel
# 외부 공개만 중지
 docker compose -f compose.yaml -f compose.public.yaml stop quick-tunnel
```

현재 경로는 `HTTPS → Cloudflare → PC cloudflared → 인증 게이트웨이 → SOP`이다. HTTP 게이트웨이의 8090 포트도 PC loopback에만 바인딩한다. 로컬 전용 SOP 8080 포트에는 추가 인증이 없지만 터널은 인증 게이트웨이만 대상으로 한다. 인증 없이 UI·API·원문 파일 모두 401을 반환하도록 구성한다.

## 4. 고정 주소가 필요할 때 — Named Tunnel

Cloudflare Zero Trust에서 named tunnel을 만들고, 도메인의 Published application route를 HTTP `gateway:8080`으로 지정한다. connector가 Compose 내부에서 실행되므로 대상은 localhost가 아니라 gateway이다. 토큰 문자열만 `.secrets/cloudflare-token.txt`에 저장한다. 이 파일은 Git과 Docker build context에서 제외된다.

```powershell
Set-Location C:\SOP_test
notepad .secrets\cloudflare-token.txt
 docker compose -f compose.yaml -f compose.public.yaml --profile named up -d --wait
 docker compose -f compose.yaml -f compose.public.yaml stop quick-tunnel
```

Northflank + Cloudflare 조합도 기술적으로 가능하지만 Cloudflare origin URL을 별도로 만들고 Access service token 등으로 우회 접속을 차단해야 한다. 현재 제공한 Northflank Caddyfile은 Tailscale Serve 전용이며 보호된 Quick Tunnel을 ORIGIN_HOST에 넣으면 인증 정책이 달라 그대로 동작하지 않는다. 불필요한 이중 공개 경로를 만들지 않도록 별도 조합은 기본 배포에 포함하지 않는다.

## 5. Tailscale Funnel 대안

Northflank 없이 Tailscale만 사용할 경우 로컬 인증 게이트웨이에 연결한다. `8443` 포트를 사용하면 Northflank 원본용 Serve `443`과 동시에 실행할 수 있다.

```powershell
 docker compose -f compose.yaml -f compose.public.yaml up -d sop gateway
& 'C:\Program Files\Tailscale\tailscale.exe' funnel --bg --https=8443 http://127.0.0.1:8090
& 'C:\Program Files\Tailscale\tailscale.exe' funnel status
```

MagicDNS·HTTPS·Funnel 권한이 필요하다. **같은 포트**의 Serve/Funnel은 동시에 사용할 수 없다. 이 구성은 Serve 443과 Funnel 8443을 함께 사용한다. 공개 주소는 `https://<PC의 ts.net 이름>:8443/`이며, 공개 포트는 443/8443/10000으로 제한되고 대역폭 제한이 있다. Funnel은 방문자를 인증해 주지 않으므로 위 Caddy 인증을 유지한다. Tailscale이 Funnel을 처음 활성화할 때 tailnet 정책에 Funnel 권한을 추가할 수 있다.

## 공식 근거

- Northflank forwarding: https://northflank.com/docs/v1/api/forwarding
- Northflank 네트워크/HTTPS: https://northflank.com/docs/v1/application/network/networking-on-northflank
- Northflank Tailscale 연결 방향·OAuth·전체 도메인: https://northflank.com/docs/v1/application/network/use-tailscale
- Northflank Sandbox: https://northflank.com/pricing
- Tailscale 요금·비상업용 조건: https://tailscale.com/pricing
- Tailscale Serve: https://tailscale.com/docs/reference/examples/serve
- Tailscale Funnel: https://tailscale.com/docs/features/tailscale-funnel
- Cloudflare Tunnel: https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/
- Quick Tunnel 제한: https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/do-more-with-tunnels/trycloudflare/
- Named Tunnel 설정: https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/get-started/create-remote-tunnel/
- Caddy 프록시: https://caddyserver.com/docs/caddyfile/directives/reverse_proxy
- Caddy 인증: https://caddyserver.com/docs/caddyfile/directives/basic_auth

## 배포 후 점검

로컬 `/health`, 태풍·호우·대설 화면의 업무 수, 두 재난의 풍수해 공통 11개 업무, 비인증 외부 요청의 401, 인증 후 외부 API의 200을 확인한다. Northflank를 선택하면 프록시 `/healthz`와 인증 후 `/api/disasters/snow/meta`를 모두 검사해야 Tailscale 원본 연결까지 확인할 수 있다. Funnel 주소는 tailnet 기기 이름을 유지하는 동안 고정된다. Quick Tunnel 주소는 컨테이너가 다시 만들어지면 바뀔 수 있으므로 로그에서 최신 주소를 확인한다.
