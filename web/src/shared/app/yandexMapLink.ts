// Branch coordinates are picked on a map (BranchMap); what stays here is
// the outbound link every client-facing surface uses to open that pin.
//
// Yandex takes **longitude,latitude** — the opposite of the lat/lon order the
// API stores, which is exactly the swap this module exists to get right once.

/** A link back to the pin, for every surface that shows a branch. */
export function yandexMapUrl(
  latitude: number | string | null | undefined,
  longitude: number | string | null | undefined,
): string | null {
  const lat = Number(latitude)
  const lon = Number(longitude)
  if (latitude == null || longitude == null) return null
  if (!Number.isFinite(lat) || !Number.isFinite(lon)) return null
  // `pt` drops the pin, `ll` centres on it — without `pt` the map opens on the
  // right spot with nothing marked.
  return `https://yandex.uz/maps/?ll=${lon}%2C${lat}&z=17&pt=${lon}%2C${lat}`
}
