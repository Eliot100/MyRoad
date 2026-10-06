# Agent path builder (`/add-path`)

A signed-in user describes a goal; an agent builds a full, long learning path
and saves it as a draft in the platform PathStore. The user (or the agent)
publishes it, and it plays in the existing `/play` player and topic map.

## Steps

1. **Goal**: goal or topic, subject (math, english, physics, piano, general),
   learner level, interface language of the path, content language, length
   (short 3x4, medium 4x5, long 6x5 topics x stages), and how to build
   (Grok through Cloudflare AI Gateway, or demo mode).
2. **Existing paths**: published catalog paths with the same subject (sample
   content and agent-built paths, all read from the PathStore). Open one, or
   continue to a new draft.
3. **Outline**: one model call returns JSON with topics and, per topic, stages
   with `type` (explanation/practice/check/experience), `channel`
   (write/read/listen/record/mouse), `objective`, and `order`. It is validated
   with Pydantic (`agent_builder/models.py`). The user edits titles and order,
   then approves. Approving creates the draft (`AgentTools.create_draft` with an
   agentId).
4. **Build**: one model call per topic fills its stages (explanation text,
   practice/check choices with one correct id, mastery rule). Each topic is
   saved to the draft right after it fills (`AgentTools.save_version`, audited
   with the agentId), so a failure part-way keeps what is already saved. The
   page shows per-topic status and a "Retry this topic" button for failures.
   "Build next topic" advances one topic at a time (the page auto-continues);
   "Build all remaining" fills every waiting topic in one request.
5. **Review and publish**: completeness check, counts, the full content, and
   two buttons: Publish (the user) or Let the agent publish. Feedback on a
   published version creates a new draft version (optionally rebuilding one
   topic with the feedback); the published version is never changed.

## Completeness rule

A path is complete when it has at least 3 topics and at least 12 stages, every
topic includes explanation, practice, and check, and no outline topic is still
waiting or failed (`agent_builder/completeness.py`). Publishing from the builder
requires a complete path. Edges are sequence edges in stage order plus
prerequisite edges between topics (`requires`, earlier topics only).

The 1-60 `estimated_minutes` range applies to sample content files only. Agent
drafts compute minutes from their stages and are not capped.

## Model interface

`PathGenerator` (`agent_builder/generator.py`) has two calls: `outline(spec)`
and `fill_topic(spec, outline, topic_index, feedback=None)`.

- `GatewayPathGenerator` calls `ui/cloudflare_gateway.call_grok_chat` (BYOK)
  with `response_format: json_object`. Replies are parsed defensively: code
  fences and stray prose are stripped, one repair call is made with the parse
  error, and a second failure becomes a readable error on the page.
- `FakePathGenerator` (`agent_builder/fake.py`) is deterministic and offline. It
  powers demo mode and the tests.

MyRoad never reads a provider API key. When `CLOUDFLARE_ACCOUNT_ID` or
`CLOUDFLARE_GATEWAY_ID` is missing, the goal step names the missing variable and
offers demo mode.

## Demo mode

Demo mode builds a full Hebrew draft (12+ stages) without Cloudflare. Demo
drafts have `demo: true`, a "דמו:" title prefix, and a Demo badge in the builder,
the catalog, and the path map.

## Where things live

- `src/myroad_core/agent_builder/`: models, parsing, generators, completeness, builder
- `src/myroad_core/ui/agent_builder_routes.py`: HTTP routes
- `src/myroad_core/ui/templates/add_path.html`: stepper UI (strings in `locales/*.json`)
- `tests/test_agent_path_builder.py`: no-network tests

Published agent paths carry `groupIds: ["agent"]` and show under the
"Agent-built paths" group in the catalog. The catalog and the player always use
the newest published version; drafts stay out of the catalog.
