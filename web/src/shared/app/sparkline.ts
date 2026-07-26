// AB-119: geometry for the dashboard trend lines. Pure on purpose — the shapes
// a sparkline has to survive (all-zero on a fresh platform, one lonely bucket,
// a single non-zero spike) are exactly the ones that look broken if unhandled,
// and they are cheaper to pin here than to catch by eye.

export const SPARK_WIDTH = 104
export const SPARK_HEIGHT = 26

// Keeps the stroke and the end dot inside the viewBox instead of clipped at it.
const PAD = 3
const BASE = SPARK_HEIGHT - PAD
const TOP = PAD

export interface SparklineGeometry {
  /** `points` for the trend polyline. */
  line: string
  /** Closed `d` for the fill under the line; empty when there is nothing to fill. */
  area: string
  /** The newest bucket, for the end dot; null when the series is flat. */
  last: { x: number; y: number } | null
  /** Every bucket is zero — draw a baseline rule, not a chart. */
  flat: boolean
}

function round(value: number): number {
  return Math.round(value * 100) / 100
}

export function sparklineGeometry(values: number[]): SparklineGeometry {
  const points = values.length === 1 ? [values[0] ?? 0, values[0] ?? 0] : values
  const peak = Math.max(0, ...points)
  const baseline = `${PAD},${BASE} ${SPARK_WIDTH - PAD},${BASE}`

  // A new platform reads every series as zero. A flat rule on the baseline is
  // the honest picture of that; an auto-scaled line would invent a trend.
  if (points.length < 2 || peak === 0) {
    return { line: baseline, area: '', last: null, flat: true }
  }

  const step = (SPARK_WIDTH - PAD * 2) / (points.length - 1)
  const coords = points.map((value, index) => ({
    x: round(PAD + index * step),
    y: round(BASE - (Math.max(0, value) / peak) * (BASE - TOP)),
  }))
  const line = coords.map((point) => `${point.x},${point.y}`).join(' ')
  const first = coords[0]
  const last = coords[coords.length - 1]
  if (!first || !last) return { line: baseline, area: '', last: null, flat: true }

  const area = [
    `M${first.x},${BASE}`,
    ...coords.map((point) => `L${point.x},${point.y}`),
    `L${last.x},${BASE}`,
    'Z',
  ].join(' ')

  return { line, area, last, flat: false }
}
