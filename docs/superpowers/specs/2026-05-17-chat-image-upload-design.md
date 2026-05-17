# Chat Image Upload — Design Spec

**Date:** 2026-05-17
**Status:** approved (user pre-authorized "no clarifying questions")
**Scope:** S1 Interpreter only

## Goal

Let the user attach **one image** (hand-drawn sketch or reference photo) before sending a chat message in `/design`. The Interpreter (Gemma 4 on Vertex AI) receives the image alongside the text prompt and uses it as visual context to produce a `DesignIntent`.

Single-shot multimodal extraction. No persistence of the image. No refine-time re-use. If the user removes the attachment and resends, behavior reverts to text-only.

## Why now

Hackathon judges score 30 pts on Storytelling. "Draw a flywheel on paper → photo → 3D model" is a 10-second demo that converts skeptics. Also legitimizes the *Impact / Vision* (40 pts) claim that the tool serves non-engineers — many of whom sketch faster than they type.

## Non-goals

- Persisting the image in GCS or in the session
- Multi-image input
- OCR of typed text in the image (Gemma handles it natively if present)
- Annotating the image with arrows / overlays back to the user
- Refining the intent through follow-up images
- Sketch input on `/refine` (deterministic merge only — unchanged)

## Architecture

### Transport

Base64-in-JSON. Keeps `apiStream()` and the SSE response stream unchanged. No multipart parser added to FastAPI.

```
ChatInput
  └─ File (PNG/JPEG/WebP, ≤ 4 MB)
     └─ FileReader.readAsDataURL → base64 (strip "data:image/...;base64," prefix)
        └─ POST /interpret { prompt, session_id, image_b64, image_mime }
            └─ Orchestrator.run(user_prompt, image=ImageInput(...))
                └─ VertexGemmaClient.generate adds Part.from_data(mime, bytes)
```

### Contract changes

**`InterpretRequest` (apps/backend/services/interpreter/api/dto.py):**

```python
class InterpretRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=2000)
    session_id: str | None = None
    image_b64: str | None = Field(default=None, max_length=6_000_000)   # ~4 MB binary
    image_mime: Literal["image/png", "image/jpeg", "image/webp"] | None = None
```

Validation rules (Pydantic `model_validator(mode="after")`):
- `image_b64` and `image_mime` must be both set or both absent.
- Decoded byte length ≤ 4_194_304 (4 MiB).
- Base64 must decode without error.

**New domain object (apps/backend/services/interpreter/agent/gemma_client.py):**

```python
@dataclass(frozen=True)
class ImageInput:
    mime_type: str
    data: bytes
```

**`GemmaProtocol.generate(...)`** gains an optional `image: ImageInput | None = None` kwarg.

**`Orchestrator.run(...)`** gains the same optional kwarg and forwards it to `gemma.generate`.

### Vertex client wiring

