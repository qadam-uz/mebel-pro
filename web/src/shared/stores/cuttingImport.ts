import { ApiError, api, apiErrorCode } from '@/shared/api/client'
import { authInit } from '@/shared/app/authInit'
import type { CuttingPart } from '@/shared/stores/cutting'

export const MAX_IMPORT_FILE_BYTES = 1_048_576

export type ImportRole =
  | 'length_mm'
  | 'width_mm'
  | 'quantity'
  | 'material'
  | 'thickness_mm'
  | 'follow_grain'
  | 'edge_top'
  | 'edge_bottom'
  | 'edge_left'
  | 'edge_right'

export type ImportStatus = 'needs_mapping' | 'parsed'
export type ImportSkipReason =
  | 'non_numeric_length'
  | 'non_numeric_width'
  | 'non_numeric_quantity'
  | 'quantity_not_integer'
  | 'quantity_not_positive'
  | 'dimension_not_positive'
  | 'dimension_too_large'
export type ImportWarningCode = 'dimension_rounded' | 'quantity_defaulted' | 'grain_token_unknown'

export interface ImportParseOptions {
  skip_rows?: number
  mapping?: Partial<Record<ImportRole, number>>
}

export interface ImportNeedsMappingResponse {
  status: 'needs_mapping'
  grid: (string | null)[][]
  guessed_mapping: Partial<Record<ImportRole, number>>
  guessed_skip_rows: number
}

export interface ImportSkippedRow {
  row: number
  reason: ImportSkipReason
  preview: string
}

export interface ImportWarning {
  code: ImportWarningCode
  rows: number[]
}

export interface ImportedPart {
  row: number
  length_mm: number
  width_mm: number
  quantity: number
  material_key: string
  follow_grain: boolean
  edges: {
    top: string | null
    bottom: string | null
    left: string | null
    right: string | null
  }
}

export interface ImportPanelMaterialGroup {
  key: string
  label: string
  part_count: number
  thickness_hint: string | null
}

export interface ImportEdgeMaterialGroup {
  key: string
  label: string
  side_count: number
}

export interface ImportParsedResponse {
  status: 'parsed'
  parts: ImportedPart[]
  panel_materials: ImportPanelMaterialGroup[]
  edge_materials: ImportEdgeMaterialGroup[]
  skipped_rows: ImportSkippedRow[]
  warnings: ImportWarning[]
  total_parts: number
  total_pieces: number
}

export type ImportParseResponse = ImportNeedsMappingResponse | ImportParsedResponse
export type ImportLoadMode = 'append' | 'replace'

export const IMPORT_ROLES: ImportRole[] = [
  'length_mm',
  'width_mm',
  'quantity',
  'material',
  'thickness_mm',
  'follow_grain',
  'edge_top',
  'edge_bottom',
  'edge_left',
  'edge_right',
]

export const IMPORT_ROLE_LABELS: Record<ImportRole, string> = {
  length_mm: 'Uzunlik (mm)',
  width_mm: 'Kenglik (mm)',
  quantity: 'Soni',
  material: 'Material',
  thickness_mm: 'Qalinlik (mm)',
  follow_grain: 'Tekstura',
  edge_top: 'Kromka: yuqori',
  edge_bottom: 'Kromka: past',
  edge_left: 'Kromka: chap',
  edge_right: "Kromka: o'ng",
}

export const IMPORT_SKIP_REASON_LABELS: Record<ImportSkipReason, string> = {
  non_numeric_length: 'uzunlik raqam emas',
  non_numeric_width: 'kenglik raqam emas',
  non_numeric_quantity: 'soni raqam emas',
  quantity_not_integer: 'soni butun son emas',
  quantity_not_positive: 'soni 1 dan kichik',
  dimension_not_positive: "o'lcham noto'g'ri",
  dimension_too_large: "o'lcham 10 m dan katta",
}

export const IMPORT_WARNING_LABELS: Record<ImportWarningCode, string> = {
  dimension_rounded: "O'lcham mm gacha yaxlitlandi",
  quantity_defaulted: "Soni ko'rsatilmagan - 1 deb olindi",
  grain_token_unknown: 'Tekstura belgisi tushunarsiz - "bo\'ylab" deb olindi',
}

function cleanOptions(options: ImportParseOptions | undefined): ImportParseOptions | undefined {
  if (!options) return undefined
  const payload: ImportParseOptions = {}
  if (options.skip_rows !== undefined) payload.skip_rows = options.skip_rows
  if (options.mapping) payload.mapping = options.mapping
  return Object.keys(payload).length > 0 ? payload : undefined
}

