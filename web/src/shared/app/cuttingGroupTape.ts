import { edgeFields } from '@/shared/app/cuttingDisplay'
import { formatMm, snapshotMaterialLabel } from '@/shared/app/materialLabel'
import type { ClientCatalogMaterialOption, CuttingPart } from '@/shared/stores/cutting'

/**
 * The client editor's kromka model (SPEC_CLIENT_UX_MVP §7.1): **the tape decor
 * belongs to the material group, the thickness to the side.**
 *
 * Nothing here is persisted. A side still stores the concrete `kromka` branch
 * material id it always did — the group's tape decor is *derived* on every read
 * from (a) the pick the client made in this editor, (b) what the group's banded
 * sides already carry, or (c) the branch's tape of the board's own decor. That
 * is what makes "storage is unchanged, no backend change" true: the optimiser,
 * the quote, the PDF and the whole workshop side keep seeing exactly what they
 * saw before.
 *
 * Every function here is pure so the resolution rules are unit-testable without
 * mounting the editor.
 */

/** One thickness the branch carries a tape decor in. */
export interface TapeVariant {
  material: ClientCatalogMaterialOption
  thicknessMm: number
}

/** One tape decor the branch carries, with every thickness it stocks it in. */
export interface TapeDecor {
  key: string
  /** `Egger H1145 · Dub Bardolino` — the identity half of the canonical label. */
  label: string
  imageFileId: string | null
  /** The decor's own `name`, for `colorForMaterial` — see cuttingDisplay. */
  swatchName: string
  /** Ascending by thickness; never empty. */
  variants: TapeVariant[]
}

function lower(value: string | null | undefined): string {
  return (value ?? '').trim().toLowerCase()
}

/**
 * Decor identity as the catalog defines it: manufacturer + code (or, with no
 * code, the decor name). Deliberately **type-free** — a board is `ldsp` and its
 * tape is `kromka`, and matching one to the other is the whole point.
 */
export function decorIdentityKey(material: ClientCatalogMaterialOption): string {
  return `${material.manufacturer_id}|${lower(material.code) || lower(material.name)}`
}

/**
 * `LDSP Egger H1145 · Dub Bardolino` — the label with no format tail. The
 * substrate stays in it: the material picker lists boards of every type in one
 * list, and «LDSP» vs «MDF» is the first thing a client sorts them by.
 */
export function decorTitle(material: ClientCatalogMaterialOption): string {
  return snapshotMaterialLabel(
    {
      manufacturer_name: material.manufacturer_name,
      type: material.type,
      code: material.code,
      name: material.name,
    },
    material.name || material.id.slice(0, 8),
  )
}

/**
 * `Egger H1145 · Dub Bardolino` — the same label with the substrate dropped.
 *
 * Every row in a tape list is a tape, and every line that names one already
 * says so («Kromka: …», «Rangi mos kromkani tanlang»), so carrying the type
 * word into the title only produces «Kromka: Kromka Egger H3734».
 */
export function tapeDecorTitle(material: ClientCatalogMaterialOption): string {
  return snapshotMaterialLabel(
    {
      manufacturer_name: material.manufacturer_name,
      type: null,
      code: material.code,
      name: material.name,
    },
    material.name || material.id.slice(0, 8),
  )
}

function thicknessOf(material: ClientCatalogMaterialOption): number {
  const value = Number(material.thickness_mm)
  return Number.isFinite(value) ? value : 0
}

/** `0.4 / 2` — the thicknesses a decor is carried in, for the group line. */
export function tapeThicknessList(decor: TapeDecor): string {
  return decor.variants.map((variant) => formatMm(variant.material.thickness_mm)).join(' / ')
}

/**
 * The branch's tape catalog folded into one row per decor. `edgeOptions` is
 * already tape-only (the store's `tape: true` listing), so no type filter here.
 */
export function groupTapeDecors(edgeOptions: readonly ClientCatalogMaterialOption[]): TapeDecor[] {
  const decors: TapeDecor[] = []
  const indexByKey = new Map<string, number>()
  for (const material of edgeOptions) {
    const key = decorIdentityKey(material)
    let decor = decors[indexByKey.get(key) ?? -1]
    if (!decor) {
      decor = {
        key,
        label: tapeDecorTitle(material),
        imageFileId: material.image_file_id,
        swatchName: material.name,
        variants: [],
      }
      indexByKey.set(key, decors.length)
      decors.push(decor)
    }
    // The first row carrying an image wins: a branch may have priced one
    // thickness before the decor picture was uploaded.
    if (!decor.imageFileId && material.image_file_id) decor.imageFileId = material.image_file_id
    decor.variants.push({ material, thicknessMm: thicknessOf(material) })
  }
  for (const decor of decors) {
    decor.variants.sort((left, right) => left.thicknessMm - right.thicknessMm)
  }
  return decors
}

