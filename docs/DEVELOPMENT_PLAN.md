# SocialStack — Development Plan & Progress

**Product:** SocialStack — standalone Python social media content automation platform  
**Purpose:** Replace 12 n8n workflows with a production-grade FastAPI + Celery product that can later be embedded into SuperOne CRM as an adapter module  
**Timeline:** 4 days (started 2026-06-15)

---

## Architecture Overview

```
HTTP Client (SuperOne CRM / any REST consumer)
        │
        ▼
  FastAPI REST API  (32 routes, /v1/*)
        │
        ├── dispatches tasks ──►  Celery Workers
        │                         ├── worker-default   (generation, orchestration)
        │                         ├── worker-images    (AI image generation, concurrency=2)
        │                         ├── worker-publishing (platform publish, concurrency=8)
        │                         └── worker-metrics   (analytics collection, concurrency=2)
        │
        ├── PostgreSQL (own schema, via asyncpg + SQLAlchemy 2.0 async)
        └── Redis (Celery broker + Beat scheduler + idempotency keys + publish locks)
```

**Key principle:** SocialStack owns its own database, auth, and scheduling. No coupling to Welvom/SuperOne API during this build phase — integration happens later as an adapter layer that reads/writes through SocialStack's own API.

**AI layer:** Model-agnostic via `AIClient` Protocol in `ai/client.py`. Provider + model selected from env vars (`AI_PROVIDER`, `AI_CHAT_MODEL`, `AI_IMAGE_MODEL`). Services never import provider-specific code.

---

## Codebase Layout

```
Social Stack/
├── docs/                           ← this folder
├── workflows_new/                  ← 12 original n8n workflow JSON exports
└── socialstack/
    ├── pyproject.toml
    ├── Makefile
    ├── Dockerfile
    ├── docker-compose.yml          (8 services: postgres, redis, api, 4 workers, beat, flower)
    ├── docker-compose.prod.yml
    ├── .env.example
    ├── alembic/                    (async migrations)
    └── src/socialstack/
        ├── config.py               (pydantic-settings, @lru_cache)
        ├── app.py                  (FastAPI factory, lifespan, CORS, error handlers)
        ├── main.py                 (uvicorn entrypoint)
        ├── celery_app.py           (4 queues, Beat CRON, redbeat scheduler)
        ├── dependencies.py
        ├── db/
        │   ├── base.py
        │   ├── session.py
        │   └── models/             (9 ORM models → source of truth for schema)
        ├── repositories/           (8 async data-access classes)
        ├── schemas/                (Pydantic v2 request/response)
        ├── middleware/
        │   ├── auth.py             (API key via X-API-Key header)
        │   └── logging.py          (request_id injection via structlog)
        ├── api/v1/                 (9 routers, 32 endpoints total)
        ├── ai/                     (AIClient Protocol, OpenAI provider, Anthropic stub)
        ├── services/               (12 service classes — business logic)
        ├── publishers/             (4 platform HTTP clients)
        ├── prompts/                (6 AI prompt template modules)
        ├── platform_rules/         (per-platform char limits, hashtag rules)
        ├── tasks/                  (5 Celery task modules)
        └── utils/                  (encryption, idempotency, retry, logging, storage, errors)

tests/
├── conftest.py                     (MockAIClient, test fixtures)
├── unit/
│   ├── platform_rules/
│   └── services/
├── integration/                    (empty — Day 2 target)
└── e2e/
```

---

## Database Schema

```
businesses              id, name, industry, timezone, compliance_tier
business_preferences    id, business_id, brand_tone, pain_points[], ai_generate_images, auto_approve, tier
social_platform_connections  id, business_id, platform, account_name, platform_account_id,
                             access_token_enc (Fernet-encrypted), is_active

calendars               id, business_id, month, year, status
calendar_days           id, calendar_id, date, day_number, theme, objective, post_idea

content_slots           id, calendar_id, calendar_day_id, business_id, platform, status,
                        scheduled_at, published_at
                        status flow: draft → pending_brief → pending_caption
                                  → pending_review → approved → published | failed
content_briefs          id, slot_id, business_id, hook, key_message, emotional_angle,
                        visual_direction, cta
content_variants        id, slot_id, business_id, platform, caption, hashtags[], char_count,
                        version, brief_id
content_feedback        id, slot_id, variant_id, business_id, feedback
media_assets            id, business_id, variant_id, storage_url, asset_type, ai_prompt

publish_events          id, slot_id, variant_id, business_id, platform, platform_post_id,
                        permalink, status, published_at
post_metrics            id, publish_event_id, platform, impressions, reach, likes, comments,
                        saves, shares, engagement_rate, collected_at

workflow_runs           id, workflow, business_id, trigger_kind, status, started_at,
                        finished_at, input jsonb, output jsonb, error jsonb
notifications           id, business_id, type, payload jsonb, sent_at, status
```

