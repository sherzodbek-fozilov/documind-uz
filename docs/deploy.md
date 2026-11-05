# Deployment on a Hetzner Ubuntu server

Step-by-step instructions for running DocuMind UZ with Docker Compose on one CPU-only
Hetzner Cloud server, either privately (only reachable through an SSH tunnel) or as a
**public demo** with HTTPS. Nothing in this repository deploys anything by itself: every
step below is run by hand on the server.

| Service | Image | Published |
|---|---|---|
| `web` | `deploy/web/Dockerfile`: the built frontend served by Caddy, which also proxies `/api/*` to the API, applies per-IP rate limits and, for a domain name, gets the HTTPS certificate | ports 80 / 443 (by default only on 127.0.0.1) |
| `api` | `Dockerfile`: FastAPI + uvicorn, tesseract `uzb`, `uzb_cyrl`, `rus`, non-root user, read-only root file system | no |
| `postgres` | `postgres:17-trixie` | no |
| `qdrant` | `qdrant/qdrant:v1.19.2` (only used with `DOCUMIND_API_RETRIEVER=hybrid`) | no |
| `ops` | the API image, for one-off jobs (model download, fetching documents, ingest); never started by `docker compose up` | no |

Data lives in named Docker volumes (`pgdata`, `qdrant`, `models`, `raw`, `store`, `cache`,
`user_store`, `caddy_data`, `caddy_config`). Model weights and lex.uz documents are
fetched **on the server**; they are never part of an image or of the repository.

> **Before making the demo public:** the lex.uz pages state no license and nothing about
> copying (see `docs/data.md`). A public demo shows quotes of that text to anyone, which is
> a form of redistribution that this project has so far avoided (`docs/decisions.md`).
> Decide this, and record the decision in `docs/decisions.md`, before setting a domain
> name. Until then, use the private setup (step 9a).

## 1. Server

- Hetzner Cloud, **Ubuntu 24.04**, x86 or Arm. 2 vCPU / 4 GB RAM is enough for BM25; for `hybrid` (e5 embeddings, Qdrant) take 4 GB or more. Building the
  web image compiles Caddy with Go and needs about 1.5 GB of free RAM.
- Add your SSH key when creating the server. Optional but recommended: a Hetzner Cloud
  Firewall that allows only TCP 22, 80, 443 and UDP 443 inbound.
