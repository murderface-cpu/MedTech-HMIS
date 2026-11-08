# Database operations

All commands run from the repository root. `COMPOSE` stands for
`docker compose --env-file .env -f infra/compose/docker-compose.yml`.

## Start, stop, status

```bash
$COMPOSE up -d
$COMPOSE ps
$COMPOSE stop          # keeps the data
```

Data lives in the Docker volume `postgresql_medsafe_pgdata`. `stop` and `down` leave it in place.

## Open a SQL shell

```bash
docker exec -it medsafe-postgres psql -U medsafe -d medsafe
```

## Back up

```bash
docker exec medsafe-postgres pg_dump -U medsafe -d medsafe -Fc > medsafe-$(date +%Y%m%d-%H%M).dump
```

Keep backups out of the repository. They contain patient data.

## Restore

```bash
docker exec -i medsafe-postgres pg_restore -U medsafe -d medsafe --clean --if-exists < medsafe-YYYYMMDD-HHMM.dump
python manage.py migrate
```

## Reset (destroys all local data)

```bash
$COMPOSE down
docker volume rm postgresql_medsafe_pgdata
$COMPOSE up -d
python manage.py migrate
python manage.py createsuperuser
```

## Migrations

```bash
python manage.py makemigrations <app_label>   # after changing models
python manage.py migrate
python manage.py showmigrations                # what is applied
```

Rules:

- Every model change ships with its migration in the same change. CI fails otherwise.
- Data migrations provide a reverse function, or `migrations.RunPython.noop` when reversing is
  safe.
- Never edit a migration that has been applied in a shared environment. Add a new one.

## Production

Production backups need WAL archiving to meet the blueprint's 15-minute RPO, plus a restore drill
at least quarterly. This is not set up yet (see the traceability matrix).
