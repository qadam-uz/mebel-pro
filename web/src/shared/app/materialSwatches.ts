export interface MaterialSwatchSource {
  id: string
  name: string
  color: string
  decor_code: string | null
}

const FALLBACK_SWATCHES = ['sw-1', 'sw-2', 'sw-3', 'sw-5', 'sw-6', 'sw-10']

function hash(value: string) {
  let result = 0
  for (let index = 0; index < value.length; index += 1) {
    result = (result * 31 + value.charCodeAt(index)) >>> 0
  }
  return result
}

export function materialSwatchClass(material: MaterialSwatchSource) {
  const text = [material.color, material.decor_code, material.name].join(' ').toLowerCase()
  if (/(white|oq|бел|snow|alpine)/.test(text)) return 'sw-7'
  if (/(black|qora|черн|graphite|anthracite)/.test(text)) return 'sw-8'
  if (/(grey|gray|kul|сер|silver|metal)/.test(text)) return 'sw-4'
  if (/(walnut|yong|орех|venge|wenge|dark|espresso)/.test(text)) return 'sw-3'
  if (/(oak|dub|дуб|sonoma|beech|buk|maple|cream|beige)/.test(text)) return 'sw-2'
  return FALLBACK_SWATCHES[hash(`${material.id}:${text}`) % FALLBACK_SWATCHES.length]
}
