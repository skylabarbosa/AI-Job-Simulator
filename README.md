# SkillUp / AI Job Simulator

## Current product foundation (Phase 5.5)

SkillUp / AI Job Simulator is a project-agnostic workplace learning platform.
Business users create a draft project, upload private CSV resources, generate
or revise a blueprint, approve it, materialize the exact approved version, and
publish the resulting immutable runtime release. Learners discover published
projects, start required tasks, submit work, and receive deterministic and,
when needed, Gemini-assisted evaluation. Progress is evidence-based; adaptive
decisions change presentation support only, never the required project path.

Supported canonical task types are `analysis`, `sql`, `data_cleaning`,
`communication`, and `other`. `data_cleaning` flows from blueprint generation
through runtime routing to `DataCleaningEvaluator` without title-based logic.

### Lifecycle and safety

- Draft project data and draft blueprints are editable.
- Approved blueprints are immutable. A change begins with a new revision.
- Materialization creates a `project_release` explicitly tied to one approved
  blueprint ID. Runtime modules and tasks are append-only per release.
- Publishing accepts only the release materialized from the exact blueprint
  being published. Published datasets and runtime definitions cannot be
  changed in place.
- Existing historical records are not guessed or rewritten by the release
  migration. They remain readable as legacy releases.

The backend uses Supabase's service-role client only behind authenticated,
role-checked, ownership-scoped APIs. Do not expose the service-role key to the
frontend. Dataset storage uses the private `project-datasets` bucket and the
API authorizes project access before issuing a ten-minute signed URL.

### Configuration

Copy the example files and set values locally. Required backend values are
`SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY`; Gemini is optional for
deterministic evaluation and needs `LLM_API_KEY` only for generation/semantic
review. Production must set `APP_ENV=production` and explicit comma-separated
HTTPS `CORS_ORIGINS`; wildcards are rejected while credentials are enabled.
`LLM_TIMEOUT_SECONDS` and `LLM_MAX_REQUESTS_PER_MINUTE` provide bounded
provider calls and a process-level cost guard.

### Verification

Run backend tests from an environment with `pytest` installed:

```powershell
Set-Location backend
python -m pytest -q
```

Run frontend checks:

```powershell
Set-Location frontend
npm.cmd test -- --run
npm.cmd run lint
npm.cmd run build
```

Hosted verifiers live in `backend/scripts/live_verification/`. They create
temporary records and clean them up, but refuse to run unless
`SKILLUP_RUN_LIVE_VERIFICATION=yes` is explicitly set. The revision example
also requires `SKILLUP_VERIFICATION_PROJECT_ID`; never point it at a real demo
or production project.

AI Job Simulator is an AI-powered workplace simulation and adaptive learning platform. The platform is designed to remain project-agnostic: businesses provide workplace context, datasets, tasks, and rubrics, while the platform handles simulation, validation, evaluation, skill modeling, and adaptive learning.

## Project Structure

```text
AI-Job-Simulator/
├── backend/
│   ├── app/
│   │   ├── api/       # FastAPI routers
│   │   ├── core/      # Configuration and shared concerns
│   │   ├── db/        # Server-side Supabase client boundary
│   │   └── schemas/   # Pydantic schemas
│   └── main.py        # FastAPI application entry point
├── supabase/
│   └── migrations/    # Versioned PostgreSQL migrations
└── frontend/
    └── src/
        ├── pages/     # Page-level views
        ├── routes/    # React Router composition
        ├── services/  # API communication
        └── types/     # Shared frontend types
```

## Technology Stack

Frontend: React, Vite, TypeScript, Tailwind CSS v4, shadcn/ui, React Router, React Hook Form, Zod, Recharts, and Lucide icons.

Backend: FastAPI, Python, and Pydantic.

## Setup

Create local environment files from the examples when needed:

```powershell
Copy-Item backend/.env.example backend/.env
Copy-Item frontend/.env.example frontend/.env
```

