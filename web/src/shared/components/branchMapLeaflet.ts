// Everything `BranchMap.vue` needs from Leaflet, in one module it imports
// **dynamically**.
//
// Leaflet plus its stylesheet is ~161 kB of JS and ~15 kB of CSS — more than
// the whole workshop entry chunk. Imported statically from `BranchMap.vue` it
// landed in the shared chunk behind both branch screens, so opening the branch
// list paid for a map the operator may never scroll to. Behind an `import()`
// it becomes its own chunk, fetched when a map actually mounts, and Vite
// carries the CSS with it.
//
// The icon is built here rather than in the component because `L.icon()` needs
// the library: keeping it beside the import means the component never holds a
// module-scope reference to Leaflet at all.

import L from 'leaflet'
import 'leaflet/dist/leaflet.css'

// Leaflet ships its marker icons as bundler-hostile relative URLs; pointing at
// the packaged assets keeps the pin visible under Vite without copying files.
export const markerIcon = L.icon({
  iconUrl: new URL('leaflet/dist/images/marker-icon.png', import.meta.url).href,
  iconRetinaUrl: new URL('leaflet/dist/images/marker-icon-2x.png', import.meta.url).href,
  shadowUrl: new URL('leaflet/dist/images/marker-shadow.png', import.meta.url).href,
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  shadowSize: [41, 41],
})

export { L }