- For HTTPS: a domain name with an `A` record (and `AAAA` for IPv6) pointing at the
  server, set **before** step 9b (Caddy asks Let's Encrypt for a certificate on start).

## 2. Base setup (as root, once)

```bash
apt-get update && apt-get -y upgrade
apt-get install -y unattended-upgrades ufw git
adduser --disabled-password --gecos "" deploy
usermod -aG sudo deploy
mkdir -p /home/deploy/.ssh && cp ~/.ssh/authorized_keys /home/deploy/.ssh/
chown -R deploy:deploy /home/deploy/.ssh && chmod 700 /home/deploy/.ssh
passwd deploy        # sudo password for the deploy user
```

SSH: key login only. In `/etc/ssh/sshd_config` set `PasswordAuthentication no` and
`PermitRootLogin no`, then `systemctl restart ssh`, and check in a **second** terminal
that `ssh deploy@<server>` still works before closing the first.

Firewall:

```bash
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow 443/udp
ufw enable
```

Note: ports published by Docker bypass ufw. That is why only the `web` service publishes
ports, and why the Hetzner Cloud Firewall is the more reliable second layer.

## 3. Docker Engine and the Compose plugin

From Docker's own apt repository (the Ubuntu `docker.io` package has no Compose v2):

```bash
sudo apt-get install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin \
  docker-compose-plugin
sudo usermod -aG docker deploy     # log out and in again
docker compose version
```

## 4. Code

As `deploy`:

```bash
git clone https://github.com/sherzodbek-fozilov/documind-uz.git
cd documind-uz
git checkout <commit or tag to deploy>
```

## 5. Settings

```bash
cp .env.example .env
chmod 600 .env
openssl rand -hex 24     # run twice: one value per password
```

In `.env` set at least:

| Variable | Value |
|---|---|
| `POSTGRES_PASSWORD` | random (owner of the main database; used only by the `ops` jobs) |
| `DOCUMIND_API_DB_PASSWORD` | another random value (role `documind_api`: SELECT only on the main database, owner of the uploads database) |
| `DOCUMIND_ANSWER_MODE` | keep `extractive` (no LLM key, no cost) |
| `DOCUMIND_API_RETRIEVER` | `bm25` (no model needed) or `hybrid` (needs step 6) |

The database and Qdrant URLs in `.env` are for local development; `docker-compose.yml`
replaces them inside the containers. Secrets are only ever read from `.env` at run time:
`.dockerignore` keeps `.env` out of every image, and the API container gets an empty
`POSTGRES_PASSWORD`.

Build both images (the web image compiles Caddy with the rate-limit plugin; a few
minutes):

```bash
docker compose build
docker compose run --rm ops tesseract --list-langs    # must list uzb, uzb_cyrl, rus
```

## 6. Embedding model (only for `hybrid`)

```bash
docker compose run --rm ops python scripts/download_model.py
```

This downloads the ONNX files of `intfloat/multilingual-e5-small` (MIT license, about
470 MB) from Hugging Face, **pinned to the revision in `scripts/download_model.py`**, into
the `models` volume, together with a `SOURCE.json` that records the repository and
revision. Run it once; it is not needed for the default `bm25` retriever. A fine-tuned
model (stage 5) would go into the same volume (`/app/models/<name>`) and be selected
with `DOCUMIND_EMBED_MODEL_DIR`.

## 7. lex.uz documents (polite mode)

```bash
docker compose run --rm ops python scripts/fetch_sources.py --keep-registry --delay 30
```

What this does, and why it is polite:

- Only entries of `data/sources.json` with `terms.status == "approved"` (and a recorded
  license and checker) are fetched; everything else is skipped. Today these are the four
  lex.uz pages (Civil Code part 2 and Labor Code 2022, ru and uz-Latn).
- `robots.txt` of the host is read first and respected; a disallowed URL is skipped.
- Requests are made **one at a time**, with at least `--delay` seconds between them
  (default 10; 30 above), and a User-Agent that names the project and links to the
  repository. In total that is one robots.txt request and four page downloads.
- Run it **once**, at a quiet hour for the site (e.g. late evening in Tashkent, UTC+5),
  and do not put it on a schedule. Re-run only when you deliberately want a newer
  edition; the log prints `content changed since last fetch` when a page differs from
  the sha256 recorded in the repository.
- `--keep-registry` writes only to the `raw` volume (the documents and
  `manifest.jsonl`); `data/sources.json` and `docs/data.md` in the image stay as
  committed. The editions shown in the log may be newer than the ones in the repository:
  then the corpus on the server differs from the one the results in the README were
  measured on (chunk ids, frozen eval set v1). Record the edition you serve.

Nothing from `data/raw` is committed: the documents stay in the `raw` volume.

## 8. Ingest

```bash
docker compose run --rm ops documind ingest data/raw
docker compose run --rm ops documind stats        # "leaking_groups": [] is required
```

Ingest applies the **committed** train/test split (`data/splits.json` in the image). Do not
run `documind split` on the server. Ingest runs as the database owner; the API later
connects as `documind_api`, which can only read these tables.

## 9a. Start: private (default)

With the defaults in `.env` (`SITE_ADDRESS=:80`, `WEB_BIND=127.0.0.1`), the site is only
reachable from the server itself, on port 8080, over plain HTTP:

```bash
docker compose up -d
docker compose ps                 # all services "healthy"
curl -s localhost:8080/api/health
```

From your computer, through an SSH tunnel:

```bash
ssh -L 8080:127.0.0.1:8080 deploy@<server>
```

then open <http://localhost:8080>. Uploads work in this mode (they go to the separate
`documind_user` database); remember that uploaded files are parsed inside the API
process (`docs/decisions.md`).

