import type { ClientCatalogMaterialOption } from '@/shared/stores/cutting'

/**
 * Whether a tape is narrower than the edge it has to cover.
 *
 * The last survivor of the CB-130 ranking helpers: SPEC_CLIENT_UX_MVP §13 W2
 * moved both editors onto the group-tape model, where a tape *decor* is chosen
 * once per material group rather than ranked per part, so `edgeRank` /
 * `rankedEdges` / `recommendedEdge` went with the per-part tape list they fed
 * (`cuttingGroupTape.autoTapeDecorForPanel` carries the decor→colour ladder
 * they used to open with). This one is a fact about the tape rather than a
 * ranking, and the workshop's tape picker still marks it.
 */
export function edgeTooNarrow(
  panelThickness: number | null | undefined,
  edge: Pick<ClientCatalogMaterialOption, 'tape_width_mm'> | null | undefined,
): boolean {
  if (!edge || panelThickness == null || !Number.isFinite(panelThickness)) return false
  // A tape with no recorded width is unknown, not narrow. `Number(null)` is 0,
  // which used to make every unmeasured tape in a branch's catalog read as
  // «Qirradan tor» — invisible while this only annotated a registry chip, and
  // wrong now that it marks rows in the tape picker.
  if (edge.tape_width_mm == null) return false
  const width = Number(edge.tape_width_mm)
  return Number.isFinite(width) && width < panelThickness
}
