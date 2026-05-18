import { globalIgnores } from 'eslint/config'
import { defineConfigWithVueTs, vueTsConfigs } from '@vue/eslint-config-typescript'
import pluginVue from 'eslint-plugin-vue'
import skipFormatting from '@vue/eslint-config-prettier/skip-formatting'

// https://eslint.vuejs.org/ + https://github.com/vuejs/eslint-config-typescript
export default defineConfigWithVueTs(
  {
    name: 'app/files-to-lint',
    files: ['**/*.{ts,mts,tsx,vue}'],
  },

  // `prototypes/` holds static HTML/JS design references — not part of the
  // app build or type-checked surface (see web/CLAUDE.md). Keep them out of
  // the lint gate so design exploration never blocks CI.
  globalIgnores([
    '**/dist/**',
    '**/dist-ssr/**',
    '**/coverage/**',
    '**/node_modules/**',
    'prototypes/**',
  ]),

  pluginVue.configs['flat/essential'],
  vueTsConfigs.recommended,

  // Disables stylistic rules that conflict with Prettier — Prettier owns formatting.
  skipFormatting,
)
