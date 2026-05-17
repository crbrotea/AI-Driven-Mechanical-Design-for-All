# Chat Image Upload — Implementation Plan

**Goal:** ship sketch attachment for `/interpret` end-to-end.

**Architecture:** base64-in-JSON → Pydantic-validated → `ImageInput` dataclass threaded through `Orchestrator` → `Part.from_data` on Vertex.

**Tech Stack:** FastAPI + Pydantic v2 + google-cloud-aiplatform / Next.js 14 + next-intl + Tailwind.

---

## Task 1 — Backend DTO: image fields

**Files:**
- Modify: `apps/backend/services/interpreter/api/dto.py`
- Test: `apps/backend/tests/unit/interpreter/test_dto_image.py` (new)

Steps:
1. Write failing tests covering: text-only back-compat / valid image / mime outside allowlist / both-fields-or-neither / decoded > 4 MiB / malformed base64.
2. Run tests → confirm fail.
3. Add `image_b64`, `image_mime` fields + `model_validator(mode="after")`.
4. Run tests → green.
5. Commit `feat(interpreter): accept image_b64 + image_mime on InterpretRequest`.

## Task 2 — ImageInput dataclass + GemmaProtocol signature

**Files:**
- Modify: `apps/backend/services/interpreter/agent/gemma_client.py`
- Test: `apps/backend/tests/unit/interpreter/test_gemma_protocol.py` (new — verify Protocol shape)

Steps:
1. Add `ImageInput` frozen dataclass.
2. Add `image: ImageInput | None = None` kwarg to `GemmaProtocol.generate`.
3. Run existing tests → no regression.
4. Commit `feat(interpreter): add ImageInput dataclass to Gemma protocol`.

## Task 3 — VertexGemmaClient: Part.from_data wiring

**Files:**
- Modify: `apps/backend/services/interpreter/agent/vertex_gemma.py`
- Test: `apps/backend/tests/unit/interpreter/test_vertex_gemma_image.py` (new)

Steps:
1. Write failing tests with a mocked `GenerativeModel`:
   - When `image=None`, contents matches today's structure.
   - When `image` set with previous_messages empty, the last entry of `contents` is a `Content(role="user", parts=[Part.from_text(prompt), Part.from_data(...)])`.
   - When `image` set + previous_messages non-empty, the final `Content` carries both parts.
2. Add `image` kwarg + Part.from_data call.
3. Run tests → green.
4. Commit `feat(interpreter): pass image via Part.from_data to Vertex`.

## Task 4 — Orchestrator threads image through

**Files:**
- Modify: `apps/backend/services/interpreter/agent/orchestrator.py`
- Test: `apps/backend/tests/component/interpreter/test_orchestrator_image.py` (new)

Steps:
1. Write a test using a `FakeGemma` that records the `image` kwarg.
2. Add `image` kwarg to `Orchestrator.run` and `_single_attempt`; forward to `self._gemma.generate`.
3. Run tests → green.
4. Commit `feat(interpreter): orchestrator forwards image to Gemma`.

## Task 5 — Router decodes + invokes orchestrator with image

**Files:**
- Modify: `apps/backend/services/interpreter/api/router.py`
- Test: `apps/backend/tests/component/interpreter/test_router_image.py` (new)

Steps:
1. Write a test with FastAPI TestClient + scripted FakeGemma:
   - POST `/interpret` with image_b64+image_mime → fake gemma records `image.data == decoded bytes`.
   - Session message log carries only the text prompt (not bytes).
2. In router, after request parsing: if both fields set, base64-decode and build `ImageInput`; pass to `orchestrator.run(image=...)`.
3. Run tests → green.
4. Commit `feat(interpreter): /interpret route forwards image to orchestrator`.

## Task 6 — Prompt update (sketch section + ES few-shot)

**Files:**
- Modify: `apps/backend/prompts/interpreter_system.md`

Steps:
1. Append "## Sketches & reference images" + Example 3 to prompt.
2. No test (it's documentation consumed by Gemma at runtime).
3. Commit `docs(interpreter): system prompt covers sketch input`.

## Task 7 — Frontend: ChatInput attach UI

**Files:**
- Modify: `apps/frontend/components/chat/ChatInput.tsx`
- Modify: `apps/frontend/messages/en.json`, `apps/frontend/messages/es.json`
- Modify: `apps/frontend/components/ui/toast.tsx` (no change — already supports `error` variant)
- Test: `apps/frontend/components/chat/__tests__/ChatInput.test.tsx` (new)

Steps:
1. Add i18n keys for `chat.attach_aria`, `chat.attach_remove`, `chat.image_too_large`, `chat.image_bad_type`, `chat.attached_image`.
2. Add tests: render attach button / reject 5 MB file / reject `.gif` / accept PNG / X removes / submit forwards attachment.
3. Refactor `ChatInput` props to `onSubmit: (text: string, attachment?: ChatAttachment) => void`.
4. Wire paperclip button + hidden file input + thumbnail preview.
5. Run tests → green.
6. Commit `feat(chat): attach sketch button + preview in ChatInput`.

## Task 8 — Frontend: useInterpretStream + ChatPanel propagation

**Files:**
- Modify: `apps/frontend/lib/hooks/useInterpretStream.ts`
- Modify: `apps/frontend/components/chat/ChatPanel.tsx`
- Test: `apps/frontend/lib/hooks/__tests__/useInterpretStream.test.ts` (extend)

Steps:
1. Add `attachment?: { b64: string; mime: string }` param to `start`.
2. POST body conditionally includes `image_b64` + `image_mime`.
3. ChatPanel `submit(text, attachment?)` → forwards to `start`.
4. Run vitest → green.
5. Commit `feat(chat): hook + panel forward image to /interpret`.

## Task 9 — Run full suites

Steps:
1. `cd apps/backend && uv run pytest -q` → 0 failures.
2. `cd apps/frontend && pnpm test --run` → 0 failures.
3. Commit nothing here; tests should already be passing per task.

## Task 10 — Deploy

Steps:
1. `git push origin master` — Vercel auto-deploys frontend, Cloud Build auto-deploys backend.
2. Manual E2E via Chrome DevTools on prod: attach a flywheel sketch, observe extracted dimensions.

## Out of scope

- Cropping / rotation
- HTML canvas drawing
- Persistence of the sketch
- Multi-image, refine-with-image
