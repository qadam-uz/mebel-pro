// Factory for lazy placeholder route components. Returns an async component
// loader that renders <PlaceholderView> with a fixed title — so a router can
// list many not-yet-built screens without a file per screen.

import { defineAsyncComponent, h } from 'vue'
import type { Component } from 'vue'

export function placeholder(title: string, sub?: string): () => Promise<Component> {
  return () =>
    Promise.resolve(
      defineAsyncComponent(() =>
        import('@/shared/ui/PlaceholderView.vue').then((m) => ({
          name: 'PlaceholderRoute',
          render: () => h(m.default, { title, sub }),
        })),
      ),
    )
}
