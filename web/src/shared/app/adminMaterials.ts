import type { MaterialKind, MaterialWriteRequest, PanelMaterialType } from '@/shared/stores/admin'

export interface AdminMaterialFormState {
  kind: MaterialKind
  manufacturerId: string
  type: PanelMaterialType
  name: string
  thicknessMm: string
  color: string
  decorCode: string
  panelLengthMm: string
  panelWidthMm: string
  grainDirection: boolean
  imageFileId: string | null
}

export function buildAdminMaterialWriteRequest(form: AdminMaterialFormState): MaterialWriteRequest {
  const base = {
    manufacturer_id: form.manufacturerId,
    name: form.name,
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
  }
}
