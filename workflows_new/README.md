# SuperOne — New Workflows (v2)

Canonical, version-controlled exports of the **rebuilt** n8n workflows for SuperOne.
These are built fresh, mock-first, and aligned with the Welvom API Specification.

> ⚠️ Do **not** confuse this with the `../workflows/` folder. Those are the **legacy v1
> skeletons** — incomplete stubs (TODO placeholders, wrong API endpoints, no working AI
> nodes). They are reference-only. Everything in `workflows_new/` is the real, tested build.

## How these are produced

1. Built and tested live in n8n (`https://n8n.welvom.com`) using mock data (no backend yet).
2. Once a workflow passes end-to-end testing, it is exported from n8n
   (workflow canvas → `...` menu → **Download**) and committed here.
3. When the Welvom backend goes live, the mock `Set` nodes are swapped for real
   `HTTP Request` nodes — and re-exported here.

## Naming convention

`WF-<SHORT>_<PascalCaseName>.json` — using **semantic** short codes (not numbers),
because the build order won't match the legacy/spec numbering. Short codes:

| Code | Workflow |
|---|---|
| CAL | Calendar Theme Generator |
| BRIEF | Content Brief Generator |
| CAPTION | Platform Caption Generator (one platform per run; orchestrator loops platforms) |
| MVAR | Multi-Variant Generator (N caption variants per slot for A/B testing) |
| ASSET | Asset (image) Generator |
| GENORCH | Full Content Generation Orchestrator |
| ERROR | Central Error Handler (set as Error Workflow on every other workflow) |
| REGEN | Regeneration Handler |
| PUBLISH | Platform Publisher |
| PUBORCH | Publish Orchestrator (CRON) |
| METRICS | Metrics Collector (CRON) |
| NOTIFY | Notification Workflow (utility, called by others) |

## Status

| File | Purpose | Status |
|---|---|---|
| WF-CAL_Calendar_Theme_Generator.json | Webhook → AI generates monthly content calendar (theme/objective/post_idea per day) → mock save → summary | ✅ Built & tested (mock) |
| WF-BRIEF_Content_Brief_Generator.json | Webhook → one calendar day → AI generates a creative brief (hook/key_message/emotional_angle/visual_direction/cta) → mock save → brief | ✅ Built & tested (mock) |
| WF-CAPTION_Platform_Caption_Generator.json | Webhook → brief + ONE platform → AI writes a platform-tailored caption + hashtags (platform rules engine, X 280-char enforcement) → mock save → caption | ✅ Built & tested (Instagram, X, LinkedIn verified) |
| WF-ASSET_Image_Generator.json | Webhook → brief → AI art-director writes a viral-grade image prompt → gpt-image-1 renders image (HTTP) → base64→file → asset | ✅ Built & tested (gpt-image-1, real image generated) |
| WF-GENORCH_Generation_Orchestrator.json | Webhook → loop calendar days → **brief once per day** → fan out to `days × platforms` slots → WF-CAPTION (per slot) + optional WF-ASSET (per slot, behind `generate_images`) → grouped aggregate. Now includes execution tracking + multi-platform fan-out. | ✅ Built & tested (2 days × 4 platforms × brief+caption+image — 8 complete posts in one call). Requires WF-BRIEF, WF-CAPTION, WF-ASSET published |
| WF-ERROR_Error_Handler.json | Error Trigger → Build Error Record → Mock Mark Failed (PATCH workflow-runs) → Mock Notify. Set as the **Error Workflow** on every other workflow's Settings | 🟡 Built (reference pattern); pending test by intentionally triggering a failure |
| WF-PUBLISH_Platform_Publisher.json | Webhook → token (mock) → build per-platform payload → Switch by platform → mock IG/FB/LI/X publish → record event → mark slot published | ✅ Built & tested (LinkedIn + Instagram branches verified; FB/X same pattern) |
| WF-PUBORCH_Publish_Orchestrator.json | **Schedule (every 5 min)** → get due approved slots → call WF-PUBLISH per slot → aggregate. Spec WF-11 / API CRON `publish_due_content`. | ✅ Built & tested. Requires WF-PUBLISH published |
| WF-METRICS_Metrics_Collector.json | **Schedule (every 6 h)** → get published posts → mock fetch insights per platform (impressions, reach, likes, comments, saves, shares, engagement_rate) → mock insert post_metrics time-series rows → aggregate. Spec WF-12 / API CRON `collect_metrics`. | ✅ Built |
| WF-REGEN_Regeneration_Workflow.json | Webhook → AI analyzes reviewer feedback → rewrites the brief automatically → calls WF-CAPTION with enhanced brief → saves new variant (v2) → slot back to pending_review. Spec WF-9. | ✅ Built & tested ("too salesy → more educational, cost anxiety" → new caption addressed it specifically) |
| WF-MVAR_Multi_Variant_Generator.json | Webhook → 1 AI call returns N distinct caption variants (emotional / educational / promotional / question / social_proof) → mock save each → list for A/B review. Spec WF-4. | ✅ Built & tested (3 distinct angles produced for same brief) |
| WF-NOTIFY_Notification_Workflow.json | Webhook → routes by type (approval_required / content_ready / publish_success / publish_failure / token_expiration / workflow_failure) → builds per-type template → mock send → mock log. Spec WF-14. Called by other workflows when they need to notify. | ✅ Built & tested (approval_required routed correctly) |