---

## n8n Workflow → Python Mapping

| n8n Workflow | Python Equivalent | Status |
|---|---|---|
| WF-CAL_Calendar_Theme_Generator | `services/calendar_service.py` + `prompts/calendar_prompt.py` | Implemented |
| WF-BRIEF_Content_Brief_Generator | `services/brief_service.py` + `prompts/brief_prompt.py` | Implemented |
| WF-CAPTION_Platform_Caption_Generator | `services/caption_service.py` + `prompts/caption_prompt.py` | Implemented |
| WF-ASSET_Image_Generator | `services/asset_service.py` + `prompts/image_prompt.py` | Implemented |
| WF-GENORCH_Generation_Orchestrator | `services/generation_service.py` | Implemented |
| WF-MVAR_Multi_Variant_Generator | `services/variant_service.py` + `prompts/multi_variant_prompt.py` | Implemented |
| WF-REGEN_Regeneration_Workflow | `services/regeneration_service.py` + `prompts/regen_prompt.py` | Implemented |
| WF-PUBLISH_Platform_Publisher | `services/publish_service.py` + `publishers/*` | Implemented |
| WF-PUBORCH_Publish_Orchestrator | `tasks/publish_tasks.publish_orchestrator_task` (Beat, every 5 min) | Implemented |
| WF-METRICS_Metrics_Collector | `services/metrics_service.py` + `tasks/metrics_tasks.py` (Beat, every 6h) | **Partial** — platform API calls stubbed |
| WF-ERROR_Error_Handler | `utils/errors.py` + exception handlers in `app.py` | Implemented |
| WF-NOTIFY_Notification_Workflow | `services/notification_service.py` | **Partial** — delivery channel stubbed |

---

## Day 1 — Complete (2026-06-15)

### What was built

**Infrastructure & Config**
- `pyproject.toml` — all deps (FastAPI, Celery, SQLAlchemy async, OpenAI, Anthropic, tenacity, structlog, cryptography, redbeat, etc.)
- `Dockerfile` — single image, CMD overridden per service in compose
- `docker-compose.yml` — 8 services: postgres:16, redis:7, api, worker-default, worker-images, worker-publishing, worker-metrics, beat, flower (dev profile)
- `docker-compose.prod.yml` — resource limits, no --reload, healthchecks
- `Makefile` — `dev`, `test`, `lint`, `migrate`, `prod` targets
- `.env.example` — all env vars documented
- `alembic/env.py` — async alembic setup importing all models for auto-detection

**Database Layer**
- `db/base.py` — SQLAlchemy declarative base with `id` (UUID), `created_at`, `updated_at`
- `db/session.py` — `async_sessionmaker`, `get_db` FastAPI dependency
- 9 ORM models: `Business`, `BusinessPreferences`, `SocialPlatformConnection`, `Calendar`, `CalendarDay`, `ContentSlot`, `ContentBrief`, `ContentVariant`, `ContentFeedback`, `MediaAsset`, `PublishEvent`, `PostMetrics`, `WorkflowRun`, `Notification`
- 8 repositories: `BusinessRepository`, `CalendarRepository`, `ContentSlotRepository`, `ContentBriefRepository`, `ContentVariantRepository`, `ContentFeedbackRepository`, `MediaAssetRepository`, `PublishEventRepository`, `RunRepository`

**AI Layer**
- `ai/client.py` — `AIClient` Protocol (`chat()`, `generate_image()`), `parse_json_response()` (strips markdown fences), `get_ai_client()` factory, `AIParseError`
- `ai/openai_provider.py` — `AsyncOpenAI` with `max_retries`, `generate_image()` decodes `b64_json` to raw bytes
- `ai/anthropic_provider.py` — stub, ready to wire in

