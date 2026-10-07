> **היסטורי, הוחלף.** המסמך משקף את דרישות v0 מ-2026-09-30. הכלל שרק אדם מפרסם בוטל ב-2026-10-04, וסוכן רשאי לפרסם. המקור הקובע הוא `docs/vision/`.
>
> **Historical, superseded.** Human-only publish was removed on 2026-10-04; agents may publish. See `docs/vision/` for the current source of truth.

# Grok chat extraction — AI Learning Platform: AI Tutors & Adaptive Paths

Source chat: https://grok.com/c/8bbe9a24-ff92-4e16-bd3b-2d3ef376f6b7?rid=4f2c8a58-1fbb-447f-a19d-aaf323dc65b8

Note: The chat visibly names four generated DOCX documents and describes their contents. The outline below consolidates those visible descriptions plus the detailed design discussion in the chat; it is intentionally a requirements-oriented extraction rather than a verbatim copy of private conversation text.

## 1. 01-chazon-umatarah.docx — חזון ומטרה (Vision and Purpose)

### Product thesis / problem
- Build a generic learning platform that turns a learner's goal into a measurable learning path rather than another unstructured tutoring chat.
- A path is a structured graph of learning steps, prerequisites, content, practice and checks for mastery.
- The differentiator is time-efficient, measurable learning with agent-assisted creation and revision.

### Users and roles
- Primary POC user: the owner as learner-builder; the learner asks to learn a new topic and also evaluates the generated path.
- Long-term roles: learner, teacher/content author/approver, and coordinator/admin; the POC may collapse them into one person.
- Permissions must be explicit; a person or agent may act only within the actor's permissions.

### Core loop / POC definition
- New topic/request -> gather or confirm sources -> generate a draft path -> learn through it -> rate the experience -> give feedback -> agent edits/revises -> human reviews and publishes -> repeat.
- The POC should demonstrate generality across subjects, ages and prior-knowledge levels, not only a fixed exam slice. A broad capability test (e.g. a long high-school mathematics course) is a capability demonstration, not a requirement to ship a full content library.
- The first build should be agent-first at the platform boundary: every meaningful human action should be representable as an authenticated API/tool call and recorded as an event.

### Product principles / constraints
- Draft and published versions are distinct; publishing requires a human and must preserve what the publisher saw.
- Maintain provenance and credit when a path is copied, extended or revised.
- Keep UI shell language separate from learning-content language; design for Hebrew, English and Arabic even if the first content slice is narrower.
- Design for future learner metrics and teacher views without making a full school/parent/regulatory product in v0.
- Prefer a small, testable learning engine over video generation, 3-D graph views, automated A/B optimization or a full communications suite.

### Success / measurement direction
- Measure time-to-mastery or another explicit learning outcome, learner return/engagement, path quality and feedback-to-improvement.
- Event logging is a day-one capability, not a later analytics feature.

## 2. 02-afyun-meforat.docx — אפיון מפורט (Detailed Specification)

### Domain model / canonical JSON requirements
- Canonical objects need stable IDs, version IDs, timestamps, actor IDs and provenance.
- Path: name, description, locale/content-language metadata, goal, target audience/prerequisites, version/status, ordered/graph nodes, edges/prerequisites, sources and credit.
- Node/block: stable ID, type (at minimum explanation, practice, assessment/test, experience), learning objective, concept/topic, content or content reference, prerequisites, completion/mastery rule, available channels and localization metadata.
- Edge: from/to IDs, relationship (prerequisite/sequence/optional/branch) and any condition.
- Attempt/progress: learner, path version, block, status, answers/evidence, mastery result, timestamps and events.
- Feedback: actor, target path/version/block, rating/comment/structured issue, source context and proposed change; feedback must create a traceable new draft/version rather than silently mutating a published path.
- Group/role/permission model: users, groups, invitations, author/approver/publisher/coordinator rights and visibility of learner metrics.
- Source/provenance: source ID, URI or citation, retrieval/approval state, content coverage, attribution and which generated material relied on it.
- Locale: UI locale and content/teaching language are separate; a path can keep its structure while content language changes.

### Learning-path structure
- A path is a graph of stages/blocks with prerequisite links and an explicit mastery state; it is not merely a list of chat turns.
- Blocks should be small enough to measure and revise independently. Completion must differ for practice, assessment and reading/explanation.
- Adaptation can change channel (read/listen/write/etc.), route (skip, slow down, split) and generative wrapper/context; the verified learning core remains authoritative.
- Support path versions so a learner mid-path is not overwritten when v3 is published.

### Agent/tool contract
- Expose operations for creating a draft, reading path/version/context, adding or editing blocks and edges, proposing a route, recording feedback, generating a revised draft, running validation, and requesting publication.
- Every tool call needs authenticated actor/agent identity, role/permission check, input/output schema, idempotency or correlation ID, audit event and provenance.
- Agent may draft, suggest, revise and navigate; it must not auto-publish or bypass human approval.
- An external-agent key/integration is separate from the account; agent actions inherit the user's authorization and must retain source/credit information.
- Tool/API results should include path/version IDs, validation warnings, changed objects and a diff/lineage reference.

### API / events / analytics
- Resources should be addressable through a stable API: paths, versions, blocks, edges, attempts, feedback, sources, groups and events.
- Log request, path generation, block view, answer, mastery evaluation, feedback, agent call, edit, approval and publish events with actor, version, timestamps and correlation IDs.
- Metrics should support learner self-view and optional teacher/group views; group visibility is controlled by the creator's permissions.

