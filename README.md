# bpif-admin

An administrative tool for BPIF.

## Quick start (development)

Requires Docker with Compose.

```sh
cp .env.example .env
docker compose up --build
```

`docker compose up` applies `docker-compose.override.yml` automatically, which gives the development setup with hot
reload for both the backend and the frontend.

| URL                                    | What                                       |
| -------------------------------------- | ------------------------------------------ |
| http://localhost:5173                  | Frontend (Vite dev server, proxies `/api`) |
| http://localhost:8000/api/docs         | Backend OpenAPI docs                       |
| http://localhost:8000/api/v1/health    | Backend health check                       |
| `localhost:5432`                       | PostgreSQL (credentials from `.env`)       |

After changing `frontend/package.json`, run `docker compose up --build -V` so the `node_modules` volume is recreated.

## Production

```sh
docker compose -f docker-compose.yml -f docker-compose.production.yml up -d --build
```

Only nginx is published, on `FRONTEND_PORT` (default 8080). It serves the frontend and proxies `/api` to the backend.