**Platform Rules & Prompts**
- `platform_rules/rules.py` — typed `PlatformRules` dataclass for Instagram, Facebook, LinkedIn, Twitter (char limits, hashtag min/max, system rules injected into captions)
- `prompts/calendar_prompt.py` — theme + objective + post_idea generation
- `prompts/brief_prompt.py` — hook, key_message, emotional_angle, visual_direction, CTA
- `prompts/caption_prompt.py` — platform-aware caption + hashtags
- `prompts/image_prompt.py` — art-direction → image description
- `prompts/multi_variant_prompt.py` — N caption variants for A/B testing
- `prompts/regen_prompt.py` — feedback analysis → adjusted brief fields

**Services (12)**
- `context_service.py` — fetches `Business` + `BusinessPreferences` into a `GenerationContext`
- `calendar_service.py` — WF-CAL: AI generates themes for each day of the month
- `brief_service.py` — WF-BRIEF: AI generates content brief for a slot
- `caption_service.py` — WF-CAPTION: AI generates caption + hashtags; **Twitter 280-char two-stage enforcement** (retry with shorten instruction, raise `TwitterCharLimitError` if still over)
- `asset_service.py` — WF-ASSET: art-direction prompt → AI image → storage backend upload
- `variant_service.py` — WF-MVAR: generates N variants for A/B testing
- `generation_service.py` — WF-GENORCH: `asyncio.gather` for parallel caption generation per platform, `asyncio.Semaphore(5)` for image generation throttling
- `regeneration_service.py` — WF-REGEN: AI analyzes feedback → enhanced brief → re-runs caption
- `publish_service.py` — WF-PUBLISH: decrypts token JIT (Fernet), routes to platform publisher, records `PublishEvent`, updates slot to `published`
- `metrics_service.py` — WF-METRICS: reads `PublishEvent` rows, calls platform insights (stubbed), writes `PostMetrics`
- `run_service.py` — creates/starts/succeeds/fails `WorkflowRun` rows for every async operation
- `notification_service.py` — creates `Notification` row + fires delivery (channel stubbed)

**Platform Publishers (4)**
- `publishers/instagram.py` — 2-step: POST `/{ig_user_id}/media` → POST `/{ig_user_id}/media_publish`
- `publishers/facebook.py` — POST `/{page_id}/photos` or `/feed`
- `publishers/linkedin.py` — POST `/v2/ugcPosts` (URN author)
- `publishers/twitter.py` — POST `/2/tweets`, hard 280-char pre-flight validation before any API call

**Celery**
- `celery_app.py` — 4 queues (`default`, `images`, `publishing`, `metrics`), Beat CRON (`publish_orchestrator_task` every 5 min, `collect_metrics_task` every 6h), `redbeat.RedBeatScheduler`
- `tasks/generation_tasks.py` — 5 tasks: `generate_content_task`, `generate_brief_task`, `generate_caption_task`, `generate_asset_task`, `generate_multi_variant_task`
- `tasks/publish_tasks.py` — `publish_slot_task` (3 retries, `acks_late`, 429 exponential backoff, idempotency lock), `publish_orchestrator_task` (CRON orchestrator)
- `tasks/metrics_tasks.py` — `collect_metrics_task`
- `tasks/regeneration_tasks.py` — `regenerate_from_feedback_task`, `regenerate_content_task`
- `tasks/notification_tasks.py` — `send_notification_task`

**API (32 endpoints across 9 routers)**
- `GET /health`, `GET /ready`, `GET /version`
- `POST /v1/businesses`, `GET /v1/businesses/{id}`, `PUT /v1/businesses/{id}/preferences`, `POST /v1/businesses/{id}/social-connections`
- `POST /v1/calendars`, `GET /v1/calendars/{id}`, `POST /v1/calendars/{id}/generate-themes`, `GET /v1/calendars/{id}/slots`
- `GET /v1/slots/{id}`, `PATCH /v1/slots/{id}`
- `POST /v1/generation/orchestrate`, `/brief`, `/caption`, `/asset`, `/multi-variant`, `/regenerate`
- `GET /v1/review/queue`, `POST /v1/review/slots/{id}/approve`, `POST /v1/review/slots/{id}/reject`
- `POST /v1/publishing/slot/{id}`, `GET /v1/publishing/queue`
- `POST /v1/metrics/collect`, `GET /v1/metrics`, `GET /v1/metrics/posts/{publish_event_id}`
- `GET /v1/runs/{run_id}`, `GET /v1/runs`

