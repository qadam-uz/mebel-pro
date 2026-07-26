import { describe, expect, it } from 'vitest'

import { SPARK_HEIGHT, SPARK_WIDTH, sparklineGeometry } from '@/shared/app/sparkline'

const BASE = SPARK_HEIGHT - 3
const TOP = 3

describe('sparklineGeometry', () => {
  it('flattens an all-zero series instead of inventing a trend', () => {
    // The state a brand-new platform sits in — it must render as an empty
    // baseline, never as a chart shape or an empty box.
    const geometry = sparklineGeometry([0, 0, 0, 0, 0])

    expect(geometry.flat).toBe(true)
    expect(geometry.area).toBe('')
    expect(geometry.last).toBeNull()
    expect(geometry.line).toBe(`3,${BASE} ${SPARK_WIDTH - 3},${BASE}`)
  })

  it('flattens an empty series', () => {
    expect(sparklineGeometry([]).flat).toBe(true)
  })

  it('scales to the peak with zero pinned to the baseline', () => {
    const geometry = sparklineGeometry([0, 5, 10])

    expect(geometry.flat).toBe(false)
    expect(geometry.line).toBe(
      `3,${BASE} ${SPARK_WIDTH / 2},${(BASE + TOP) / 2} ${SPARK_WIDTH - 3},${TOP}`,
    )
    expect(geometry.last).toEqual({ x: SPARK_WIDTH - 3, y: TOP })
  })

  it('keeps a single spike readable rather than clipping it', () => {
    // Sparse data is the normal case on this dashboard: one non-zero bucket
    // must still peak at the top of the box, with the rest on the baseline.
    const geometry = sparklineGeometry([0, 0, 7, 0])

    expect(geometry.flat).toBe(false)
    expect(geometry.line.split(' ').map((point) => point.split(',')[1])).toEqual([
      `${BASE}`,
      `${BASE}`,
      `${TOP}`,
      `${BASE}`,
    ])
  })

  it('draws a one-bucket series as a level line with an end dot', () => {
    const geometry = sparklineGeometry([4])

    expect(geometry.flat).toBe(false)
    expect(geometry.last).toEqual({ x: SPARK_WIDTH - 3, y: TOP })
  })

  it('closes the area path back down to the baseline', () => {
    const geometry = sparklineGeometry([1, 2])

    expect(geometry.area.startsWith(`M3,${BASE}`)).toBe(true)
    expect(geometry.area.endsWith(`L${SPARK_WIDTH - 3},${BASE} Z`)).toBe(true)
  })
})