---

# 🚀 GO-LIVE MIGRATION GUIDE

**Read this before connecting any workflow to the real backend.**
Everything here is currently **mocked**. The mocks were built to match the real Welvom
API shapes exactly, so going live is mostly node-type swaps — *but* there are global
changes (auth, env vars, error handling, security) that apply to EVERY workflow and must
be done once, centrally. Do the GLOBAL section first, then the per-workflow swaps.

## A) GLOBAL changes — apply to ALL workflows (do these first)

These are NOT yet in any workflow. They must be added during go-live.

1. **Authentication (Supabase JWT).** Every real Welvom API call needs
   `Authorization: Bearer {supabase_jwt}`. The legacy `X-API-KEY` is wrong — ignore it.
   - Create a **service-account user** in Supabase for n8n with an `admin` role.
   - Store its token/refresh token as an **n8n credential** (Header Auth or a custom cred),
     never hardcoded in nodes.
   - Recommended: build a small shared sub-workflow `SUB-AUTH` that returns a valid
     (refreshed-if-needed) bearer token, and have each workflow call it before its HTTP nodes.

2. **Environment variables** (set in n8n, used by every HTTP node):
   | Var | Example | Purpose |
   |---|---|---|
   | `WELVOM_API_BASE` | `https://superone-api.welvom.com/v1` | API base URL |
   | `N8N_WEBHOOK_SECRET` | (random) | verify inbound webhooks (see #4) |
   | `N8N_SERVICE_JWT` / refresh token | (secret) | service-account auth |

3. **Swap pattern for every mock node** (`Set` → `HTTP Request`):
   - `Get *` mock (returns `{ data: ... }`) → **HTTP Request GET**; keep the node **name** identical
     so all `$('Get X')` references keep working. Map the response so `$json.data` still holds the payload.
   - `Mock Save *` → **HTTP Request POST/PATCH**; body is already prepared on the item.
   - After each HTTP node, add an **error check**: if `$json.error` exists, `throw` so the
     Error Workflow fires (see #5).

4. **Webhook security.** Today the webhooks are open (no auth). Before production:
   - Require a shared secret header (`x-n8n-secret` == `$env.N8N_WEBHOOK_SECRET`) checked in a
     first IF node, OR proper HMAC signature verification (preferred, Stripe/GitHub style).
   - Reject with `401` if it fails (mirror the existing `Respond 400` pattern).

5. **Error handling + run logging.** ✅ Pattern in place: **WF-ERROR** is built + WF-GENORCH has Mock Insert Run / Mock Mark Succeeded. Still TODO at go-live: swap the Mock Insert/Mark Set nodes for real `POST /workflow-runs` + `PATCH /workflow-runs/{id}` (Global pattern, see §C.5). Roll out the tracking pattern to WF-CAL, WF-BRIEF, WF-CAPTION, WF-ASSET (currently only WF-GENORCH has it).

6. **Idempotency.** Accept an `idempotency_key` in each trigger payload and pass it to the
   backend so retries don't double-write.

7. **Rate limits / retries.** AI + platform APIs throttle. `Message a model` already has
   `retryOnFail` (3×, 2s). Add the same to every real HTTP node; back off on `429`.

8. **Remove/repurpose `Mock Save *` "saved/saved_at" stamps** — those are mock-only markers.
   The real save returns the persisted row; read IDs from that response instead.

## B) PER-WORKFLOW swap maps

Each table = the only nodes that change for that workflow. Node **names stay the same**;
only the node **type** (Set → HTTP Request) and its config change. `Merge Context` / `Parse *`
/ `Build *` logic nodes stay UNCHANGED.

### WF-CAL — Calendar Theme Generator  ✅ tested
| Mock node | Real replacement | Notes |
|---|---|---|
| `Get Preferences` | `GET {WELVOM_API_BASE}/content/preferences` | returns `{ data:{...} }` |
| `Get Offerings` | `GET {WELVOM_API_BASE}/settings/offerings` | returns `{ data:[...] }` |
| `Get Business` | `GET {WELVOM_API_BASE}/settings/business` | returns `{ data:{...} }` |
| `Mock Save Day` | `PATCH {WELVOM_API_BASE}/content/calendars/{calendar_id}/days/{date}` | body `{ theme, objective, post_idea }`; `calendar_id`+`date` already on each item |

Trigger: `{ "calendar_id", "business_id", "month", "year" }`

### WF-BRIEF — Content Brief Generator  ✅ tested
| Mock node | Real replacement | Notes |
|---|---|---|
| `Get Preferences` | `GET {WELVOM_API_BASE}/content/preferences` | brand tone, pain points |
| `Get Business` | `GET {WELVOM_API_BASE}/settings/business` | name, industry |
| `Mock Save Brief` | `PATCH {WELVOM_API_BASE}/content-items/{content_item_id}` (legacy pattern) — store brief on the item | ⚠️ brief has **no dedicated endpoint**; alternatively the orchestrator passes the brief in-memory to WF-CAPTION and this save is dropped |

Trigger: `{ "slot_id", "business_id", "day": { date, theme, objective, post_idea } }`

### WF-CAPTION — Platform Caption Generator  🟢 tested (IG/X)
| Mock node | Real replacement | Notes |
|---|---|---|
| `Get Preferences` | `GET {WELVOM_API_BASE}/content/preferences` | brand tone |
| `Get Business` | `GET {WELVOM_API_BASE}/settings/business` | name, industry |
| `Mock Save Caption` | persist as a `content_variant` (part of `generate-content` internals, or `PATCH content_variants`) | `slot_id` + `platform` already on the item |

Trigger: `{ "slot_id", "business_id", "platform", "brief": {...} }`
Keep the platform rules engine + X 280-char enforcement as-is.

### WF-ASSET — Image Generator  ✅ tested (gpt-image-1)
| Mock node | Real replacement | Notes |
|---|---|---|
| `Get Preferences` | `GET {WELVOM_API_BASE}/content/preferences` | brand_tone + `ai_generate_images` decides branch |
| `Get Business` | `GET {WELVOM_API_BASE}/settings/business` | name, industry |
| `Generate Image` (HTTP) | already real `POST https://api.openai.com/v1/images/generations` (`gpt-image-1`, body: model/prompt/size) | Returns `data[0].b64_json` |
| `Image to File` | keep — converts base64 to binary | At go-live: pipe binary into `POST {WELVOM_API_BASE}/media/assets` (multipart), then `PATCH /content/variants/{id}/override-media` with `media_asset_id` |
| (new branch needed) | when `ai_generate_images=false`: `GET /media/assets?asset_type=image&tag_ids=...` → pick best match → attach via `PATCH /content/variants/{id}/override-media` with `media_asset_id` | Library-match path is not yet built |

Trigger: `{ "slot_id", "business_id", "platform", "theme", "brief": { visual_direction, key_message, emotional_angle, cta } }`

### WF-GENORCH — Generation Orchestrator  ✅ tested (incl. images)
| Mock node | Real replacement | Notes |
|---|---|---|
| `Get Calendar Days` | `GET {WELVOM_API_BASE}/content/calendars/{calendar_id}` | Cursor-paginate; map response so the days array stays at `data.days` |
| `Mock Insert Run` | `HTTP POST {WELVOM_API_BASE}/workflow-runs` body `{ workflow, trigger_kind, started_at, status:"running", input, related_entity_id }` → use `{id}` as `run_id` | See §C.5 |
| `Mock Mark Succeeded` | `HTTP PATCH {WELVOM_API_BASE}/workflow-runs/{run_id}` body `{ status:"succeeded", finished_at, output }` | See §C.5 |
| `Call WF-BRIEF` / `Call WF-CAPTION` / `Call WF-ASSET` (HTTP to worker webhooks) | At go-live, prefer **Execute Workflow** (sub-workflow) calls OR keep HTTP to internal worker URLs. Workers must have Execute Workflow Trigger if switching off webhook calls. | Today they go through worker production webhooks — that works as-is at go-live too |
| (new step needed) | After Aggregate: per slot, `PATCH /content/slots/{id}` with `status="pending_review"` (covers spec WF-7 essence) | Not yet added |

Trigger: `{ "calendar_id", "business_id", "platform", "generate_images": bool }`

### WF-ERROR — Central Error Handler  🟡 built, deploy in progress
| Mock node | Real replacement | Notes |
|---|---|---|
| `Mock Mark Failed` | `HTTP PATCH {WELVOM_API_BASE}/workflow-runs/{run_id}` body `{ status:"failed", finished_at, error: { message, node, stack } }` | Read run_id from `$execution.id` for now |
| `Mock Notify` | real notification call (Slack webhook / email / on-call paging) — covers spec WF-14 partly | Wire to whichever channel ops watches |

Trigger: auto-fired by n8n when any workflow that lists WF-ERROR as its *Error Workflow* throws an unhandled error.

## C) UPCOMING workflows — pre-noted real targets (build mock-first, same pattern)

| Workflow | Will read (real) | Will write (real) | Special notes |
|---|---|---|---|
| **WF-4 Multi-Variant** (spec) | brief + preferences | multiple `content_variants` per slot | NOT BUILT. Spec requires multiple variants per slot for A/B and approval flexibility |
| **WF-7 Review Queue** (spec) | content_variants, content_items | slot `status=pending_review`, notify | Currently folded as a TODO step in WF-GENORCH; spec separates it |
| **WF-8 Approval Handler** (spec) | content_variants | approve/reject + trigger selective regen | NOT BUILT |
| **WF-REGEN** (regeneration) | `content_variants`, `content_feedback` | new `content_variant` (version+1); slot back to `pending_review` | Triggered by `POST /content/variants/:id/reject` (regenerate=true). Re-runs only flagged platforms. |
| **WF-PUBLISH** (publisher) | `social_platform_connections` (decrypt tokens just-in-time), `content_variants` | Meta/LinkedIn/X APIs; `publish_events`; slot `status=published` | Per slot+platform. Instagram = 2-step (create container → publish). Handle token refresh + `429`. |
| **WF-PUBORCH** (publish CRON) | `content_slots` where `status=approved AND scheduled_at<=now()` | delegates to WF-PUBLISH | **Schedule Trigger every 5 min** (matches API CRON `publish_due_content`). |
| **WF-METRICS** (metrics CRON) | `publish_events` (success), `social_platform_connections` | `post_metrics` (time-series row per post per run) | **Schedule Trigger every 6h** (matches API CRON `collect_metrics`). |

## C.5) OBSERVABILITY PATTERN — execution tracking + error workflow

Every workflow follows this pattern (currently being rolled out — WF-GENORCH first; workers next):

```
Webhook → Validate → [Mock Insert Run] → ... main work ... → [Mock Mark Succeeded] → Respond Success
                                                      ↘
                            (if anything throws) → WF-ERROR → Mock Mark Failed → Mock Notify
```

**Mock Insert Run** (Set node, just after validation) — produces tracking fields:
`run_id` (= `$execution.id`), `run_workflow`, `run_started_at`, `run_status: running`.
At go-live: replace with `HTTP POST {WELVOM_API_BASE}/workflow-runs`; use the returned `{id}` as run_id.

**Mock Mark Succeeded** (Set node, just before Respond Success) — adds:
`run_finished_at`, `run_status: succeeded`. Response body now carries this metadata so callers
can correlate the result with the run.
At go-live: `PATCH /workflow-runs/{run_id}` with body `{ status, finished_at, output }`.

**WF-ERROR** — set as each workflow's *Settings → Error Workflow*. When ANY node throws,
n8n auto-fires WF-ERROR with `{ workflow, execution: { id, url, error } }`. WF-ERROR builds
an error record and Mock-Marks the run failed + Mock-Notifies.
At go-live: replace the two Set nodes with `PATCH /workflow-runs/{id}` (failed) + a real
notification (Slack/email/webhook → covers spec WF-14).

**How to apply WF-ERROR to a workflow:** open the workflow → Settings tab → *Error Workflow* dropdown → pick **WF-ERROR**. No JSON changes needed.

## D) Known mock-only quirks to clean at go-live

- `saved` / `saved_at` fields on every `Mock Save *` node are placeholders — remove once the
  real API response provides persisted IDs/timestamps.
- Webhooks currently have **no auth** — must add secret/HMAC (Global #4) before production.
- ✅ Central error workflow (**WF-ERROR**) is built. Still TODO: wire it as the Error Workflow
  on WF-CAL/WF-BRIEF/WF-CAPTION/WF-ASSET (currently only WF-GENORCH points to it).
- Execution tracking (Mock Insert Run / Mock Mark Succeeded) is currently only in
  **WF-GENORCH** — replicate to the 4 workers using the §C.5 pattern.
- `pending_review` status update is **not yet** wired into WF-GENORCH (spec WF-7 handoff). TODO.
- Multi-variant (spec WF-4) and multi-platform fan-out in WF-GENORCH are not built.

## E) MASTER API INTEGRATION MAP (all 9 workflows)

Complete view: every workflow, how it's triggered, and **every exact Welvom endpoint** it
reads/writes. Built workflows also have node-level maps in section B. Methods/paths are
relative to `{WELVOM_API_BASE}` (= `https://superone-api.welvom.com/v1`).

### Content generation (workers)

**WF-CAL** — trigger: backend `POST /content/calendars/:id/generate-themes` → n8n webhook `calendar-generate-themes`
- READ  `GET /content/preferences`
- READ  `GET /settings/offerings`
- READ  `GET /settings/business`
- WRITE `PATCH /content/calendars/{calendar_id}/days/{date}`  (one call per day)

**WF-BRIEF** — trigger: WF-GENORCH sub-workflow (or webhook `content-brief-generate` for tests)
- READ  `GET /content/preferences`
- READ  `GET /settings/business`
- WRITE `PATCH /content-items/{content_item_id}`  (store brief — legacy pattern) ⚠️ see §F
- EXTERNAL  OpenAI (chat)

**WF-CAPTION** — trigger: WF-GENORCH sub-workflow (or webhook `content-caption-generate` for tests)
- READ  `GET /content/preferences`
- READ  `GET /settings/business`
- WRITE  content_variant caption ⚠️ no granular public endpoint — see §F
- EXTERNAL  OpenAI (chat)

**WF-ASSET** — trigger: WF-GENORCH sub-workflow (or webhook for tests)
- READ  `GET /content/preferences`  (ai_generate_images, platform_media_overrides)
- READ  `GET /media/assets?asset_type=image&tag_ids=...`  (library-match branch only)
- WRITE `POST /media/assets`  (when AI-generates a new image → upload to Storage)
- WRITE `PATCH /content/variants/{id}/override-media`  (attach asset to the variant)
- EXTERNAL  Image-gen API (OpenAI images / provider)

### Orchestration

**WF-GENORCH** — trigger: backend `POST /content/calendars/:id/generate-content` → n8n webhook
- READ  `GET /content/calendars/{id}`  (days)
- READ  `GET /content/slots?calendar_id=...`  (the slots to fill; cursor-paginate)
- CALLS (sub-workflows): WF-BRIEF → WF-CAPTION → WF-ASSET  (loops days × platforms)
- WRITE  content_items / content_variants created; slot `status → pending_review` ⚠️ see §F

**WF-REGEN** — trigger: backend `POST /content/variants/:id/reject` (regenerate=true) → n8n webhook
- READ  `GET /content/slots?...` / variant + `content_feedback`
- READ  `GET /content/preferences`, `GET /settings/offerings`
- CALLS WF-CAPTION and/or WF-ASSET for only the flagged platforms
- WRITE  new content_variant (version+1); slot `status → pending_review`

### Publishing

**WF-PUBLISH** — trigger: WF-PUBORCH sub-workflow (one slot+platform)
- READ  `GET /content/platforms`  → decrypt token from `social_platform_connections` ⚠️ token access, see §F
- READ  variant caption + asset_url
- WRITE `publish_events`; slot `status → published`
- EXTERNAL  Meta Graph API (IG 2-step: create container → publish; FB photos), LinkedIn ugcPosts, X create-tweet

**WF-PUBORCH** — trigger: **Schedule (every 5 min)** = API CRON `publish_due_content`
- READ  `GET /content/slots?status=approved&due=now`  (scheduled_at <= now)
- CALLS WF-PUBLISH per due slot

**WF-METRICS** — trigger: **Schedule (every 6 h)** = API CRON `collect_metrics`
- READ  `publish_events` (status=success) + `social_platform_connections`
- WRITE `post_metrics`  (new time-series row per post per run)
- EXTERNAL  Meta/LinkedIn/X insights APIs

## F) ⚠️ OPEN BACKEND-COORDINATION ITEMS (must resolve before go-live)

The public API spec exposes **bulk** and **review** endpoints but not all the **granular
writes** n8n needs for intermediate results. Confirm these with the backend team:

1. **Writing content_items / content_variants from n8n.** The spec only has the bulk
   `POST /content/calendars/:id/generate-content`. n8n's orchestrator produces variants
   step-by-step and needs to persist them. Options to agree on:
   (a) backend adds internal granular endpoints (`POST /content/items`, `POST /content/variants`),
   (b) `generate-content` triggers n8n and n8n **returns** the data for the backend to persist, or
   (c) n8n writes directly to Supabase with the service_role key.
2. **Brief storage.** No `brief` endpoint exists. Either add a field on `content_items`
   (`PATCH /content-items/:id`) or pass the brief in-memory orchestrator→caption (no persistence).
3. **Platform token access for publishing.** Tokens are encrypted in `social_platform_connections`.
   n8n must NOT hold raw tokens — agree on an internal "get decrypted token" endpoint that
   returns a short-lived token just-in-time, or have the backend perform the publish call.
4. **Who runs the CRONs** — n8n Schedule triggers (WF-PUBORCH / WF-METRICS) vs the backend's
   own CRONs (`publish_due_content`, `collect_metrics`). Pick one to avoid double-publishing.

## Test invocations (mock — current state)

```
# WF-CAL
POST https://n8n.welvom.com/webhook-test/calendar-generate-themes
Body: { "calendar_id":"cal_test_123", "business_id":"biz_test_456", "month":6, "year":2025 }

# WF-BRIEF
POST https://n8n.welvom.com/webhook-test/content-brief-generate
Body: { "slot_id":"slot_test_1", "business_id":"biz_test_456",
        "day": { "date":"2025-06-06", "theme":"Teeth Whitening Myths Busted",
                 "objective":"education", "post_idea":"Debunk common whitening myths" } }

# WF-CAPTION
POST https://n8n.welvom.com/webhook-test/content-caption-generate
Body: { "slot_id":"slot_ig_1", "business_id":"biz_test_456", "platform":"instagram",
        "brief": { "hook":"...", "key_message":"...", "emotional_angle":"...", "cta":"..." } }

# WF-ASSET
POST https://n8n.welvom.com/webhook-test/content-asset-generate
Body: { "slot_id":"slot_ig_1", "business_id":"biz_test_456", "platform":"instagram",
        "theme":"Teeth Whitening Myths Busted",
        "brief": { "visual_direction":"...", "key_message":"...", "emotional_angle":"..." } }

# WF-GENORCH (full pipeline; brief + caption + optional real image)
POST https://n8n.welvom.com/webhook-test/content-generate-orchestrate
Body: { "calendar_id":"cal_test_123", "business_id":"biz_test_456",
        "platform":"instagram", "generate_images": true }
```
