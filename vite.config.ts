import { defineConfig } from 'vite'
import { devtools } from '@tanstack/devtools-vite'

import { tanstackStart } from '@tanstack/react-start/plugin/vite'

import viteReact from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { nitro } from 'nitro/vite'

const config = defineConfig({
  resolve: { tsconfigPaths: true },
  server: {
    // the roundtrip prototype's custom_path.py appends to these while it prices (raw CLI responses, valuation caches);
    // each write would otherwise make Vite reload the page
    watch: { ignored: ['**/scenarios/iren/data/raw/**', '**/scenarios/iren/data/*-exit-values-*.json', '**/scenarios/iren/data/*-quotes-*.json', '**/__pycache__/**'] },
  },
  plugins: [
    devtools(),
    nitro({ rollupConfig: { external: [/^@sentry\//] } }),
    tailwindcss(),
    tanstackStart(),
    viteReact(),
  ],
})

export default config