export function findTapeDecor(decors: readonly TapeDecor[], key: string | null): TapeDecor | null {
  if (!key) return null
  return decors.find((decor) => decor.key === key) ?? null
}

/** The decor a tape material belongs to, or null when it left the catalog. */
export function tapeDecorOfMaterial(
  decors: readonly TapeDecor[],
  materialId: string | null | undefined,
): TapeDecor | null {
  if (!materialId) return null
  return (
    decors.find((decor) => decor.variants.some((variant) => variant.material.id === materialId)) ??
    null
  )
}

/**
 * The branch's tape in the board's own decor — what §7.1 attaches automatically
 * when a material is added to the drawing.
 *
 * Same ladder as `edgeRank`: the catalog's decor identity first, then a plain
 * decor-name match, which is how a shop that stocks a matching tape under a
 * different manufacturer still gets picked up. No fuzzy third rung: a wrong
 * auto-attached colour is worse than asking.
 */
export function autoTapeDecorForPanel(
  panel: ClientCatalogMaterialOption | null | undefined,
  decors: readonly TapeDecor[],
): TapeDecor | null {
  if (!panel) return null
  const key = decorIdentityKey(panel)
  const byIdentity = decors.find((decor) => decor.key === key)
  if (byIdentity) return byIdentity
  const name = lower(panel.name)
  if (!name) return null
  return decors.find((decor) => lower(decor.swatchName) === name) ?? null
}

/** Every tape material id banded on this group's parts, in first-use order. */
export function groupBandedTapeIds(groupParts: readonly CuttingPart[]): string[] {
  const ids: string[] = []
  const seen = new Set<string>()
  for (const part of groupParts) {
    for (const side of edgeFields) {
      const materialId = part[side]?.material_id
      if (!materialId || seen.has(materialId)) continue
      seen.add(materialId)
      ids.push(materialId)
    }
  }
  return ids
}

export function groupHasBandedSide(groupParts: readonly CuttingPart[]): boolean {
  return groupParts.some((part) => edgeFields.some((side) => part[side]?.material_id))
}

export type TapeDecorSource = 'picked' | 'sides' | 'auto'

export interface GroupTapeResolution {
  decor: TapeDecor | null
  source: TapeDecorSource | null
}

/**
 * The group's tape decor, in the order the client would expect it:
 *
 * 1. what they picked for this group in this editor (`pickedKey`),
 * 2. what the group's sides already carry — a resumed draft keeps the tape it
 *    was banded with, even when the branch also stocks a matching one,
 * 3. the branch's tape of the board's decor (the §7.1 auto-attach),
 * 4. nothing — the line asks for a colour and the gate fires.
 */
export function resolveGroupTape(input: {
  panel: ClientCatalogMaterialOption | null | undefined
  groupParts: readonly CuttingPart[]
  decors: readonly TapeDecor[]
  pickedKey?: string | null
}): GroupTapeResolution {
  const picked = findTapeDecor(input.decors, input.pickedKey ?? null)
  if (picked) return { decor: picked, source: 'picked' }
  for (const materialId of groupBandedTapeIds(input.groupParts)) {
    const decor = tapeDecorOfMaterial(input.decors, materialId)
    if (decor) return { decor, source: 'sides' }
  }
  const auto = autoTapeDecorForPanel(input.panel, input.decors)
  if (auto) return { decor: auto, source: 'auto' }
  return { decor: null, source: null }
}

/**
 * The thickness a fresh band should take: the one last used in the drawing when
 * this decor carries it, else the thickest the decor is stocked in — a visible
 * edge is the common case, and 2 mm is what a shop puts on one.
 */
export function preferredVariant(
  decor: TapeDecor,
  lastThicknessMm: number | null | undefined,
): TapeVariant | null {
  if (decor.variants.length === 0) return null
  if (lastThicknessMm != null) {
    const exact = decor.variants.find((variant) => variant.thicknessMm === lastThicknessMm)
    if (exact) return exact
  }
  return decor.variants[decor.variants.length - 1]
}

