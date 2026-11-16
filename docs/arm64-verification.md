# Verification plan: Docker Compose, Caddy, PostgreSQL and Tesseract on ARM64 Linux

Target: Hetzner **CAX11** (ARM64 / aarch64, 2 vCPU, 4 GB RAM, 40 GB SSD), Ubuntu 24.04.

**Status: not executed.** Nothing in this file has been run on an ARM64 machine, and the
Docker stack has not been built or started at all since the changes of 2026-11-17 (the
workstation they were made on has no Docker). Until the table at the end is filled in
with real output, do not describe the ARM64 build, the Caddy configuration, the
PostgreSQL roles or the limits in `docker-compose.yml` as working.

What was checked without Docker (2026-11-17, Windows, Python 3.12, SQLite):

- pytest: the API protections in `tests/test_hardening.py`, the rest of the suite;
- the API under uvicorn: read-only mode forced by `DOCUMIND_WEB_BIND=0.0.0.0`, 413 for a
  20 MB question, validation errors without the input, `--limit-concurrency`,
  `--no-server-header`;
- `docker-compose.yml` parses as YAML and the log and memory settings are on the services
  they are meant for (a Python check, not `docker compose config`);
- the frontend tests and production build.

The steps below use **only synthetic text written for the test**. They do not need, fetch
or publish lex.uz documents, and they keep the site on `127.0.0.1` throughout.

## 0. Before touching the server

The server already runs a VPN. Docker changes the host's iptables rules and the stack
wants ports 80 and 443 (TCP) and 443 (UDP) for the public setup. Check first, change
nothing yet:

```bash
uname -m                                   # expected: aarch64
free -m && df -h /                         # expected: about 3.7 GB RAM, most of 40 GB free
sudo ss -tulpn | grep -E ':(80|443|8080|8443)\s'   # expected: no output
sudo iptables -S | head -40                # note the VPN's FORWARD / NAT rules
```

- If the VPN listens on 443 (TCP or UDP), the public setup of `docs/deploy.md` step 9b
  conflicts with it; decide on ports before going further.
- Docker sets the `FORWARD` chain policy to `DROP` and adds its own NAT rules. A VPN that
  forwards traffic through this host can stop working when Docker is installed. Take a
  Hetzner snapshot first, and keep a second SSH session open while installing Docker.
- Building the web image compiles Caddy with Go (about 1.5 GB of RAM). On 4 GB with the
  VPN running, check `free -m` before the build; add swap if less than 2 GB is free.

Record the outcome of every step in the table at the end.

## 1. Docker and the configuration

```bash
docker info --format '{{.Architecture}} {{.ServerVersion}}'   # expected: aarch64 ...
docker compose version                                        # Compose v2
cp .env.example .env && chmod 600 .env
# set POSTGRES_PASSWORD and DOCUMIND_API_DB_PASSWORD (openssl rand -hex 24); keep
# SITE_ADDRESS=:80 and WEB_BIND=127.0.0.1
docker compose config -q && echo "compose config OK"
docker compose config | grep -E 'max-size|max-file|mem_limit|cpus|pids_limit|DOCUMIND_WEB_BIND|DOCUMIND_SITE_ADDRESS'
```

Expected: `compose config OK`; `max-size: 10m` and `max-file: "5"` under every service;
`mem_limit` for postgres (768m), qdrant (512m), api (1536m) and web (256m);
`DOCUMIND_WEB_BIND: 127.0.0.1` and `DOCUMIND_SITE_ADDRESS: :80` in the `api` service.

## 2. Images for arm64

```bash
for image in postgres:17-trixie qdrant/qdrant:v1.19.2 python:3.12-slim-trixie \
             node:22-bookworm-slim caddy:2.11-builder-alpine caddy:2.11-alpine; do
  printf '%s: ' "$image"
  docker manifest inspect "$image" | grep -c '"architecture": "arm64"'
done
```

Expected: a count of at least 1 for every image. A `0` means that image has no arm64
build and the stack cannot run here as written.

The images published by `.github/workflows/release.yml` are built on an x86 runner
without a `platforms` setting, so they are **amd64 only** and will not run on CAX11.
Build on the server (next step).

## 3. Build

