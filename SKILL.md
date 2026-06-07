---
name: utools-plugin-development
description: Build, migrate, debug, package, and review uTools plugin projects using Vite, Vue, React, Angular, Svelte, Solid, TypeScript, the official uTools developer APIs, and @ver5/vite-plugin-utools. Use when tasks mention uTools plugins, plugin.json, preload/preload.ts, window.utools, uTools Developer Tools, UPX/UPXS packaging, browser mock, @ver5/vite-plugin-utools, dynamic commands, ubrowser, registerTool/MCP/AI Agent tools, local db/dbStorage, Sharp/FFmpeg integration, native module rebuilds, or converting Web apps, browser extensions, Electron apps, or Tauri apps into uTools plugin applications.
---

# uTools Plugin Development

Use this skill to turn requirements, Web apps, Electron apps, or Tauri apps into maintainable uTools plugins, and to debug real uTools packaging/runtime issues without guessing.

## First moves

1. Inspect the project before changing code: `package.json`, `vite.config.*`, `tsconfig.json`, `plugin.json`, `preload.*`, `dist/`, and existing README/docs.
2. If docs or package behavior may have changed, refresh the official uTools docs and npm registry before relying on this skill's snapshot.
3. Run the audit helper when a project exists:
   ```bash
   python3 ~/.agents/skills/utools-plugin-development/scripts/audit_utools_project.py /path/to/project
   ```
4. Decide the lane:
   - Web/Electron/Tauri migration: read `references/app-migration-playbook.md` first, then load the lane-specific references it names.
   - New plugin or broad architecture: read `references/engineering-patterns.md` and `references/ver5-vite-plugin-utools.md`.
   - Manifest behavior: read `references/official-utools-docs.md` and `references/plugin-json-schema.md`.
   - uTools API usage, preload bridge design, or browser mocks: read `references/utools-api-reference.md`.
   - Framework quirks: read `references/framework-quirks.md`.
   - Electron native module issue: read `references/native-module-recompile.md`.
   - Tauri command mapping: read `references/tauri-command-mapping.md`.
   - Build/mock/UPX issue: read `references/ver5-vite-plugin-utools.md` first, then inspect runtime output.

## Architecture rules

- Keep uTools runtime files explicit: prefer `utools/plugin.json`, `utools/preload.ts`, and `utools/logo.png` as source; treat `dist/` as generated output.
- With `@ver5/vite-plugin-utools`, require development preload source to be `utools/preload.ts`; let the plugin generate final `dist/preload.js`.
- Keep browser UI and native capabilities separated. Put UI in Vite `src/`; put filesystem, Electron, OS, db, and AI tool registration in preload.
- For Web apps, fix hash routing, relative assets, `file://` local fetches, browser storage, and early `window.utools` reads before chasing framework-specific bugs.
- For Electron apps, there is no independent main process in uTools: fold `ipcMain` handlers and main-process services into preload exports or uTools APIs.
- For Tauri apps, frontend code can often stay; reimplement Rust commands as narrow Node/uTools preload services and recreate Tauri allowlist/path safety.
- Route by `feature.code` from `utools.onPluginEnter`; do not infer behavior from command labels.
- Design for the embedded main window first. Official default height is `544`; avoid hardcoded 800px canvases, but keep layouts dense and responsive for small uTools windows and detached wider windows.
- For persistence, prefer `utools.db.promises`/`dbStorage` behind a narrow repository layer. Split large mutable state into multiple docs to reduce sync conflicts.
- Do not package the repository root. Build the Vite app, then point uTools Developer Tools or UPX packaging at the generated output containing `plugin.json`, `main`, `logo`, and `preload.js`.

## @ver5/vite-plugin-utools baseline

Use the plugin when the project is Vite-based and should support browser-side development:

```ts
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import utools from '@ver5/vite-plugin-utools'

export default defineConfig({
  plugins: [
    vue(),
    utools({
      configFile: './utools/plugin.json',
      name: 'preload',
    }),
  ],
})
```

Minimum TypeScript setup:

```json
{
  "compilerOptions": {
    "types": ["@ver5/vite-plugin-utools/utools"]
  },
  "include": ["src", "utools/**/*.ts"]
}
```

