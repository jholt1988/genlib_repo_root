GenLib Backend

This directory contains the GenLib backend service, implemented with FastAPI.

The backend is a thin execution wrapper around the genlib CLI.
It does not contain generation logic, planning logic, or stack definitions.

Purpose

The backend exists to:

Expose GenLib functionality over HTTP

Run stack and agent jobs asynchronously

Provide job status and logs

Serve generated images from the filesystem

Act as a stable interface for UIs (Web, future clients)

The backend is intentionally minimal.

Design Principles

CLI is the source of truth

No prompt logic in the backend

No stack mutation

No database requirement

Filesystem is the contract

If the backend disappears, GenLib still works via CLI and TUI.

Architecture

FastAPI Backend
↓ (subprocess)
genlib CLI
↓
Forge (headless)
↓
outputs/ (filesystem)

Responsibilities

The backend is responsible for:

Accepting run requests

Enqueueing background jobs

Executing CLI commands asynchronously

Capturing stdout / stderr

Tracking job lifecycle

Exposing job state via HTTP

Serving /outputs/* as static files

The backend is not responsible for:

Planning

Validation

Orchestration logic

Prompt composition

Background Jobs

Jobs are executed using an in-process queue + worker thread.

Job lifecycle

queued → running → completed | failed

Each job has:

A unique job ID

A single output root

Captured stdout / stderr

Final execution status

This design avoids:

Celery

Redis

Message brokers

External infrastructure dependencies

API Endpoints
Health

GET /api/health

Stack execution (async)

POST /api/stacks/run

Returns:

{ "job_id": "abc123" }

Agent execution (async)

POST /api/agent/run

Returns:

{ "job_id": "def456" }

Job status

GET /api/jobs/{job_id}

Returns live job state:

{
"id": "abc123",
"status": "running",
"stdout": "...",
"stderr": "...",
"out": "outputs/..."
}

Gallery

GET /api/gallery?path=outputs/...

Returns image URLs relative to /outputs.

Static files

/outputs/*

Serves generated images directly from disk.

Configuration

Optional environment variables:

GENLIB_STACKS_DIR=stacks
GENLIB_OUTPUTS_ROOT=outputs

Defaults are safe for local usage.

Running the Backend

cd backend
pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 8000

Extending the Backend

Safe extensions:

Job persistence to disk

Worker pools

Authentication

Rate limiting

Unsafe extensions:

Prompt generation

Stack editing

Engine-specific logic

Summary

The backend is:

Intentionally boring

Easy to inspect

Easy to replace

Designed to stay out of the way

That is its job.

