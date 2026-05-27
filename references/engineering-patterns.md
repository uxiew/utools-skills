# Engineering patterns for maintainable uTools plugins

Use these patterns when designing, migrating, refactoring, or reviewing plugin code.

## Requirement-to-plugin mapping

Map each user-facing capability to one of these entry modes:

- Search command: string `cmds`, normal UI entry.
- Text/file/image/window match: object `cmds`, payload enters through `onPluginEnter`.
- Direct background action: `mainHide: true` plus explicit completion feedback.
- Search push: `mainPush: true` plus `onMainPush` and `onSelect`.
- AI Agent tool: `plugin.json.tools` plus top-level `utools.registerTool`.

Prefer a small number of stable `feature.code` values and route payloads explicitly.

## Migration from web app or browser extension

1. Identify browser-only dependencies: extension APIs, `chrome.*`, web storage, IndexedDB, clipboard, downloads, native messaging.
2. Build an adapter layer in preload or `src/services/`, rather than changing every UI component.
3. Move OS/native operations to preload: files, shell, clipboard, Electron dialogs, uTools db, ubrowser, Sharp/FFmpeg.
4. Keep the UI framework idiomatic: Vue Composition API with `<script lang="ts" setup>` or React function components with Hooks.
5. Add browser mocks only for plugin APIs; never mutate unrelated user project code to make local dev pass.
6. Verify in browser dev first, then uTools Developer Tools, then production `dist`/UPX.

## Suggested code boundaries

```txt
src/
├─ app/ or pages/           # UI and routes
├─ components/              # pure UI
├─ services/                # frontend-facing service clients
├─ stores/                  # Pinia/Zustand/etc.; no raw uTools calls when possible
└─ types/                   # window/preload declarations
utools/
├─ plugin.json
├─ preload.ts               # required source preload for @ver5/vite-plugin-utools
├─ services/                # Node/Electron/uTools implementations
├─ repositories/            # db/dbStorage/dbCryptoStorage wrappers
└─ preload.mock.ts          # browser-only overrides generated/customized by plugin
```

Keep files under 500-800 lines; split by feature or responsibility before adding helper sprawl.

## Preload bridge pattern

Use narrow exported functions:

```ts
/** Read all saved snippets from local uTools storage. */
export async function listSnippets(): Promise<Snippet[]> {
  return window.utools.db.promises.allDocs('snippet/') as Promise<Snippet[]>
}

/** Save a single snippet document. */
export async function saveSnippet(snippet: Snippet): Promise<void> {
  await window.utools.db.promises.put({ _id: `snippet/${snippet.id}`, ...snippet })
}
```

Avoid exposing generic `readFile(path)` or `exec(command)` unless the product explicitly needs it. If a generic primitive is required, validate inputs and return structured errors.

## Storage pattern

- Use document prefixes such as `settings/`, `item/`, `cache/` for `utools.db`.
- Keep each document below official limits and split mutable records to reduce sync conflicts.
- Use `dbStorage` for simple non-sensitive key-value state.
- Use `dbCryptoStorage` for local encrypted values; still avoid storing unrelated credentials or secrets.
- Wrap storage in repositories so UI tests and browser mocks can substitute data.

## UI pattern for the uTools host

- Default height is 544; keep top-level layout useful around 800px wide without hardcoding that width.
- Provide compact empty/error/loading states; avoid full-page whitespace.
- Use `utools.setSubInput` for host search/filter flows when it improves keyboard ergonomics.
- React to uTools light/dark theme using `utools.isDarkColors()` at runtime and `prefers-color-scheme` as browser fallback. Put the result on `document.documentElement.dataset.theme` or a root class, then drive colors with CSS variables.
- Detached windows may be larger; make grids/forms responsive instead of creating a second design system.

Minimal theme adapter:

```ts
export function applyHostTheme(): void {
  const isDark = window.utools?.isDarkColors?.() ?? window.matchMedia('(prefers-color-scheme: dark)').matches
  document.documentElement.dataset.theme = isDark ? 'dark' : 'light'
}

applyHostTheme()
window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', applyHostTheme)
```

## Build evidence pattern

For every non-trivial change, collect evidence in this order:

1. Source manifest and preload route review.
2. Browser dev with generated mock data.
3. Typecheck/test/build output.
4. Generated `dist/plugin.json` and file list.
5. uTools Developer Tools runtime check or UPX archive/file check.

If evidence conflicts, trust live generated output over source assumptions.

## Common failure modes

- Developer Tools points at source `plugin.json` while Vite plugin generated a different output manifest.
- `preload.ts` paths are treated as project-root relative instead of manifest-relative.
- `utools/plugin.json` points to `preload.js` in a `@ver5/vite-plugin-utools` source project. Correction: source preload must be `utools/preload.ts`; only generated `dist/plugin.json` should point at `preload.js`.
- Generated `preload.js` sits under a root `package.json` with `"type": "module"`, so Node/Electron treats `.js` preload as ESM instead of CommonJS. Add a nearer packaged `package.json` with `"type": "commonjs"` or isolate the output scope.
- Mock files are ignored by `.gitignore`, causing new machines to fail browser dev.
- Business UI adds `undefined` fallbacks instead of fixing mock/preload contracts.
- UPX packaging runs before preload build/copy completes and captures incomplete `dist`.
- Large dependency is bundled into unreadable preload or omitted entirely when externalized.
- AI tool exists in manifest but is never registered, or registration happens only inside `onPluginEnter`.