Important behavior:

- `configFile` is required and paths inside `plugin.json` resolve relative to that file.
- For the default `configFile: './utools/plugin.json'` source manifest, `preload` must be `preload.ts`. Do not develop against `utools/preload.js`; final runtime output should still be generated as `dist/preload.js`.
- Named exports from `preload.ts` mount to `window[name]`; default export object mounts directly on `window`.
- Dev mode generates browser mocks from `preload.ts`; customize user overrides instead of hacking app-layer fallbacks.
- `upx: true` or an `upx` object can emit `.upx`; encrypted `.upxs` remains a Developer Tools/server-side flow.
- Keep `minify` off for preload unless the target review policy explicitly allows it; official docs require readable preload code for submission.
- Ensure generated `preload.js` is not inside a `type: module` package scope. If the nearest parent `package.json` has `"type": "module"`, Node/Electron treats `.js` as ESM and CommonJS preload code can fail; put a nearer `{ "type": "commonjs" }` package file in the packaged output or isolate the preload output.

## Implementation checklist

- Manifest: unique `features[].code`; concise unique command names; match commands use valid `regex`/`over`/`img`/`files`/`window` shapes; `tools` keys use lower snake_case and have object `inputSchema`.
- Preload: expose the smallest stable API surface on `window`; add TSDoc/JSDoc for exported functions; avoid leaking raw Node primitives to UI when a narrow operation is enough.
- Migration: map old platform APIs before editing UI. For Electron map `ipcMain`/`ipcRenderer`, dialogs, shell, windows, storage, and native modules; for Tauri map every `invoke()` / `#[tauri::command]` pair.
- uTools API: choose host APIs by capability, not by vague similarity. Check `references/utools-api-reference.md` before using lifecycle, window, clipboard/input, db, ubrowser, AI, Sharp, or FFmpeg APIs.
- UI: use Vue Composition API or React Hooks; adapt to uTools light/dark theme via `utools.isDarkColors()` plus browser fallback; keep empty/error/loading states usable in the small host window.
- Dev: make browser mocks return contract-correct data, not `undefined`; verify both browser dev and uTools Developer Tools output `plugin.json`.
- Package: inspect `dist/plugin.json`, `dist/preload.js`, assets, copied dependencies, and optional `.upx`; for UPX problems, list the archive or output files instead of assuming build success.
- AI tools: define `plugin.json.tools` and register matching tools during preload/page initialization, not inside `onPluginEnter`.

## Validation

Use a narrow evidence chain before declaring done:

1. Static: `python3 ~/.agents/skills/utools-plugin-development/scripts/audit_utools_project.py . --strict`.
2. Type/build: run the repo's real package-manager commands (`pnpm typecheck`, `pnpm test`, `pnpm build`, etc.).
3. Runtime: inspect generated `dist/plugin.json`; if relevant, open via uTools Developer Tools or check the `.upx` archive contents.
4. Regression: verify the one decisive flow from `feature.code`/matched payload -> preload/API call -> UI/state/output.

## Reference map

- `references/official-utools-docs.md`: official manifest, preload, API, AI tools, packaging/publish notes.
- `references/app-migration-playbook.md`: first-stop playbook for Web, Electron, and Tauri conversions.
- `references/framework-quirks.md`: Vue/React/Angular/Svelte/Solid quirks under the uTools host.
- `references/plugin-json-schema.md`: extended manifest checklist and trigger schema details.
- `references/utools-api-reference.md`: `window.utools` capability map, method groups, API selection rules, and mock contracts.
- `references/utools-api-cheatsheet.md`: fast API lookup and type-oriented usage snippets.
- `references/ver5-vite-plugin-utools.md`: npm package behavior, Vite config, preload export/mocking, UPX, troubleshooting.
- `references/engineering-patterns.md`: full engineering conversion guide for Web/Electron/Tauri/native-module scenarios.
- `references/native-module-recompile.md`: Electron/uTools ABI rebuild workflow for native `.node` modules.
- `references/tauri-command-mapping.md`: Tauri Rust command and `@tauri-apps/api` to uTools/preload mapping.
