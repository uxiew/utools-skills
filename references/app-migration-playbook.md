# App migration playbook: Web / Electron / Tauri → uTools

Use this first when the user asks to convert an existing app into a uTools plugin. Then load the detailed companion references only for the lane you need:

- Web frameworks: `framework-quirks.md` and `engineering-patterns.md` §6.
- Electron: `engineering-patterns.md` §7 and `native-module-recompile.md` when native `.node` modules exist.
- Tauri: `tauri-command-mapping.md` plus `engineering-patterns.md` §8.
- Manifest design: `plugin-json-schema.md` and `official-utools-docs.md`.
- uTools host APIs: `utools-api-reference.md` and `utools-api-cheatsheet.md`.

## 0. Triage before changing code

Inspect these files first:

```text
package.json
vite.config.* / webpack.config.* / angular.json / svelte.config.*
src-tauri/tauri.conf.* / src-tauri/src/**/*.rs
main.* / electron/main.* / preload.* / src/main.*
plugin.json / utools/plugin.json / dist/plugin.json
```

Classify the source app:

| Source | Main migration target | High-risk items |
| --- | --- | --- |
| Vue / React / Angular / Svelte / Solid SPA | Vite UI + `utools/preload.ts` bridge | HTML5 history, absolute asset paths, browser storage, local fetch, early `window.utools` reads |
| Electron app | Renderer UI reused, main-process logic folded into preload/services | `ipcMain`, `BrowserWindow`, `Menu`, `Tray`, `globalShortcut`, native modules |
| Tauri app | Frontend mostly reused, Rust commands reimplemented as Node preload services | `invoke`, allowlist/path security, Rust-only crates, sidecars, file/network permissions |

Do not package the original repository root. The final uTools runtime folder must contain built UI assets, `plugin.json`, logo/assets, generated `preload.js`, and any readable runtime dependencies.

## 1. Universal conversion flow

1. Create/normalize `utools/` source runtime:
   ```text
   utools/plugin.json
   utools/preload.ts
   utools/logo.png
   ```
2. Add `@ver5/vite-plugin-utools` and configure it with `configFile: './utools/plugin.json'`.
3. Enforce source preload rule: `utools/plugin.json` must use `"preload": "preload.ts"`; final `dist/plugin.json` should point to `preload.js`.
4. Move native/host work behind a narrow preload bridge. UI calls `window.preload.*`; preload calls `window.utools.*`, Node, and Electron renderer APIs.
5. Make routing and assets uTools-safe:
   - Use hash routing, not browser history routing.
   - Use relative asset base, not root-absolute paths.
   - Avoid `fetch('/local.json')` under `file://`; import static JSON or read files in preload.
6. Replace storage:
   - UI-only temporary state can stay in framework stores.
   - Persistent plugin config should use `utools.db.promises`, `dbStorage`, `dbCryptoStorage`, or explicit file-backed repositories in preload.
7. Mock browser development with contract-correct values. Never return `undefined` just to silence TypeScript.
8. Validate in four layers: static audit → type/build → generated `dist/plugin.json`/file list → uTools Developer Tools/UPX runtime.

## 2. Web framework lane

### Shared rules

- Use the framework's hash router:
  - Vue: `createWebHashHistory()`.
  - React: `HashRouter` or equivalent.
  - Angular: `withHashLocation()` / `HashLocationStrategy`.
  - Svelte/Solid routers: hash mode or `#/path` URLs.
- Read `window.utools` inside lifecycle/effect hooks, not at module top-level.
- Centralize host calls in a bridge/composable/service; do not scatter raw `window.utools` calls through UI components.
- Use CSS variables and `utools.isDarkColors()` with `prefers-color-scheme` fallback for light/dark theme.
- Prefer compact 544px-height-friendly layouts; support wider detached windows without hardcoding a fixed 800px canvas.

### Vue

- Keep `<script setup lang="ts">` and Composition API.
- Put `onPluginEnter` effects into a composable such as `useUtoolsEntry()`.
- Use `onMounted()` for host API reads.
- Route with `createWebHashHistory()`.

### React

- Use function components and hooks.
- Route with `HashRouter`.
- Guard React StrictMode double-invocation: lifecycle registration should be idempotent and cleanup-aware.
- Keep preload calls in `useEffect`, event handlers, or service modules, not module initialization.