**Middleware**
- `middleware/auth.py` — `X-API-Key` header verification against `API_SECRET_KEY` env var
- `middleware/logging.py` — per-request UUID injection, structured request/response logging via structlog

**Utils**
- `utils/encryption.py` — Fernet encrypt/decrypt for platform access tokens at rest
- `utils/idempotency.py` — Redis `SET NX EX` for generation dedup + publish lock
- `utils/retry.py` — tenacity decorators (AI: 3× 2s backoff; HTTP 429: exponential)
- `utils/logging.py` — structlog setup (JSON in prod, text in dev)
- `utils/storage.py` — `StorageBackend` Protocol, `LocalStorage`, S3 stub, Supabase stub
- `utils/errors.py` — `SocialStackError` hierarchy: `NotFoundError`, `ConflictError`, `AIParseError`, `TwitterCharLimitError`, `PublishValidationError`, `RateLimitError`

**Tests (9/9 passing)**
```
tests/unit/platform_rules/test_rules.py::test_all_platforms_have_rules        PASSED
tests/unit/platform_rules/test_rules.py::test_twitter_280_limit               PASSED
tests/unit/platform_rules/test_rules.py::test_instagram_hashtag_range         PASSED
tests/unit/platform_rules/test_rules.py::test_unknown_platform_raises         PASSED
tests/unit/services/test_caption_service.py::test_twitter_char_limit_triggers_retry  PASSED
tests/unit/services/test_caption_service.py::test_ai_parse_json_strips_markdown      PASSED
tests/unit/services/test_caption_service.py::test_ai_parse_json_invalid_raises       PASSED
tests/e2e/test_api_endpoints.py::test_health                                  PASSED
tests/e2e/test_api_endpoints.py::test_version                                 PASSED
```

### What is stubbed / not yet wired (Day 2–4 work)

| Component | Current State | Needed |
|---|---|---|
| `metrics_service._fetch_insights()` | Returns `None` always | Real platform API calls (Day 3) |
| `notification_service._deliver()` | Logs only | Webhook / Slack / email delivery (Day 3) |
| `ai/anthropic_provider.py` | Protocol stub | Wire in when model decision made |
| `middleware/rate_limit.py` | File missing | Redis token bucket per business (Day 4) |
| Integration tests | Empty `tests/integration/` folder | Day 2 |
| Prompt strings | Structurally correct, not verbatim from n8n JSONs | Day 2 |

---

## Day 2 — AI Prompt Extraction + Integration Tests

**Goal:** `POST /v1/generation/orchestrate` triggers full end-to-end pipeline with mock AI + real test DB; all new tests green.

### Tasks

#### 2.1 Extract exact prompt strings from n8n workflow JSONs

Read each JSON from `workflows_new/` and replace the current prompt template content with the verbatim tested strings from production n8n:

| File to update | Source n8n JSON |
|---|---|
| `prompts/calendar_prompt.py` | `WF-CAL_Calendar_Theme_Generator.json` |
| `prompts/brief_prompt.py` | `WF-BRIEF_Content_Brief_Generator.json` |
| `prompts/caption_prompt.py` | `WF-CAPTION_Platform_Caption_Generator.json` |
| `prompts/image_prompt.py` | `WF-ASSET_Image_Generator.json` |
| `prompts/multi_variant_prompt.py` | `WF-MVAR_Multi_Variant_Generator.json` |
| `prompts/regen_prompt.py` | `WF-REGEN_Regeneration_Workflow.json` |

Look for `parameters.messages[].content` or `parameters.prompt` fields in the JSON nodes named "OpenAI Chat Model", "AI Agent", or similar.

#### 2.2 Integration test infrastructure

- Add `pytest-asyncio`, `factory-boy`, async test DB fixtures to `tests/conftest.py`
- Add a test PostgreSQL database URL (SQLite in-memory via `aiosqlite` or separate test-postgres container)
- `MockAIClient` deterministic responses keyed by prompt keywords (already partially in `conftest.py`)

#### 2.3 Integration tests to write

