# Documentation

Index for the project report. Every claim in these documents is grounded
in the actual code and actual measured results in this repository (fraud
accuracy, load-test latencies, test counts) — none of it is projected or
estimated. Where something hasn't been done (e.g. Sepolia deployment),
that's stated plainly rather than implied.

| Document | Covers |
|---|---|
| [01_project_report.md](01_project_report.md) | Abstract, problem statement, objectives, literature survey, existing vs. proposed system, future scope, conclusion, references |
| [02_architecture_and_diagrams.md](02_architecture_and_diagrams.md) | Architecture diagram, DFD, ER diagram, sequence diagrams, use case diagram, class diagram, deployment diagram, flowcharts |
| [03_database_schema.md](03_database_schema.md) | All 13 tables, column-level notes, design rationale |
| [04_algorithms_and_pseudocode.md](04_algorithms_and_pseudocode.md) | Trust score formula, fraud detection pipeline, recommendation engine, dispute resolution — explained and in pseudocode |
| [05_testing_and_results.md](05_testing_and_results.md) | Testing strategy across all layers, and the actual measured results (not projections) |
| [screenshots/](screenshots/) | Screenshots of the running application, captured via an automated browser during actual verification (see `frontend/README.md`) |

## Where the source of truth actually lives

This documentation *describes* the system; it isn't the system's source
of truth for anything that has one closer to the code:

- Database schema: `database/schema.sql` (with `backend/app/models/` and
  the Alembic migrations mirroring it — see `backend/README.md`'s "Why
  this structure").
- API contract: `/docs` (FastAPI's auto-generated OpenAPI UI) once the
  backend is running, or `backend/README.md`'s API surface table.
- Design decisions and their reasoning: the "Design decisions worth
  knowing for a viva" sections in `backend/README.md` and
  `frontend/README.md` — there are more of those than fit comfortably
  here, and they're kept next to the code they explain so they can't
  drift out of sync with it.
