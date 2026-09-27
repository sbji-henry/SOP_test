"""Deploy only the HTTPS proxy. Secrets stay in .secrets; never print payloads."""
import argparse
import base64
import json
from pathlib import Path
import urllib.request
import urllib.error

ROOT = Path(__file__).resolve().parents[1]
PROJECT = 'sop-pc-origin'
ORIGIN = 'home-pc.tail9bc174.ts.net'
IMAGE = 'caddy@sha256:6aeddd44c3078b0f9a35206472a11420648a79c184603ef95957d0a20044cb2b'


def service_payload(plan, env):
    config = (ROOT / 'deploy/northflank/Caddyfile').read_bytes()
    # Copying the binary drops image file capabilities, allowing restricted runtimes.
    command = "sh -c 'printf %s \"$CADDY_CONFIG_B64\" | base64 -d > /tmp/SOP-Caddyfile && cp /usr/bin/caddy /tmp/sop-caddy && exec /tmp/sop-caddy run --config /tmp/SOP-Caddyfile --adapter caddyfile'"
    return {
        'name': 'sop-edge',
        'description': 'Authenticated HTTPS proxy to SOP on local PC via Tailscale',
        'billing': {'deploymentPlan': plan},
        'deployment': {'instances': 1, 'external': {'imagePath': IMAGE},
                       'docker': {'configType': 'customCommand', 'customCommand': command}},
        'runtimeEnvironment': {**env, 'ORIGIN_HOST': ORIGIN,
                               'CADDY_CONFIG_B64': base64.b64encode(config).decode()},
        'ports': [{'name': 'http', 'internalPort': 8080, 'public': True, 'protocol': 'HTTP'}],
        'healthChecks': [{'protocol': 'HTTP', 'type': 'readinessProbe', 'path': '/healthz',
                         'port': 8080, 'initialDelaySeconds': 10, 'periodSeconds': 10,
                         'timeoutSeconds': 3, 'failureThreshold': 3}],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--plan', required=True, help='Account-verified deployment plan ID')
    parser.add_argument('--apply', action='store_true', help='Actually create the service')
    args = parser.parse_args()
    secret_dir = ROOT / '.secrets'
    token = (secret_dir / 'northflank-token.txt').read_text(encoding='utf-8-sig').strip()
    oauth = json.loads((secret_dir / 'tailscale-oauth.json').read_text(encoding='utf-8-sig'))
    if not all(oauth.get(k) for k in ['clientId', 'clientSecret']):
        raise SystemExit('Tailscale clientId and clientSecret are required.')
    env = dict(line.split('=', 1) for line in (secret_dir / 'gateway.env').read_text().splitlines() if '=' in line)
    body = service_payload(args.plan, env)
    if not args.apply:
        print('Ready to deploy sop-edge. No API writes performed. Check account free-plan eligibility before --apply.')
        return

    def api(method, path, data=None):
        req = urllib.request.Request('https://api.northflank.com/v1/' + path,
            data=None if data is None else json.dumps(data).encode(), method=method,
            headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(req, timeout=45) as response:
                return json.load(response)['data']
        except urllib.error.HTTPError as error:
            raise SystemExit(f'Northflank {method} {path}: HTTP {error.code}; response suppressed to protect secrets.')

    services = api('GET', f'projects/{PROJECT}/services')['services']
    if any(s['id'] == 'sop-edge' for s in services):
        raise SystemExit('sop-edge already exists; inspect it before changing or retrying.')
    project = api('GET', f'projects/{PROJECT}')
    network = project.get('networking', {})
    network['tailscale'] = {
        'enabled': True, 'authKeyTags': ['tag:northflank-sop'],
        'restrictions': {'enabled': False},
        'options': {'applyToAddons': False, 'applyToAddonJobs': False, 'autoRedeployOnRegeneration': True},
        'tailscaleOptions': {'acceptRoutes': False},
        'secrets': {'clientId': oauth['clientId'], 'clientSecret': oauth['clientSecret']},
    }
    api('PATCH', f'projects/{PROJECT}', {'networking': network})
    result = api('POST', f'projects/{PROJECT}/services/deployment', body)
    print('Created service:', result['id'])
    print('Verify deployment, public HTTPS authentication, and origin reachability before reporting success.')


if __name__ == '__main__':
    main()
