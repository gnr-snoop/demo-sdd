# Test Fixtures: Onboarding (spec 002, T037)

Fixture images for the onboarding test suite. All `.jpg` fixtures are **valid
minimal JPEGs** (Pillow decodes them successfully). Rejection cases encode their
scenario in a **JPEG COM (comment) segment** so that:

1. Pillow decode succeeds (the image is well-formed), and
2. `ScriptableMockDetector` still sees the marker in the **raw request bytes**
   (it substring-searches the raw bytes, not the decoded pixels).

## Marker convention (`ScriptableMockDetector`)

| Fixture | Marker | Detector result |
|---------|--------|-----------------|
| `one_face.jpg` | _(none)_ | `face_count=1`, `score=0.99` (default — happy path) |
| `no_face.jpg` | `NOFACE` | `face_count=0` → `no_face` (422) |
| `multi_face.jpg` | `MULTIFACE` | `face_count=2` → `multiple_faces` (422) |
| `low_quality.jpg` | `LOWQUALITY` | `face_count=1`, `score=0.1` → `insufficient_quality` (422) |

## Other fixtures

| Fixture | Purpose |
|---------|---------|
| `not_an_image.txt` | Plain text — undecodable → `invalid_image` (422) |
| `oversized.jpg` | Valid JPEG > 2 MB → `invalid_image` (422) |

## Regenerating

The fixtures are generated programmatically with Pillow (see the spec 002
implementation). A COM segment is inserted right after the JPEG SOI (`FFD8`)
as `FFFE <len> <marker>`. To regenerate, build a small RGB image, save as JPEG,
and splice the COM segment in.