### Angular

- Prefer modern standalone bootstrap with hash location.
- Zone.js can obscure callback timing; when bridging uTools events, explicitly re-enter Angular zone for UI state updates or keep host calls outside zone when appropriate.
- Avoid relying on Angular dev server path behavior; verify built output under `file://` / uTools.

### Svelte / Solid

- Use lifecycle hooks (`onMount`, `createEffect`) for host reads.
- Avoid SSR-only assumptions; uTools plugin UI is a client-only runtime.
- These frameworks are good for small plugins because bundle size and runtime overhead are low.

## 3. Electron lane

uTools plugin runtime has no independent Electron main process. Migrate by folding main-process logic into preload services or uTools host APIs.

Mapping:

| Electron source | uTools migration |
| --- | --- |
| `ipcMain.handle('x', fn)` | `export async function x(...)` in `utools/preload.ts` |
| renderer `ipcRenderer.invoke('x')` | `window.preload.x(...)` |
| `BrowserWindow` main window | uTools plugin main window (`main`) |
| additional windows | `utools.createBrowserWindow()` |
| `dialog.showOpenDialog` | `utools.showOpenDialog()` |
| `dialog.showSaveDialog` | `utools.showSaveDialog()` |
| `shell.openExternal/openPath` | `utools.shellOpenExternal`, `shellOpenPath` |
| `clipboard` | `utools.copyText/copyFile/copyImage` or Electron renderer clipboard from preload |
| `app.getPath` | `utools.getPath(name)` |
| `Menu`, `Tray`, custom app lifecycle | Usually remove, replace with uTools commands/features |
| `globalShortcut` | Usually not portable; guide users to uTools hotkeys or dynamic features |

Native modules from Electron projects need ABI review. Prefer pure JS/WASM replacements; otherwise read `native-module-recompile.md` and rebuild against the uTools/Electron ABI, not standard Node.

## 4. Tauri lane

Tauri frontend code often survives, but Rust commands must be mapped to Node/uTools capabilities.

Workflow:

1. List all `#[tauri::command]` functions and frontend `invoke('cmd')` calls.
2. Group commands by domain: fs/path/shell/dialog/clipboard/notification/http/window/event/store/system.
3. For each command, implement an equivalent `utools/preload.ts` export using Node/uTools APIs.
4. Replace frontend imports from `@tauri-apps/api` with a small adapter, or intercept `window.__TAURI_IPC__` only when it reduces churn and remains explicit/testable.
5. Rebuild Tauri allowlist semantics: validate paths, URLs, command args, and output locations in preload.
6. Convert Tauri store/state to `utools.dbStorage`, `utools.db.promises`, or file-backed config.

Never blindly port Rust permissions into arbitrary Node `fs`/`child_process` access. Recreate the narrow allowlist in TypeScript.

## 5. Data and persistence mapping

| Source pattern | uTools target |
| --- | --- |
| `localStorage` for persisted config | `dbStorage` or file-backed repository in preload |
| IndexedDB / app database | `utools.db.promises` docs or explicit local DB module in preload |
| Tauri store plugin | `dbStorage` / `dbCryptoStorage` / file repository |
| Electron userData JSON | `utools.getPath('userData'?)` if available, otherwise `getPath('home')` + namespaced directory |
| Secrets/tokens | `dbCryptoStorage` where appropriate; avoid unrelated credential storage |

Use stable prefixes such as `settings/`, `item/`, `cache/` and keep mutable data split across documents to reduce sync conflicts.

## 6. Packaging and regression evidence

Before declaring migration complete, capture:

- `python3 ~/.agents/skills/utools-plugin-development/scripts/audit_utools_project.py . --strict` result.
- Framework build/typecheck/test output.
- Generated `dist/plugin.json` and `dist/preload.js` existence.
- If project root is `type: module`, confirm generated runtime has a nearer `package.json` with `{ "type": "commonjs" }` or otherwise avoids ESM treatment for `preload.js`.
- One end-to-end route: command/match payload → `onPluginEnter` → preload service → UI/state/output.
- For Electron/Tauri migrations, one representative former IPC/command flow fully replayed.