**`tests/integration/test_generation_flow.py`**
- `test_full_orchestration_creates_slots_and_variants` — call `GenerationService.orchestrate()` with mock AI + real DB; assert `ContentSlot`, `ContentBrief`, `ContentVariant` rows created for each platform × each calendar day
- `test_brief_shared_across_platforms` — one `ContentBrief` per calendar day, not per slot
- `test_twitter_280_retry_end_to_end` — mock AI returns 290-char caption on first call, 250-char on retry; assert variant saved with short version and `char_count ≤ 280`
- `test_multi_variant_creates_correct_count` — `variant_count=3` produces exactly 3 `ContentVariant` rows with `version` 1, 2, 3

**`tests/integration/test_brief_caption_chain.py`**
- `test_brief_to_caption_db_persistence` — `brief_service.generate()` → `caption_service.generate()` → assert `brief.id` set on `ContentVariant.brief_id`
- `test_slot_status_advances_correctly` — slot starts `draft`, brief sets `pending_brief`, caption sets `pending_caption`, orchestrator sets `pending_review`

**`tests/unit/services/test_generation_service.py`**
- `test_asyncio_gather_called_for_all_platforms` — mock all sub-services, assert `caption_service.generate` called once per platform
- `test_semaphore_limits_image_concurrency` — assert `asyncio.Semaphore(5)` applied when `generate_images=True`

#### 2.4 Service unit tests (expand)

**`tests/unit/services/test_caption_service.py`** (extend existing)
- `test_instagram_allows_over_280` — 300-char caption on instagram does not trigger retry
- `test_facebook_hashtag_count_respected` — caption contains between `hashtag_min` and `hashtag_max` hashtags per platform rules

### Day 2 Deliverable

`POST /v1/generation/orchestrate` returns `{run_id}`, Flower shows task progress, `GET /v1/runs/{run_id}` shows `status: "succeeded"` after mock AI completes. `make test` still fully green with new integration tests.

---

## Day 3 — Publishing, Regeneration, Real Metrics, CRON Wiring

**Goal:** Full approve → auto-publish flow working. Regeneration from feedback tested. Metrics collection wired to real platform APIs.

### Tasks

#### 3.1 Real metrics platform API calls

Update `services/metrics_service._fetch_insights()` to call real platform APIs:

- **Instagram:** `GET /{media_id}/insights?metric=impressions,reach,likes,comments,saved,shares`
- **Facebook:** `GET /{post_id}/insights?metric=post_impressions,post_reach,post_reactions_by_type_total`
- **LinkedIn:** `GET /v2/organizationalEntityShareStatistics?shares={urn}` (impressions, likes, comments, shares)
- **Twitter/X:** `GET /2/tweets/{id}?tweet.fields=public_metrics` (retweet_count, reply_count, like_count, impression_count)

Use `httpx.AsyncClient` with platform token (Fernet-decrypt via same pattern as `publish_service`). On HTTP error, log and return `None` (partial metrics OK).

#### 3.2 Real notification delivery

Update `services/notification_service._deliver()` with channel routing:

- **webhook** — `POST` to `business.webhook_url` (if set) with `{type, payload, timestamp}` JSON
- **slack** — `POST` to `SLACK_WEBHOOK_URL` env var (if set)
- Email channel — defer to Day 4 or leave as log

Notification types in use: `generation_complete`, `publish_failed`, `publish_success`, `metrics_collected`.

#### 3.3 Integration tests — publishing

**`tests/integration/test_publish_flow.py`**
- `test_publish_lock_prevents_duplicate_publish` — acquire lock on slot_id, assert second publish attempt returns without calling publisher
- `test_publish_orchestrator_filters_due_slots` — create slots with `scheduled_at` in past (approved) and future; assert orchestrator only dispatches past ones
- `test_publish_event_recorded_on_success` — call `publish_service.publish()` with mock publisher; assert `PublishEvent` row created, slot status = `published`
- `test_publish_slot_task_retry_on_429` — mock publisher raises `RateLimitError(retry_after_seconds=60)`; assert Celery `self.retry(countdown=60)` called

#### 3.4 Integration tests — regeneration

**`tests/integration/test_regen_flow.py`**
- `test_regeneration_creates_new_variant_version` — existing variant version=1; after regen, new variant version=2; slot back to `pending_review`
- `test_feedback_analysis_adjusts_brief` — mock AI returns adjusted `emotional_angle`; assert `enhanced_brief` reflects it
- `test_regen_falls_back_to_original_brief_on_ai_failure` — mock AI raises `AIParseError`; assert service uses original brief unchanged