No real secrets belong in these files or in source control.

### Supabase setup

Phase 2 requires a Supabase project for applying the database migration. The
backend reads `SUPABASE_URL` and the server-only `SUPABASE_SERVICE_ROLE_KEY`.
The frontend may later use only `VITE_SUPABASE_URL` and
`VITE_SUPABASE_PUBLISHABLE_KEY`; never put the service-role key in a Vite
environment variable or frontend source.

Install backend dependencies before using the server-side database boundary:

```powershell
Set-Location backend
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Apply the versioned migration with the Supabase CLI from the repository root:

```powershell
supabase link --project-ref <your-project-ref>
supabase db push
```

The migration creates a project-agnostic schema for users, projects, datasets,
modules, competencies, concepts, tasks, task mappings, rubrics, simulations,
submissions, evaluations, and user skills. Uploaded CSV files belong in
Supabase Storage; the `datasets` table stores their project relationship and
metadata rather than CSV contents.

Row Level Security is enabled on every Phase 2 table with no permissive public
policies. Phase 3 must add policies based on Supabase Auth identities before
authenticated application access is enabled.

### Start the backend

```powershell
Set-Location backend
.\venv\Scripts\Activate.ps1
uvicorn main:app --reload
```

The backend is available at `http://localhost:8000`. The Phase 1 health endpoint is `GET /api/health`.

### Start the frontend

In a second terminal:

```powershell
Set-Location frontend
npm run dev
```

The frontend is available at `http://localhost:5173/`.

### Deployment

Deploy the Vite frontend to Vercel with the `frontend` directory as the project
root and set `VITE_API_BASE_URL`, `VITE_SUPABASE_URL`, and
`VITE_SUPABASE_PUBLISHABLE_KEY`. Deploy the FastAPI backend to Render with
`backend` as the root directory and `uvicorn main:app --host 0.0.0.0 --port
$PORT` as the start command; use `/api/health` for the health check. Set
`APP_ENV=production`, explicit HTTPS `CORS_ORIGINS` without trailing slashes,
the backend Supabase service-role credentials, and the backend-only Gemini key
in Render. Database, Auth, and Storage are provided by Supabase; Gemini is
backend-only.

## Phase 1 Status

Phase 1 establishes the project foundation only:

- scalable FastAPI package structure
- typed backend health endpoint
- React Router route foundation
- typed frontend API service boundary
- minimal professional landing page
- environment examples and repository ignore rules

## Phase 2 Status

Phase 2 establishes the database and Supabase foundation only:

- versioned, project-agnostic PostgreSQL migration
- relational tables, foreign keys, indexes, constraints, and timestamps
- RLS enabled as a closed foundation pending Phase 3 authorization policies
- server-only backend Supabase configuration boundary
- frontend-safe Supabase configuration boundary

Authentication, authorization policies, CRUD APIs, project management UI,
dataset upload UI, SQL execution, AI evaluation, skill calculations, and
adaptive learning are not implemented yet.

## Phase 3 Status

Phase 3 establishes authentication and authorization foundations only:

- Supabase Auth sign-up, sign-in, sign-out, session restoration, and auth state handling
- application profiles linked to `auth.users` through `public.users`
- validated `learner`, `business`, and `admin` application roles
- protected frontend routes and a minimal role-restricted route
- reusable FastAPI bearer-token, profile, and role dependencies
- least-privilege RLS policies based on `auth.uid()` and actual project relationships

Public signup can create learner or business profiles. It cannot create admin
profiles; admin access requires a secure server-side or Supabase administrative
operation. The Phase 3 migration is
`supabase/migrations/20260915010000_phase3_auth_roles_rls.sql` and should be
applied after the Phase 2 migration.

Live authentication and RLS behavior require configured Supabase credentials.
The local frontend and backend can still build and start without credentials,
but authenticated operations will report that Supabase is not configured.
