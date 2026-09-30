# MyRoad POC — Agent / Tool Contract (freeze v0.1)

**Product ID (stable, English):** `MyRoad`  
**Scope:** draft → learn → feedback → revise → human publish. Agent may draft/suggest/revise/navigate; **never auto-publish**.  
**Every call requires:** authenticated `actorId` + optional `agentId`, RBAC check, `correlationId`, audit event, provenance retention.

## Shared envelopes

### Request (all ops)
| Field | Type | Notes |
|-------|------|-------|
| `actorId` | string | Human or service principal |
| `agentId` | string? | External agent key ≠ account; inherits actor auth |
| `correlationId` | string | Idempotency / trace key (client-generated UUID) |
| `pathId` | string? | When targeting a path |
| `versionId` | string? | When targeting a version |

### Response (all ops)
| Field | Type | Notes |
|-------|------|-------|
| `ok` | boolean | |
| `correlationId` | string | Echo |
| `pathId` / `versionId` | string? | |
| `changedObjectIds` | string[] | Blocks/edges/sources touched |
| `diffRef` | string? | Lineage / diff id when revision |
| `validationWarnings` | object[] | Non-fatal |
| `errors` | object[] | Fatal; include `code` |
| `auditEventId` | string | Persisted event |

### Audit event (emitted every call)
`eventType`, `actorId`, `agentId?`, `correlationId`, `pathId?`, `versionId?`, `payloadDigest`, `timestamp`, `rbacDecision` (`allow`|`deny`).

### Path statuses (enum freeze)
`draft` | `in_review` | `published` | `archived`  
Published versions are **immutable**. Feedback always yields a **new** `versionId` in `draft`.

### Block types (enum freeze)
`explanation` | `practice` | `assessment` | `experience`

### Edge relationships (enum freeze)
`prerequisite` | `sequence` | `optional` | `branch`

---

## Operations

### 1. `createDraft`
**Purpose:** Start a path draft from goal + audience (sources still unapproved).  
**RBAC:** `author` | `coordinator` | agent-as-author  
**Input:** `name`, `description?`, `goal`, `audience`, `prerequisites[]`, `contentLanguage`, `uiLocale`, `topicHint?`  
**Output:** `pathId`, `versionId`, `status=draft`, empty/partial `blocks[]`, `sources[]` with `retrievalState.approved=false`  
**Audit:** `path.create_draft`  
**Rules:** No publish. Content language ≠ UI locale fields kept separate.

### 2. `listSourcesForApproval`
**Purpose:** Pre-search / list candidate sources before building authoritative content.  
**RBAC:** `author` | `approver` | `coordinator` | agent-as-author  
**Input:** `pathId`, `versionId`, `query?`  
**Output:** `sources[]` (`sourceId`, `title`, `uri`, `citation`, `coverage`, `retrievalState`)  
**Audit:** `source.list_for_approval`  
**Rules:** Building/publishing verified content that depends on a source requires prior `approveSources` for that source.

### 3. `approveSources`
**Purpose:** Human confirms sources (or rejects).  
**RBAC:** `approver` | `coordinator` (human required; agent may propose only)  
**Input:** `pathId`, `versionId`, `decisions[]`: `{sourceId, approved: boolean, note?}`  
**Output:** updated `sources[]` with `approvedBy`, `approvedAt`  
**Audit:** `source.approve` / `source.reject`  
**Rules:** Agent **cannot** self-approve. Rejected sources must not back verifiedCore.

### 4. `addBlock`
**Purpose:** Add an independently editable block with stable `blockId`.  
**RBAC:** `author` | agent-as-author on `draft` only  
**Input:** `pathId`, `versionId`, `type`, `title`, `learningObjective`, `concept`, `content`, `masteryRule`, `prerequisites[]`, `sourceRefs[]?`  
**Output:** `blockId`, block object, `changedObjectIds`  
**Audit:** `block.add`  
**Rules:** Draft only. Prefer verifiedCore for formulas/answers; generativeShell for prose.

### 5. `editBlock`
**Purpose:** Per-stage edit during construction or revision.  
**RBAC:** `author` | agent-as-author on `draft` only  
**Input:** `pathId`, `versionId`, `blockId`, `patch` (partial block fields)  
**Output:** updated block, `changedObjectIds`  
**Audit:** `block.edit`  
**Rules:** Stable `blockId` preserved. Published versions: deny.