### Authorization / sharing
- Published paths can be discovered/used by others; editing and creating require permission.
- Group creator defines membership and metric visibility. Learners can see their own metrics when a path is private; teachers can see selected group metrics.
- Publishing records the human publisher and the evidence/context available at publish time.

## 3. 03-mimush-uvdinot.docx — מימוש ובדיקות (Implementation and Testing)

### Recommended build sequence
1. Lock canonical data model and two representative path JSONs.
2. Implement persistence, versions/statuses and the event log.
3. Implement the agent/tool API with RBAC, validation, diffs and audit trail.
4. Implement a thin learner path UI and a minimal author/editor UI.
5. Implement the golden loop: request a new topic -> draft -> learn -> rate/feedback -> revise -> review -> publish.
6. Add the main adaptive behaviours and measurement/BI hooks.
7. Run breadth tests across more than one subject, level and content-language configuration.

### Golden scenario / acceptance tests
- Generate a path for a previously unseen topic with explicit goal/prerequisites.
- Verify each block has objective, type, prerequisite relation and completion/mastery rule.
- Learner progress advances only on valid evidence; adaptive routing can branch or remediate.
- Feedback creates a new draft/version and a clear diff; published version remains immutable.
- Human approval is required for publish; the audit trail identifies the publisher and sources.
- Metrics/events appear for learner and permitted teacher views.
- Switch UI locale without moving the top-level layout or translating the stable product identifier; content language remains independent.
- Verify permissions for learner, author, teacher/coordinator and agent; test denial of unauthorized tool calls.
- Verify source citation/credit and the handling of missing or user-rejected sources.
- Re-run the same scenario after feedback and compare learning-path versions.

### Scope constraints
- Core = path/block/mastery model + event log + API + thin learner UI + thin path editor.
- Do not make v0 depend on a full parent app, video/3-D generation, automatic A/B experimentation on minors, or a complete school-regulation workflow.
- A long mathematics example tests architecture and course-length handling; it is not a promise to author all mathematics content.
- Keep a dedicated Git project with software-engineering practices, CI/CD, readable code and documentation.

### Suggested minimum operational metrics
- Time-to-mastery for a chosen objective.
- Completion/return and evidence quality.
- Learner rating and feedback resolution time.
- Draft-to-publish cycle time and number of revisions.
- Agent/tool error rate, cost per path/revision and source coverage.

## 4. 04-lifney-mimush.docx — לפני מימוש (Pre-implementation / Risks and Locks)

### Model and product risks
- A single evaluator can bias the result; define observable acceptance tests and collect evidence.
- LLM must not be the source of truth for math or other verifiable answers. Separate a verified core (concepts, definitions, scoring/rubrics) from a generative shell (examples, explanations, dialogue) and navigation.
- “Generic” can be false if every subject is represented as the same text block; block types, edges and mastery rules must be domain-aware enough to test breadth.
- LLM cost, latency, context size and retry behaviour need budgets and telemetry.
- Group/child use introduces privacy, consent, safety and regulatory work; do not silently imply that a solo POC solves it.
- Source quality and attribution need a policy; generated content must not lose origin/credit.

### Locks required before first code
- Freeze a small enum of block types, edge types, mastery/completion states and path statuses.
- Write two canonical JSON examples for the same path: before feedback and after feedback; include a version diff.
- Freeze the tool contract: inputs/outputs, permissions, audit/correlation IDs, validation errors and publish gate.
- Define the event schema and the minimum metrics before building UI.
- Define publish/version rules, including what happens to learners already in an older version.
- Define role/group permissions, agent identity, external-key separation and human approval.
- Define locale/content-language rules and source/credit handling.
- Choose one small golden scenario plus a cross-subject/level breadth test.

### What to postpone
- Automatic A/B optimization on learners, rich inter-role communications, a spectacular graph visualization, personalized story/character systems, simultaneous full Hebrew/Arabic/English teaching, and “zero-to-full-exam” coverage.
- Keep the first UI simple: lists/maps are sufficient; learning evidence and version history matter more than presentation.

### Pre-code artifact
- The document ends with a short “week before code” checklist: canonical path JSON, block/edge/tool contract, verified-vs-generative boundary, event/measurement definitions, authorization/publish policy, source/provenance rules and the first golden scenario.

## Initial result / first draft visible in the chat
- The first generated product cycle was saved as the first Git commit and presented as a learner-builder/agent loop for a path called “דרך” (later fixed as the English product identifier “MyRoad”).
- The visible first result included path creation, draft/revise/publish concepts, feedback, attribution, language switching and basic metrics/event-contract thinking, plus four DOCX design documents.
- The chat's latest implementation guidance says the next practical step is to write the canonical JSON and tool contract, then begin phase 0 or exercise one real learning path and give feedback.

## User dissatisfaction / requested fixes visible in the chat
- The initial generated path lacked actual topic-specific learning content and math content.
- Blocks were generic and lacked explicit context tied to the requested path.
- The build saved the agent prompt but not the path name/description.
- The user wanted pre-search of sources and an approval/confirmation step before building a path.
- The user wanted to edit any stage during path construction.
- UI language switching mixed Hebrew and English in stages/tags and did not localize all shell text.
- The user asked Grok Build UX to improve substantially and wanted the platform to support a real source-informed educational path rather than only a generic scaffold.
- The user then requested an ongoing guided POC process with a dedicated Git project, CI/CD, readable code and documentation.