#### 3.5 CRON integration test

**`tests/integration/test_cron.py`**
- `test_publish_orchestrator_dispatches_tasks_for_due_slots` — create 2 approved past-scheduled slots, call `publish_orchestrator_task()` directly; assert `publish_slot_task.delay()` called twice
- `test_metrics_cron_creates_post_metrics_rows` — create 2 publish events, call `collect_metrics_task()` with mock insights; assert `PostMetrics` rows created

### Day 3 Deliverable

Full slot lifecycle working end-to-end: `POST /orchestrate` → `GET /review/queue` → `POST /review/slots/{id}/approve` → Beat fires within 5 min → `publish_event` row created → `GET /metrics` shows data.

---

## Day 4 — Auth, Rate Limiting, Hardening, Full Test Suite

**Goal:** Production-ready. All 32 API endpoints tested. `make test` fully green. `make prod` starts stack cleanly.

### Tasks

#### 4.1 Rate limiting middleware

Create `middleware/rate_limit.py` — Redis token bucket per `business_id`:

```python
class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        business_id = request.headers.get("X-Business-ID")
        if business_id:
            allowed = await check_rate_limit(business_id, limit=100, window_seconds=60)
            if not allowed:
                return Response(status_code=429, content="Rate limit exceeded")
        return await call_next(request)
```

Wire into `app.py` `create_app()` after `LoggingMiddleware`.

#### 4.2 JWT auth option

Extend `middleware/auth.py` to support either `X-API-Key` header OR `Authorization: Bearer <JWT>`:
- JWT signed with `API_SECRET_KEY`, verifiable via `python-jose`
- Claim: `sub` = `business_id`, `exp` = standard expiry
- `GET /v1/auth/token` (POST body: `{api_key}`) → returns `{access_token, expires_in}`

#### 4.3 Production docker-compose validation

- Verify all healthchecks fire correctly in `docker-compose.prod.yml`
- Confirm `worker-images` has `CELERYD_CONCURRENCY=2`, `worker-publishing` has `8`
- Confirm no `--reload` flag in prod
- Confirm `flower` is **not** in the prod profile (dev only)
- Add `depends_on: {condition: service_healthy}` chains: api depends on postgres + redis; workers depend on redis

#### 4.4 Full E2E test suite

**`tests/e2e/test_api_endpoints.py`** (extend existing 2 tests to full coverage)

Grouped by router:
- **Businesses:** `POST /v1/businesses` → creates + returns 201; `GET /v1/businesses/{id}` → 200 or 404; `PUT /v1/businesses/{id}/preferences` → 200
- **Calendars:** `POST /v1/calendars` → 201; `POST /v1/calendars/{id}/generate-themes` → 202 + `{run_id}`
- **Slots:** `GET /v1/slots/{id}` → 200; `PATCH /v1/slots/{id}` → status updated
- **Generation:** `POST /v1/generation/orchestrate` → 202 + `{run_id}`; assert Celery `delay()` called (mock)
- **Review:** `GET /v1/review/queue` → list; `POST /v1/review/slots/{id}/approve` → status=approved; `POST /v1/review/slots/{id}/reject` with `regenerate: true` → 202 + `{run_id}`
- **Publishing:** `POST /v1/publishing/slot/{id}` → 202; `GET /v1/publishing/queue` → list
- **Metrics:** `POST /v1/metrics/collect` → 202; `GET /v1/metrics` → list
- **Runs:** `GET /v1/runs/{run_id}` → 200 or 404; `GET /v1/runs` → list
- **Auth rejection:** all write endpoints return 401 when `X-API-Key` missing or wrong

#### 4.5 Task audit — fail paths

Verify every Celery task calls `run_svc.fail()` on every exception branch:

Files to audit:
- `tasks/generation_tasks.py` — 5 tasks
- `tasks/publish_tasks.py` — 2 tasks
- `tasks/metrics_tasks.py` — 1 task
- `tasks/regeneration_tasks.py` — 2 tasks

Pattern every task must follow:
```python
try:
    result = await svc.some_operation(...)
    await run_svc.succeed(run_id, output=result)
except Exception as exc:
    await run_svc.fail(run_id, error={"message": str(exc), "type": type(exc).__name__})
    raise  # re-raise so Celery marks task as FAILURE
```

#### 4.6 Final `make test` target