`VertexGemmaClient.generate` builds the `contents` list. When `image` is present, append `Part.from_data(mime_type=image.mime_type, data=image.data)` AFTER `Part.from_text(user_prompt)` in the final user-turn `Content`. (Vertex AI tolerates either order; we put text last so the prompt anchors the model's task.)

The image is sent only on the initial turn — never replayed from session history. Session messages remain text-only (we append the text prompt to the session, not the image bytes).

### Prompt update

`apps/backend/prompts/interpreter_system.md` gains a new section after "## Units":

```markdown
## Sketches & reference images

If the user attaches an image:
- Treat it as a **hand-drawn sketch** or **reference photo** of the desired mechanical part.
- Read any visible **dimension annotations** (e.g. "Ø500 mm", "300 mm", "RPM=3000") as if the user typed them.
- Use the **shape** to disambiguate the primitive (a circle with a hole = `Flywheel_Rim`; a rectangular panel with a fold line = `Hinge_Panel`).
- If the sketch contradicts the text, prefer **dimensions from the sketch** and **intent from the text**.
- If you cannot read a dimension, mark it `missing` — do NOT invent.
```

Plus one ES few-shot:

```markdown
### Example 3 (ES + sketch)

User text: "Diseñá esto"
User image: hand drawing of a disc, "Ø600 mm" labeled outside, "Ø100 mm" labeled at center hole, "espesor 50 mm" arrow, "1500 RPM" written below.

Expected output:
{
  "type": "Flywheel_Rim",
  "fields": {
    "outer_diameter_m": {"value": "600 mm", "source": "extracted", "original": "Ø600 mm"},
    "inner_diameter_m": {"value": "100 mm", "source": "extracted", "original": "Ø100 mm"},
    "thickness_m": {"value": "50 mm", "source": "extracted", "original": "espesor 50 mm"},
    "rpm": {"value": "1500 rpm", "source": "extracted", "original": "1500 RPM"}
  },
  "composed_of": ["Shaft", "Bearing_Housing"]
}
```

### Frontend UX

**ChatInput** gains:
1. **Paperclip icon button** to the LEFT of the text input. `aria-label`: `chat.attach_aria` ("Attach sketch / Adjuntar boceto").
2. Hidden `<input type="file" accept="image/png,image/jpeg,image/webp">`.
3. On file selected → validate `size ≤ 4 MB`, type matches allowlist → encode to base64 → store `{ file, dataUrl, b64, mime }` in local state.
4. **Preview row** above the text input when an attachment exists: 56×56 thumbnail (`dataUrl`) + filename + size + X button. Click X clears state.
5. On submit: `onSubmit(text, attachment?)`.
6. After successful send → clear attachment (one-shot).

**Validation errors** surface as toasts: "Image must be PNG/JPG/WebP" / "Image must be under 4 MB".

**i18n keys (new):**
- `chat.attach_aria`
- `chat.attach_remove`
- `chat.image_too_large` ("Image must be under 4 MB")
- `chat.image_bad_type` ("PNG, JPG or WebP only")

### Streaming hook

`useInterpretStream.start(prompt, sessionId, attachment?)` accepts an optional `{ b64: string, mime: string }`. Posted as `{ prompt, session_id, image_b64, image_mime }`.

No change to `SSEEvent` types — the response stream stays text + final_json.

## Failure modes

| Failure | Handling |
|---|---|
| File > 4 MB | Frontend rejects with toast. No request sent. |
| Wrong MIME | Frontend rejects with toast. |
| Base64 corrupted in transit | Pydantic validator → 422 + `INVALID_JSON_RETRY_FAILED`. |
| Vertex returns "image rejected" | Orchestrator emits `error` SSE with `INTERNAL_ERROR`. User can retry without image. |
| Vertex multimodal latency spike | Existing `timeout_seconds=10` covers; circuit breaker trips after 2 consecutive failures (unchanged). |

## Testing strategy

**Backend (pytest):**
1. DTO accepts text-only request unchanged (back-compat).
2. DTO accepts well-formed image_b64+image_mime; computes decoded byte length.
3. DTO rejects mime outside allowlist (422).
4. DTO rejects when only one of {image_b64, image_mime} is set.
5. DTO rejects image_b64 that decodes > 4 MiB.
6. DTO rejects malformed base64.
7. `VertexGemmaClient` (mock SDK): when `image` kwarg present, the built `contents` list contains a `Part.from_data` call with matching mime + bytes.
8. `Orchestrator.run` threads `image` through to `gemma.generate`.
9. Router test: POST with image triggers orchestrator with image set; session history stores text-only.

**Frontend (vitest):**
1. ChatInput renders attach button.
2. Selecting a 5 MB file fires toast, leaves state clean.
3. Selecting a `.gif` fires toast.
4. Selecting a valid PNG renders preview with filename.
5. Clicking X removes preview.
6. Submit with attachment calls `onSubmit` with `{ text, attachment: { b64, mime } }`.
7. After submit, attachment state clears.
8. `useInterpretStream.start` posts `image_b64` and `image_mime` when attachment provided.

**E2E (manual, Chrome DevTools):**
1. On Vercel prod: select preset=blank, attach the flywheel sketch from `/private/tmp/flywheel-sketch.png`, type "Use this as reference", submit, observe `Flywheel_Rim` returned with extracted dimensions.

## Out of scope (deferred)

- Cropping / rotation UI for the uploaded image
- Drawing tool inline (HTML canvas)
- Saving the sketch to GCS for the engineering report
- Sketch in `/explain` or `/document` paths
