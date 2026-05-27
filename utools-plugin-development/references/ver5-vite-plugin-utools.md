# @ver5/vite-plugin-utools reference

Source snapshot: 2026-05-10; npm registry latest rechecked 2026-05-27: `@ver5/vite-plugin-utools@0.4.1` published 2026-04-16. Source links: https://www.npmjs.com/package/@ver5/vite-plugin-utools, https://registry.npmjs.org/%40ver5%2Fvite-plugin-utools, https://github.com/uxiew/vite-plugin-utools

## What it solves

- Connects Vite build output, `plugin.json`, logo, preload, and optional UPX output.
- Lets frontend UI run in a browser during dev by injecting `window.utools` and preload mocks.
- Builds preload separately from the page and writes generated `dist/plugin.json` for uTools Developer Tools.
- Provides uTools type declarations and a `plugin.json` schema export.

## Recommended source layout

```txt
.
├─ src/                 # Vue/React/Svelte/etc. UI
├─ utools/
│  ├─ plugin.json       # source manifest
│  ├─ preload.ts        # source preload entry
│  └─ logo.png
├─ vite.config.ts
└─ tsconfig.json
```

Use `npx utools` to create the default `utools/` scaffold, or `npx utools --dir plugin-runtime` for another folder name.

Hard rule for this skill: when using the default `utools/` source directory with `@ver5/vite-plugin-utools`, develop preload as `utools/preload.ts` and set source `utools/plugin.json` to `"preload": "preload.ts"`. Do not use `utools/preload.js` as the source file. The production build remains responsible for generating final `dist/preload.js`.

## Vite config

```ts
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import utools from '@ver5/vite-plugin-utools'

export default defineConfig({
  plugins: [
    react(),
    utools({
      configFile: './utools/plugin.json',
      name: 'preload',
      mock: { enabled: true, showBadge: true },
    }),
  ],
})
```

Key options:

- `configFile` (required): path to source `plugin.json`.
- For `configFile: './utools/plugin.json'`, enforce source `preload.ts`. This keeps preload typed, mock-analyzable, and aligned with the plugin's named-export mounting behavior.
- `watch` (default `true`): rebuild preload and refresh generated output in dev.
- `name` (default `preload`): named exports mount to `window[name]`.
- `minify` (default `false`): keep false for official readability unless explicitly needed.
- `external`: dependencies excluded from preload bundling; `electron` and `original-fs` are always external.
- `define`: define values for preload sub-build.
- `viteConfig`: merge additional Vite config into preload sub-build.
- `onGenerate`: last-mile string patch hook before writing generated files.
- `mock.enabled` / `mock.showBadge`: control browser mock injection.
- `vconsole`: `true` or custom script URL to inject vConsole and forward preload logs.
- `upx`: `true` or `{ outDir, outName }`; default output name is `[pluginName]_[version].upx`.

## Type/schema setup

`tsconfig.json`:

```json
{
  "compilerOptions": {
    "types": ["@ver5/vite-plugin-utools/utools"]
  },
  "include": ["src", "utools/**/*.ts"]
}
```

`utools/plugin.json` schema path when `plugin.json` lives under `utools/`:

```json
{
  "$schema": "../node_modules/@ver5/vite-plugin-utools/utools.schema.json"
}
```

## Preload export contract

For `name: 'preload'`:

```ts
export const readText = async (path: string) => '...'

export default {
  appVersion: '1.0.0',
}
```

Runtime shape:

```ts
window.preload.readText('/tmp/a.txt')
window.appVersion
```

If `name: 'bridge'`, named exports mount under `window.bridge`.

Guidance:

- Prefer named exports for page-facing services.
- Avoid default export for large APIs because it pollutes `window` directly.
- Add TSDoc to exported preload functions; this helps generated mocks and future maintainers.

## Browser mock behavior

Dev mode injects a `window.utools` mock and generates preload mock files near `preload.ts`:

- `_mock.auto.ts`: generated from current preload exports.
- `preload.mock.ts`: user override file; first creation only, not overwritten.

Fix mock issues at the plugin/mock layer, not by sprinkling `undefined` checks through business UI. Custom mock returns should match the real API contract closely enough for normal UI flows.

Typical override:

```ts
import { autoMock } from './_mock.auto'

autoMock.preload.loadItems = async () => [{ id: 'demo', title: 'Demo' }]

export default autoMock
```

## Build and UPX flow

- `pnpm vite`: starts the UI dev server, builds preload, and writes generated `plugin.json` pointing at the dev server. In Developer Tools, point to the generated output `plugin.json`, not necessarily the source one.
- `pnpm vite build`: builds UI assets, builds `preload.js`, writes final `dist/plugin.json`, and optionally emits `.upx` when `upx` is configured.
- Inspect `dist/` after build: missing assets or preload usually means path resolution or async build ordering is wrong.
- Inspect the module scope of generated `dist/preload.js`: if the closest parent `package.json` has `"type": "module"`, `.js` preload is treated as ESM. uTools preload code and many dependencies expect CommonJS, so place a nearer `package.json` with `{ "type": "commonjs" }` in `dist`/runtime output or keep the plugin output outside the project-root ESM package scope.
- `.upx` is plain offline package output. Encrypted `.upxs` is outside the plugin package's current documented support.

## Troubleshooting map

- `configFile` missing: pass `utools({ configFile: './utools/plugin.json' })`.
- `preload`/`logo` not found: paths in manifest are relative to the `plugin.json` directory.
- Browser works but uTools fails: compare generated `dist/plugin.json` with actual files, then inspect preload Node/Electron dependencies.
- `preload.js is treated as an ES module file`: nearest package scope has `"type": "module"`; add a packaged-output `package.json` with `"type": "commonjs"` or change the output scope.
- `window.utools` or `window.preload` undefined in browser: confirm mock injection runs before app entry and that generated mock files are not ignored/missing.
- UPX white screen/no logs: enable `vconsole`, rebuild, and verify archive/output file list.
- Native modules fail from preload: consider `external`, copying dependencies beside preload, or replacing with pure JS if possible.