```bash
time docker compose build 2>&1 | tee build.log
docker image inspect documind-api documind-web --format '{{.RepoTags}} {{.Architecture}} {{.Size}}'
```

Expected: both builds finish; architecture `arm64`. What can go wrong on arm64, and what
it looks like:

- A Python dependency without an aarch64 wheel (candidates: `pymupdf`, `onnxruntime`,
  `tokenizers`, `psycopg[binary]`): pip falls back to compiling and fails, because the
  slim image has no compiler. The failing package is named in `build.log`.
- The Debian packages `tesseract-ocr-uzb`, `tesseract-ocr-uzb-cyrl`, `tesseract-ocr-rus`
  missing: the build stops at the `tesseract --list-langs | grep -qx uzb_cyrl` check.
  This apt step has never been run for this project on any architecture
  (`docs/decisions.md`).
- The Caddy build (`xcaddy`) killed for lack of memory: `signal: killed` in the log.

## 4. Tesseract in the API image

```bash
docker compose run --rm --no-deps ops tesseract --list-langs
docker compose run --rm --no-deps ops python - <<'PY'
from PIL import Image, ImageDraw
import pytesseract
img = Image.new("L", (1400, 300), 255)
ImageDraw.Draw(img).text((40, 100), "IJARA SHARTNOMASI 2026", fill=0, font_size=72)
print(repr(pytesseract.image_to_string(img, lang="uzb+uzb_cyrl+rus")))
PY
```

Expected: the list contains `uzb`, `uzb_cyrl` and `rus`; the second command prints text
that contains `IJARA SHARTNOMASI`.

## 5. Caddy configuration and the rate-limit plugin

```bash
docker compose run --rm --no-deps --entrypoint caddy web list-modules | grep rate_limit
docker compose run --rm --no-deps --entrypoint caddy web validate \
  --config /etc/caddy/Caddyfile --adapter caddyfile
```

Expected: `http.handlers.rate_limit` is listed; `Valid configuration`. The two
`request_body` blocks with matchers (16 KB for everything, 21 MB for the upload path)
were written without a Caddy binary to check them: this step is their first test.

## 6. PostgreSQL roles

```bash
docker compose up -d postgres
docker compose exec postgres psql -U documind -d documind -c '\du'
# ingest one synthetic document, written here for the test (as the owner role)
docker compose run --rm ops sh -c 'python - <<PY
import docx, pathlib
d = docx.Document()
for p in ["SINOV SHARTNOMASI (SYNTHETIC)", "1-modda. Ijara haqi",
          "Ijara haqi har oyning oʻninchi kunigacha toʻlanadi."]:
    d.add_paragraph(p)
pathlib.Path("/tmp/syn").mkdir()
d.save("/tmp/syn/sinov.docx")
PY
documind ingest /tmp/syn --synthetic --source synthetic-test && documind stats'
# the API role can read and cannot write
API_PW=$(grep '^DOCUMIND_API_DB_PASSWORD=' .env | cut -d= -f2)
docker compose exec -e PGPASSWORD="$API_PW" postgres psql -U documind_api -d documind \
  -c 'SELECT count(*) FROM chunks' -c 'DELETE FROM chunks'
```

Expected: roles `documind` and `documind_api`; ingest reports `"status": "ingested"` and
`"leaking_groups": []`; the `SELECT` returns `1`; the `DELETE` fails with
`permission denied for table chunks`.

(The ingest command was run on Windows against SQLite on 2026-11-17 and stored the
document as synthetic; it has not been run in the container.)

## 7. The stack, private mode

```bash
docker compose up -d
docker compose ps                                  # every service "healthy"
curl -s localhost:8080/api/health                  # "public_demo": false
curl -s -o /dev/null -w '%{http_code}\n' localhost:8080/            # 200 (the UI)
curl -s localhost:8080/api/ask -H 'content-type: application/json' \
  -d '{"question":"Ijara haqi qachon to‘lanadi?","corpus":"synthetic"}' | head -c 300
for c in postgres qdrant api web; do
  docker inspect "$(docker compose ps -q $c)" --format \
    "$c log={{.HostConfig.LogConfig.Config}} mem={{.HostConfig.Memory}} pids={{.HostConfig.PidsLimit}} oom={{.State.OOMKilled}}"
done
```

