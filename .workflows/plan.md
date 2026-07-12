# Cutting Import XML

## Problem

The cutting import flow currently supports CSV only. БАЗИС-Мебельщик also exports a structured
`Спецификация в XML` file whose named elements can be parsed without the CSV column-mapping step.

## Approach

Add XML as a second import source that produces the existing `ImportedPart` IR. The backend
detects content first, dispatches XML to a new safe XML parser, and keeps CSV behavior intact.
The frontend keeps material picking/report/load unchanged, but skips the mapping step for XML.

Key decisions:

- XML root must be `Проект`; other XML shapes are rejected as unsupported.
- XML parsing uses `defusedxml.ElementTree.fromstring(bytes)` so declared encodings are honored
  and entity expansion is blocked.
- Shared CSV parser helpers move to `imports/common.py` to avoid duplicating number parsing,
  group keys, warnings, and cell text normalization.
- Product quantity multiplies part quantity before the 100-piece cap.
- Geometry we do not model is imported as a rectangle with row warnings, not silently ignored.

## Acceptance criteria

- CSV imports still return `needs_mapping` first and existing CSV tests stay green.
- XML `<Проект>` imports return `parsed` on the first parse call.
- XML panel objects flatten across products, apply product quantity, produce panel/edge groups,
  preserve `follow_grain`, map side lists 1/2/3/4 to top/bottom/left/right, and report ignored
  non-panel objects.
- XML non-rectangular panels, holes, grooves, and `СписокКромокСМЧертеж` produce warnings.
- Non-`Проект` XML, xlsx/ole2, empty files, and too-large files are rejected with existing error
  handling.
- The wizard accepts `.csv` and `.xml`; XML renders a 3-step flow and skips column mapping.
- Cutting feature docs describe CSV/XML import behavior.

## Out of scope

- ObjTree/script XML export parsing.
- Holes/grooves/CNC geometry modeling.
- Cross-grain modeling beyond existing `follow_grain`.
- Auto material matching.
- Database persistence or migration.

## Affected docs

- `docs/ref/features/cutting.md`

## Contracts & seams

- `ImportParsedResponse` adds `source_format` and `ignored_object_count`.
- `ImportNeedsMappingResponse` adds `source_format`.
- `SourceFormat` is `csv | bazis_xml`.
- Warning codes add `non_rectangular`, `ignored_holes`, `ignored_grooves`, `edge_see_drawing`.
- Existing endpoint stays `POST /api/v1/client/cutting/import/parse`.

## Steps

1. Backend shared import helpers and dispatcher.
2. XML parser + fixture + backend tests.
3. Frontend type/store changes.
4. Wizard XML flow and tests.
5. Docs update.
6. Format, lint, type, and targeted test verification.

## Test plan

- Backend unit/parser tests for detection, XML IR, encoding, unsupported XML, and too many pieces.
- Backend endpoint test for first-call XML parsed response.
- Frontend store unit test for XML-shaped parsed response and new warnings.
- Frontend wizard test for XML 3-step flow/no mapping.
- Existing targeted CSV import tests remain green.

## Risks & rollback

Main risk is overfitting XML element names without a real export. The fixture pins the expected
schema shape; rollback is to remove XML dispatch and leave CSV path untouched.