### 6. `addEdge`
**Purpose:** Link blocks with relationship + optional condition.  
**RBAC:** `author` | agent-as-author on `draft` only  
**Input:** `pathId`, `versionId`, `from`, `to`, `relationship`, `condition?`  
**Output:** `edgeId`, edge object  
**Audit:** `edge.add`  
**Rules:** Both endpoints must exist on the version.

### 7. `recordAttempt`
**Purpose:** Learner evidence against a block/version.  
**RBAC:** `learner` (self) | teacher recording on behalf where permitted  
**Input:** `pathId`, `versionId`, `blockId`, `learnerId`, `answers` / `evidence`, `channel?`  
**Output:** `attemptId`, `masteryResult` (`passed`|`failed`|`incomplete`), scores  
**Audit:** `attempt.record`  
**Rules:** Scored against verifiedCore / masteryRule of **that version**. Does not mutate path content.

### 8. `recordFeedback`
**Purpose:** Rating / structured issue / proposed change.  
**RBAC:** `learner` | `author` | `teacher` (per visibility)  
**Input:** `pathId`, `versionId`, `targetBlockId?`, `rating?`, `comment?`, `structuredIssue?`, `proposedChange?`  
**Output:** `feedbackId` (does **not** mutate published path)  
**Audit:** `feedback.record`  
**Rules:** Feedback alone never edits published content; use `reviseDraft` to materialize changes.

### 9. `reviseDraft`
**Purpose:** Create a new draft version from feedback / edits; clear lineage.  
**RBAC:** `author` | agent-as-author  
**Input:** `pathId`, `baseVersionId`, `feedbackIds[]?`, `changeSet?` (blocks/edges add/edit/remove)  
**Output:** new `versionId`, `status=draft`, `_diff` / `diffRef`, `changedObjectIds`  
**Audit:** `path.revise_draft`  
**Rules:** Previous **published** version stays immutable. Mid-path learners stay on their started version unless migrated explicitly (deferred).

### 10. `validatePath`
**Purpose:** Structural + policy checks before review/publish request.  
**RBAC:** `author` | `approver` | agent-as-author  
**Input:** `pathId`, `versionId`  
**Output:** `valid`, `errors[]`, `warnings[]` (e.g. missing masteryRule, unapproved sources, orphan blocks, locale mismatch)  
**Audit:** `path.validate`  
**Rules:** `requestPublish` should fail if `valid=false` on hard errors.

### 11. `requestPublish`
**Purpose:** Ask a human to publish; **does not publish by itself**.  
**RBAC:** `author` | agent-as-author may request; **`approver` / `coordinator` (human) must confirm** via separate publish confirmation (out of agent auto-path)  
**Input:** `pathId`, `versionId`, `evidenceSnapshotRef?`  
**Output:** `status` → `in_review` (or remains `draft` if policy requires), `publishRequestId`  
**Audit:** `path.request_publish`  
**Hard rule:** **No auto-publish.** Final publish records human `publisherId` + evidence/context at publish time as a distinct privileged action (`path.publish`) not listed here as an agent-invokable autopilot op.

---

## RBAC matrix (POC)

| Op | learner | author | approver | coordinator | agent* |
|----|---------|--------|----------|-------------|--------|
| createDraft | — | ✓ | — | ✓ | ✓ |
| listSourcesForApproval | — | ✓ | ✓ | ✓ | ✓ |
| approveSources | — | — | ✓ | ✓ | propose only |
| addBlock / editBlock / addEdge | — | ✓ draft | — | ✓ | ✓ draft |
| recordAttempt | ✓ self | — | — | — | navigate assist only |
| recordFeedback | ✓ | ✓ | — | ✓ | — |
| reviseDraft | — | ✓ | — | ✓ | ✓ |
| validatePath | — | ✓ | ✓ | ✓ | ✓ |
| requestPublish | — | ✓ | — | ✓ | ✓ |
| path.publish (human) | — | — | ✓ | ✓ | **deny** |

\*Agent inherits the binding user's permissions; external agent key ≠ elevated role.

## Correlation & idempotency
- Same `correlationId` + same op + same payload digest → return prior result (no double-create).  
- All denials still emit audit with `rbacDecision=deny`.

## Explicit non-goals in this freeze
Auto-publish, silent mutation of published versions, agent self-approval of sources, full school/parent regulatory workflow.