Ensure `pyproject.toml` `[tool.pytest.ini_options]` covers all three test levels:
```toml
testpaths = ["tests"]
```

Add coverage threshold to Makefile:
```make
test:
    pytest --cov=socialstack --cov-report=term-missing --cov-fail-under=70
```

### Day 4 Deliverable

- `make test` — all unit + integration + e2e tests pass, ≥70% coverage
- `make prod` — full stack starts cleanly with no `--reload`, all healthchecks green
- Every write endpoint rejects unauthenticated requests (401)
- Rate limiting returns 429 when threshold exceeded
- All Celery tasks have complete fail paths

---

## Environment Variables Reference

```bash
# Database
DATABASE_URL=postgresql+asyncpg://socialstack:password@postgres:5432/socialstack

# Redis / Celery
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/1

# AI (model-agnostic — swap provider and models without code changes)
AI_PROVIDER=openai                  # openai | anthropic
AI_CHAT_MODEL=gpt-4o-mini
AI_IMAGE_MODEL=gpt-image-1
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...        # for future Claude provider

# Storage
STORAGE_BACKEND=local               # local | s3 | supabase
LOCAL_STORAGE_PATH=./data/media
S3_BUCKET=socialstack-media
S3_REGION=us-east-1
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=

# Security
API_SECRET_KEY=<random-32-bytes-hex>
TOKEN_ENCRYPTION_KEY=<fernet-key>   # encrypts social platform tokens at rest
INBOUND_HMAC_SECRET=<random>

# Application
ENVIRONMENT=production
LOG_LEVEL=INFO
LOG_FORMAT=json                     # json | text (text recommended for local dev)

# CRON
PUBLISH_CRON_EVERY_MINUTES=5
METRICS_CRON_EVERY_HOURS=6

# Workers
MAX_CONCURRENT_IMAGE_TASKS=5
CELERY_WORKER_CONCURRENCY=4
CELERY_TASK_SOFT_TIME_LIMIT=600
CELERY_TASK_TIME_LIMIT=900
```

---

## Quick Start

```bash
cd socialstack

# copy and fill .env
cp .env.example .env

# start full stack (docker required)
make dev

# run migrations (first time)
make migrate

# run tests
make test

# watch Celery tasks
open http://localhost:5555  # Flower
```

---

## Verification Checklist

Run this sequence manually after Day 4 to validate the full product:

1. `make dev` → all containers healthy
2. `POST /v1/businesses` → business created
3. `PUT /v1/businesses/{id}/preferences` → preferences saved
4. `POST /v1/businesses/{id}/social-connections` → encrypted token stored
5. `POST /v1/calendars` → calendar created
6. `POST /v1/calendars/{id}/generate-themes` → returns `{run_id}`
7. `GET /v1/runs/{run_id}` → status `succeeded`, calendar_days rows populated
8. `POST /v1/generation/orchestrate` → returns `{run_id}`
9. Flower shows task tree: orchestrate → brief × days → caption × platforms → asset × slots (optional)
10. `GET /v1/runs/{run_id}` → `succeeded`
11. `GET /v1/review/queue?business_id={id}` → slots with status `pending_review`
12. `POST /v1/review/slots/{id}/approve` → slot status = `approved`
13. Wait up to 5 min → Beat fires `publish_orchestrator_task` → slot status = `published`, `publish_events` row created
14. `POST /v1/review/slots/{id}/reject` with feedback + `regenerate: true` → new `{run_id}`
15. `GET /v1/runs/{run_id}` → new variant version=2, slot back to `pending_review`
16. `POST /v1/metrics/collect` → `PostMetrics` rows created
17. `GET /v1/metrics?business_id={id}` → analytics data returned
18. `make test` → all tests pass

---

## Future: SuperOne Integration Adapter

When the time comes to integrate into SuperOne CRM, the integration layer will be a thin adapter — **not** modifications to SocialStack itself:

- SuperOne reads SocialStack's REST API to display calendars, slots, and content in the CRM UI
- SuperOne writes via SocialStack's API to create businesses, set preferences, trigger generation
- SocialStack's `businesses` table maps 1:1 to SuperOne `Account` records via `external_id` column (add via Alembic migration when needed)
- No n8n, no Welvom API dependency — SocialStack is a self-contained product

This keeps SocialStack independently deployable and testable.