/**
 * The variant closest to `thicknessMm`. Used when a group's tape changes to a
 * decor that is not stocked in every thickness the old one was: the band keeps
 * its side and lands on the nearest thickness rather than disappearing.
 */
export function nearestVariant(decor: TapeDecor, thicknessMm: number): TapeVariant | null {
  if (decor.variants.length === 0) return null
  let best = decor.variants[0]
  let bestDistance = Math.abs(best.thicknessMm - thicknessMm)
  for (const variant of decor.variants.slice(1)) {
    const distance = Math.abs(variant.thicknessMm - thicknessMm)
    // `<` not `<=`: on a tie the thinner variant wins, which is the sorted
    // order's first hit and the cheaper of the two.
    if (distance < bestDistance) {
      best = variant
      bestDistance = distance
    }
  }
  return best
}

export interface ReResolveOutcome {
  parts: CuttingPart[]
  /** A side landed on a thickness the new decor does not carry. */
  fellBack: boolean
  changed: boolean
}

/**
 * Re-point every banded side of one material group at a new tape decor, keeping
 * each side's thickness where the decor has it and falling back to the nearest
 * one where it does not (§7.1, "Changing the group tape").
 *
 * Returns a new array — the editor replaces `parts` wholesale so the autosave's
 * deep watch fires exactly once.
 */
export function reResolveGroupTape(input: {
  parts: readonly CuttingPart[]
  groupMaterialId: string
  decor: TapeDecor
  /** Thickness of the tape a side currently carries, by material id. */
  thicknessById: (materialId: string) => number | null
}): ReResolveOutcome {
  let fellBack = false
  let changed = false
  const parts = input.parts.map((part) => {
    if (part.material_id !== input.groupMaterialId) return part
    let touched = false
    const next = { ...part }
    for (const side of edgeFields) {
      const band = part[side]
      if (!band?.material_id) continue
      const currentThickness = input.thicknessById(band.material_id)
      const variant =
        currentThickness == null
          ? preferredVariant(input.decor, null)
          : (input.decor.variants.find((item) => item.thicknessMm === currentThickness) ??
            nearestVariant(input.decor, currentThickness))
      if (!variant) continue
      if (currentThickness != null && variant.thicknessMm !== currentThickness) fellBack = true
      if (variant.material.id === band.material_id) continue
      next[side] = { material_id: variant.material.id, source: 'shop' }
      touched = true
    }
    if (!touched) return part
    changed = true
    return next
  })
  return { parts, fellBack, changed }
}

/**
 * Which side of which part carries a tape that is NOT in the group's decor —
 * a legacy draft, or one banded before the client changed the group colour and
 * whose tape the branch has since dropped. §7.1 keeps those bands as they are
 * and names them read-only; only re-tapping a side adopts the group tape.
 */
export function foreignTapeIds(
  groupParts: readonly CuttingPart[],
  decor: TapeDecor | null,
): string[] {
  const inDecor = new Set(decor?.variants.map((variant) => variant.material.id) ?? [])
  return groupBandedTapeIds(groupParts).filter((id) => !inDecor.has(id))
}

/**
 * The gate (§7.1): material groups that band at least one side but have no tape
 * decor to band it with. «Hisoblash» refuses and scrolls to the first of these.
 */
export function groupsMissingTape<T extends { key: string; materialId: string | null }>(
  groups: readonly T[],
  partsOfGroup: (group: T) => readonly CuttingPart[],
  tapeOfGroup: (group: T) => TapeDecor | null,
): T[] {
  return groups.filter(
    (group) => groupHasBandedSide(partsOfGroup(group)) && tapeOfGroup(group) === null,
  )
}

/**
 * Per-thickness colour (§7.1). The tokens are the `tur-*` ramp, reused rather
 * than invented: the client is telling 0.4 from 2 mm at a glance on the diagram
 * and the chips, which is the same "tell these categories apart" job the ramp
 * already does elsewhere. Only paints when the part actually uses more than one
 * thickness — with a single one everything stays ink, per the spec.
 */
export function thicknessColorVar(thicknessMm: number): string {
  if (thicknessMm <= 0.5) return 'var(--color-tur-board)'
  if (thicknessMm <= 1.5) return 'var(--color-tur-mdf)'
  if (thicknessMm <= 2.5) return 'var(--color-tur-tape)'
  return 'var(--color-tur-wood)'
}