export async function parseCuttingImport(
  file: File,
  options?: ImportParseOptions,
): Promise<ImportParseResponse> {
  const form = new FormData()
  form.append('file', file)
  const payload = cleanOptions(options)
  if (payload) form.append('options', JSON.stringify(payload))
  return await api.postForm<ImportParseResponse>('/client/cutting/import/parse', form, authInit())
}

export function isImportMappingComplete(
  mapping: Partial<Record<ImportRole, number | null | undefined>>,
): boolean {
  const lengthCol = mapping.length_mm
  const widthCol = mapping.width_mm
  return (
    typeof lengthCol === 'number' &&
    typeof widthCol === 'number' &&
    Number.isInteger(lengthCol) &&
    Number.isInteger(widthCol) &&
    lengthCol !== widthCol
  )
}

export function areImportMaterialPicksComplete(
  parsed: Pick<ImportParsedResponse, 'panel_materials' | 'edge_materials'>,
  panelPicks: Record<string, string | null | undefined>,
  edgePicks: Record<string, string | null | undefined>,
): boolean {
  return (
    parsed.panel_materials.every((group) => !!panelPicks[group.key]) &&
    parsed.edge_materials.every((group) => !!edgePicks[group.key])
  )
}

function picked(
  picks: Record<string, string | null | undefined>,
  key: string,
  kind: 'panel' | 'edge',
): string {
  const value = picks[key]
  if (!value) throw new Error(`Missing ${kind} pick for ${key}`)
  return value
}

export function buildImportedParts(
  parsed: Pick<ImportParsedResponse, 'parts'>,
  panelPicks: Record<string, string | null | undefined>,
  edgePicks: Record<string, string | null | undefined>,
  uuidFactory: () => string = () => crypto.randomUUID?.() ?? `import-${Date.now()}`,
): CuttingPart[] {
  return parsed.parts.map((part) => ({
    part_ref: uuidFactory(),
    material_id: picked(panelPicks, part.material_key, 'panel'),
    material_source: 'shop',
    follow_grain: part.follow_grain,
    length_mm: part.length_mm,
    width_mm: part.width_mm,
    quantity: part.quantity,
    edge_top: part.edges.top
      ? { material_id: picked(edgePicks, part.edges.top, 'edge'), source: 'shop' }
      : null,
    edge_bottom: part.edges.bottom
      ? { material_id: picked(edgePicks, part.edges.bottom, 'edge'), source: 'shop' }
      : null,
    edge_left: part.edges.left
      ? { material_id: picked(edgePicks, part.edges.left, 'edge'), source: 'shop' }
      : null,
    edge_right: part.edges.right
      ? { material_id: picked(edgePicks, part.edges.right, 'edge'), source: 'shop' }
      : null,
  }))
}

export function applyImportedParts(
  existing: CuttingPart[],
  imported: CuttingPart[],
  mode: ImportLoadMode,
): CuttingPart[] {
  return mode === 'replace' ? [...imported] : [...existing, ...imported]
}

export function cuttingImportErrorLabel(error: unknown): string {
  const fallback = "Faylni import qilib bo'lmadi. Qayta urinib ko'ring."
  if (!(error instanceof ApiError)) return fallback
  const code = apiErrorCode(error)
  const details =
    typeof error.body === 'object' && error.body !== null
      ? (error.body as { details?: { total_pieces?: unknown } }).details
      : undefined
  if (code === 'unsupported_format') {
    return "Bu fayl turi qo'llab-quvvatlanmaydi - faqat CSV. БАЗИС-Мебельщик'da «Спецификация в CSV» orqali, Excel'da «Сохранить как -> CSV» qilib saqlang."
  }
  if (code === 'file_too_large') return 'Fayl 1 MB dan katta'
  if (code === 'empty_file') return "Fayl bo'sh"
  if (code === 'invalid_mapping') return "Ustunlar mosligi noto'g'ri"
  if (code === 'too_many_parts') {
    const total = typeof details?.total_pieces === 'number' ? details.total_pieces : null
    return total
      ? `Faylda ${total} dona detal - bir optimallashtirishga eng ko'pi 100 dona. Faylni bo'lib yuklang`
      : "Faylda detal ko'p - bir optimallashtirishga eng ko'pi 100 dona. Faylni bo'lib yuklang"
  }
  return fallback
}
