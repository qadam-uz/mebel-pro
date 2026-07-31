import type { MaterialKind, MaterialWriteRequest, PanelMaterialType } from '@/shared/stores/admin'

export interface AdminMaterialFormState {
  kind: MaterialKind
  manufacturerId: string
  type: PanelMaterialType
  thicknessMm: string
  color: string
  decorCode: string
  panelLengthMm: string
  panelWidthMm: string
  edgeWidthMm: string
  grainDirection: boolean
  imageFileId: string | null
}

const TYPE_LABELS: Record<PanelMaterialType, string> = {
  dsp: 'LDSP',
  mdf: 'MDF',
  plywood: 'Fanera',
  natural_wood: "Yog'och",
  other: 'List',
}

export function buildAdminMaterialWriteRequest(form: AdminMaterialFormState): MaterialWriteRequest {
  const base = {
    manufacturer_id: form.manufacturerId,
    thickness_mm: form.thicknessMm,
    color: form.color,
    decor_code: form.decorCode || null,
    image_file_id: form.imageFileId,
  }
  if (form.kind === 'panel') {
    return {
      ...base,
      kind: 'panel',
      type: form.type,
      panel_length_mm: Number(form.panelLengthMm),
      panel_width_mm: Number(form.panelWidthMm),
      grain_direction: form.grainDirection,
    }
  }
  return {
    ...base,
    kind: 'edge',
    edge_width_mm: Number(form.edgeWidthMm),
  }
}

export function composeMaterialName(
  form: AdminMaterialFormState,
  manufacturerName: string | null | undefined,
): string {
  const manufacturer = normalizeText(manufacturerName) || '...'
  const color = normalizeText(form.color) || '...'
  const decor = normalizeText(form.decorCode)
  const firstSegment =
    form.kind === 'panel'
      ? [TYPE_LABELS[form.type], manufacturer, decor].filter(Boolean).join(' ')
      : ['Kromka', manufacturer, decor].filter(Boolean).join(' ')
  const dimensions =
    form.kind === 'panel'
      ? `${form.panelLengthMm || '0'}×${form.panelWidthMm || '0'}×${formatMm(form.thicknessMm)} mm`
      : `${formatMm(form.thicknessMm)}×${form.edgeWidthMm || '0'} mm`
  return `${firstSegment} · ${color} · ${dimensions}`
}

function normalizeText(value: string | null | undefined): string {
  return (value ?? '').trim().split(/\s+/).filter(Boolean).join(' ')
}

function formatMm(value: string): string {
  const parsed = Number(value)
  if (!Number.isFinite(parsed)) return value || '0'
  return parsed.toString()
}