Expected: all healthy; an answer with a `quote` from the synthetic document; for every
service `log=map[max-file:5 max-size:10m]`, the memory limits of step 1 in bytes and
`oom=false`.

## 8. Request limits through Caddy

```bash
# 17 kB to /api/ask: refused by Caddy
head -c 17000 /dev/zero | tr '\0' a > /tmp/big.txt
curl -s -o /dev/null -w '%{http_code}\n' localhost:8080/api/ask \
  -H 'content-type: application/json' --data-binary @/tmp/big.txt          # 413
# a too long question: a short 422 that does not repeat the input
curl -s localhost:8080/api/ask -H 'content-type: application/json' \
  -d "{\"question\":\"$(head -c 1200 /tmp/big.txt)\"}" | wc -c             # under 200
# rate limit: the last answers are 429
for i in $(seq 25); do curl -s -o /dev/null -w '%{http_code} ' localhost:8080/api/ask \
  -H 'content-type: application/json' -d '{"question":"Ijara","corpus":"synthetic"}'; done; echo
# private mode on loopback: the API docs are on
curl -s -o /dev/null -w '%{http_code}\n' localhost:8080/api/openapi.json   # 200
```

## 9. Read-only mode, including the forgotten flag

Still on `127.0.0.1`. In `.env` set `SITE_ADDRESS=http://demo.invalid` and leave
`DOCUMIND_PUBLIC_DEMO=false` and `WEB_BIND=127.0.0.1` (the `http://` prefix keeps Caddy
from asking for a certificate; `.invalid` never resolves). Then:

```bash
docker compose up -d
docker compose logs api | grep 'DOCUMIND_PUBLIC_DEMO is not set'            # the warning
H='Host: demo.invalid'
curl -s -H "$H" localhost:8080/api/health                                   # "public_demo": true
curl -s -o /dev/null -w '%{http_code}\n' -H "$H" -X POST localhost:8080/api/documents/upload   # 403
curl -s -o /dev/null -w '%{http_code}\n' -H "$H" localhost:8080/api/openapi.json               # 404
curl -s -o /dev/null -w '%{http_code}\n' -H "$H" localhost:8080/api/docs                       # 404
```

Then set `DOCUMIND_PUBLIC_DEMO=true`, `SITE_ADDRESS=:80`, `docker compose up -d`, and
repeat the four `curl` commands without the `Host` header: same results.

Do **not** test `WEB_BIND=0.0.0.0` on this server as part of this plan: that publishes
the site.

## 10. Restarts and memory

```bash
docker compose restart postgres && sleep 15
for i in 1 2 3; do curl -s -o /dev/null -w '%{http_code} ' localhost:8080/api/health; done; echo   # 200 200 200
docker compose restart api && sleep 25 && docker compose ps api            # healthy
sudo reboot        # then, after logging in again:
docker compose ps  # every service up and healthy without any command
docker stats --no-stream
free -m
```

Expected: no 500 after the PostgreSQL restart (`pool_pre_ping`); the stack returns after
a reboot (`restart: unless-stopped`); the API well under its memory limit with the
default `bm25` retriever; the VPN still works after the reboot.

If `DOCUMIND_API_RETRIEVER=hybrid` is planned, repeat steps 7 and 10 with it after
`scripts/download_model.py`: the ONNX model is loaded into the API process, and
whether it fits into 1536 MB next to the other services on 4 GB has not been measured.

## 11. Clean up the test data

```bash
docker compose down            # keeps the volumes
# to drop the synthetic test document as well (this deletes the database volume):
# docker compose down -v
```

## Results

| Step | Date | Result (pass / fail / not run) | Notes |
|---|---|---|---|
| 0 Ports, iptables, memory | | not run | |
| 1 Compose configuration | | not run | |
| 2 arm64 images | | not run | |
| 3 Build | | not run | |
| 4 Tesseract | | not run | |
| 5 Caddy validate, rate-limit module | | not run | |
| 6 PostgreSQL roles | | not run | |
| 7 Stack healthy, log and memory limits applied | | not run | |
| 8 413 / 422 / 429 through Caddy | | not run | |
| 9 Read-only mode, forgotten flag | | not run | |
| 10 Restarts, reboot, memory | | not run | |
