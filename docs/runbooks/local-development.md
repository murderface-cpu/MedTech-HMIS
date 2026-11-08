# Local development

## Prerequisites

- Python 3.11
- Docker Desktop (for PostgreSQL)
- Git

## 1. Configure the environment

```bash
cp .env.example .env
```

Edit `.env`:

- `DJANGO_KEY`: a long random string, for example
  `python -c "import secrets; print(secrets.token_urlsafe(50))"`.
- `DATABASE_PASSWORD`: any password. It is applied when the database volume is first created.
- `DEBUG="True"` for local work.
- `HOSPITAL_NAME`, `CURRENCY` and `TIME_ZONE` as needed. The examples use `KES` and
  `Africa/Nairobi`.

`.env` holds secrets and must never be committed (it is in `.gitignore`).

## 2. Start PostgreSQL

```bash
docker compose --env-file .env -f infra/compose/docker-compose.yml up -d
docker compose --env-file .env -f infra/compose/docker-compose.yml ps   # wait for "healthy"
```

The database listens on host port `DATABASE_PORT` (5433 by default). More detail is in
[database.md](database.md).

## 3. Install and migrate

```bash
python -m venv .venv
.venv/Scripts/activate            # Linux/macOS: source .venv/bin/activate
pip install -r requirements-dev.txt
python manage.py migrate
python manage.py createsuperuser
```

`migrate` also creates the module groups and default staff titles.

## 4. Run

```bash
python manage.py runserver
```

| URL | What |
| --- | --- |
| http://127.0.0.1:8000/ | Sign-in, then the first module you can access |
| http://127.0.0.1:8000/admin/ | Application administration: staff, titles, categories |
| http://127.0.0.1:8000/api/v1/ | API root (signed-in users) |
| http://127.0.0.1:8000/dashboard/ | Django admin for low-level data maintenance |

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| `password authentication failed for user "medsafe"` | The volume was created with a different password. Put that password in `.env`, or reset the database ([database.md](database.md)). |
| `connection refused` on port 5433 | The container is not running. Run `docker compose ... up -d` and check `ps`. |
| `container name "/medsafe-postgres" is already in use` | A container from another compose file has the same name. Stop it with `docker stop medsafe-postgres && docker rm medsafe-postgres`. The data volume is kept. |
| Static files return 404 with `DEBUG="False"` | Run `python manage.py collectstatic` and serve `STATIC_ROOT`, or use `DEBUG="True"` locally. |
