# 0002. PostgreSQL as the system of record

- Status: accepted
- Date: 2026-10-30

## Context

Clinical and financial records need transactional integrity, concurrent access and point-in-time
recovery (the blueprint targets RPO 15 minutes and RTO 4 hours).

## Decision

Use PostgreSQL 16 for all environments, including tests. Connection settings come only from
environment variables (`DATABASE_*`). For local development the database runs in Docker using
`infra/compose/docker-compose.yml`. CI starts the same image as a service container.

## Consequences

- Tests exercise the same database engine as production, so engine-specific behaviour such as
  sequences, constraints and locking is covered.
- Developers need Docker (or a local PostgreSQL install).
- Backups, WAL archiving and restore drills are operational work still to do. They are tracked in
  the traceability matrix under the non-functional requirements.