## 9b. Start: public demo

In `.env`:

```bash
DOCUMIND_PUBLIC_DEMO=true
SITE_ADDRESS=demo.example.org     # your domain; its DNS record must already point here
WEB_BIND=0.0.0.0
WEB_HTTP_PORT=80
WEB_HTTPS_PORT=443
```

Then:

```bash
docker compose up -d
docker compose logs -f web        # wait for "certificate obtained successfully"
```

What the demo mode changes:

- `POST /api/documents/upload` answers **403** without reading the request body, and
  there is no user corpus (`"corpus": "user"` answers 503).
- The main database is opened **read-only** (every PostgreSQL transaction is
  `READ ONLY`), on top of the `documind_api` role that has only SELECT rights.
- Caddy serves HTTPS with a Let's Encrypt certificate (renewed automatically, stored in
  the `caddy_data` volume), redirects HTTP to HTTPS and sends security headers.
- Rate limits per client IP (`.env`, enforced by Caddy, **429** with `Retry-After`):
  `RATE_LIMIT_ASK_PER_MINUTE` (20) for `/api/ask`, `RATE_LIMIT_UPLOAD_PER_HOUR` (10),
  `RATE_LIMIT_ALL_PER_MINUTE` (300) for everything together.

Checks:

```bash
curl -s https://demo.example.org/api/health          # "public_demo": true
curl -s -o /dev/null -w "%{http_code}\n" -X POST https://demo.example.org/api/documents/upload
                                                     # 403
for i in $(seq 25); do curl -s -o /dev/null -w "%{http_code} " \
  -H 'content-type: application/json' -d '{"question":"Ijara haqi"}' \
  https://demo.example.org/api/ask; done; echo       # the last ones are 429
docker compose logs web | grep -o '"remote_ip":"[^"]*"' | sort | uniq -c
```

The last command must show the **visitors' addresses**. If every request shows a
`172.x.x.x` address, Caddy sees Docker's gateway instead of the client, and the per-IP
limit acts as one global limit. With Docker's default iptables setup, external traffic
keeps its source address (requests made from the server itself, e.g. through the SSH
tunnel, show the gateway; that is expected). Do not put another proxy or a load balancer
in front of Caddy without changing the rate-limit key.

## 10. Operations

Update to a new version:

```bash
git fetch && git checkout <new commit or tag>
docker compose build
docker compose up -d
```

New or re-fetched documents: run steps 7 and 8 again, then
`docker compose restart api` (the API builds its search index once per process).

Logs: `docker compose logs -f api web`. Disk: `docker system df`; remove old images with
`docker image prune`.

Backups (the documents in `raw` can be fetched again; the databases cannot be rebuilt
without them):

```bash
docker compose exec -T postgres pg_dump -U documind -d documind -Fc > documind-$(date +%F).dump
docker compose exec -T postgres pg_dump -U documind -d documind_user -Fc > documind_user-$(date +%F).dump
```

Copy the dumps off the server (the Hetzner server backup option covers the whole disk
as well).

Change a password after the first start (the init script runs only on an empty volume):

```bash
docker compose exec postgres psql -U documind -d documind \
  -c "ALTER ROLE documind_api PASSWORD '<new value>'"
```

then update `.env` and `docker compose up -d`.

## Not covered yet

- No user accounts or authentication: the public demo is anonymous and read-only.
- LLM mode (`DOCUMIND_ANSWER_MODE=llm`) has no budget guard yet (`docs/issues.md`); keep
  the demo extractive.
- Uploads are parsed inside the API process, not in a sandbox; they stay disabled in the
  public demo.
- The UI is only a placeholder page until stage 4 is finished; until then the demo is
  used through the API (`/api/ask`, `/api/documents`, `/api/health`). FastAPI's
  interactive docs (`/docs`) are not reachable through Caddy: they expect to be served at
  the root and load scripts from a CDN, which the Content-Security-Policy blocks.
