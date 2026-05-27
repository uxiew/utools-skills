# Official uTools developer docs snapshot

Source snapshot: 2026-05-10, refreshed from `https://www.u-tools.cn/docs/developer/` and Context7 `/websites/u-tools_cn_developer`.

## Source links

- Entry: https://www.u-tools.cn/docs/developer/basic/getting-started.html
- First plugin: https://www.u-tools.cn/docs/developer/basic/first-plugin.html
- Debugging: https://www.u-tools.cn/docs/developer/basic/debug-plugin.html
- Offline package: https://www.u-tools.cn/docs/developer/basic/offline-plugin.html
- Publish: https://www.u-tools.cn/docs/developer/basic/publish-plugin.html
- File structure: https://www.u-tools.cn/docs/developer/information/file-structure.html
- Manifest: https://www.u-tools.cn/docs/developer/information/plugin-json.html
- Preload: https://www.u-tools.cn/docs/developer/information/preload.html
- API root: https://www.u-tools.cn/docs/developer/docs.html

## Development flow

1. Create a project in uTools Developer Tools, then point it at a folder containing `plugin.json`.
2. Keep source compilation separate from final plugin output. uTools recognizes ordinary HTML/CSS/JavaScript assets; framework source must be built first.
3. During development, enable reload-on-enter / kill-on-background behavior in Developer Tools when preload code changes, because preload does not hot-reload like browser UI.
4. Debug with the plugin window's Developer Tools; for Vite/Webpack, use a dev server during UI iteration and the generated output `plugin.json` for uTools integration.
5. Offline packages are for testing/internal sharing; market publishing has its own metadata, review, screenshots, manual, and version flow.

## `plugin.json` essentials

Core fields:

- `main`: relative path to an `.html` entry. Required for UI plugins.
- `logo`: relative path to the plugin logo. Required.
- `preload`: relative path to a `.js` preload script. Optional for simple UI plugins; required when using native APIs or AI tools.
- `pluginSetting.single`: boolean, default `true`.
- `pluginSetting.height`: number, default `544`; can be changed at runtime with `utools.setExpendHeight`.
- `features`: array of user-facing capabilities. Required for UI-triggered plugins; each feature needs a unique `code` and one or more `cmds`.
- `tools`: object of AI Agent tools. For tool-only plugins, the minimal mode can omit `main` and `features`, but still needs `logo`, `preload`, and `tools`.

Feature fields:

- `code`: stable unique feature id; use it as the runtime route key.
- `explain`: optional description.
- `icon`: optional relative image path.
- `mainPush`: enable search-box push behavior; pair with `utools.onMainPush`.
- `mainHide`: hide the main search panel when a command triggers a direct action.
- `cmds`: string commands or object match commands.

Match command object types:

- `regex`: match text by regex string; avoid catch-all expressions because uTools ignores arbitrary matches. Escape backslashes for JSON.
- `over`: match arbitrary text with optional `exclude`, `minLength`, `maxLength`.
- `img`: match copied/pasted images.
- `files`: match files/directories; supports `fileType`, `extensions`, regex `match`, and length bounds.
- `window`: match the active system window by app/title/class.

AI tool manifest rules:

- `tools` keys must be lowercase snake_case and must match runtime `utools.registerTool(name, handler)` exactly.
- Each tool needs a clear `description` and object `inputSchema`; for no-arg tools use an empty object schema.
- `outputSchema` is optional but useful for predictable AI clients.

## Preload rules

- Preload runs before the page, outside normal browser sandbox, and can call Node.js and Electron renderer APIs.
- Official submission guidance requires preload and bundled third-party modules to remain readable: no minification, obfuscation, or opaque bundling for reviewed code.
- Official runtime preload is CommonJS and uses `require`; Node version is documented as 16.x.
- If `preload.js` is under a nearest parent `package.json` with `"type": "module"`, Node/Electron treats that `.js` file as an ES module. This conflicts with CommonJS-style preload code and can trigger errors such as “preload.js is treated as an ES module file...”. Fix the packaged runtime scope by adding a nearer `package.json` with `{ "type": "commonjs" }`, removing the ESM package scope from the plugin output, or otherwise isolating final preload code from the project-root ESM scope.
- Put preload beside `plugin.json` or under that folder so it is included in packaging.
- In Vite projects that use `@ver5/vite-plugin-utools`, keep official runtime requirements separate from source authoring: author `utools/preload.ts` and let the plugin emit final CommonJS-compatible `preload.js` into `dist`.
- Expose a narrow API on `window`, e.g. `window.services = { readConfig, saveConfig }`, rather than giving UI direct access to `fs`, `child_process`, or large mutable global state.
- Third-party Node dependencies should be present beside preload in the final package when not bundled; native modules need extra care and runtime verification.

## API categories to check before implementation

- Events: `onPluginEnter`, `onPluginOut`, `onMainPush`, `onPluginDetach`, `onDbPull`.
- Window: hide/show main window, `setExpendHeight`, sub input APIs, `outPlugin`, `redirect`, open/save dialogs, find-in-page, drag files, `createBrowserWindow`, parent/child communication, window type, dark color detection.
- Clipboard/input: copy text/file/image; paste or type text/file/image into the previous active app.
- System/screen/user: path/platform info, display/cursor data, user information, app-specific behaviors.
- Storage: `utools.db` and `utools.db.promises` for documents/attachments/sync; `dbStorage` for local key-value; `dbCryptoStorage` for encrypted key-value.
- Dynamic features: read/set plugin features, redirect hotkey settings, custom AI model settings.
- Automation: `simulateKeyboardTap` and `ubrowser` for visible programmable browser workflows.
- Integrations: payment, AI, Sharp, FFmpeg, server API.
- AI tools: `utools.registerTool(name, handler)` with optional `ctx.sendProgress` for long tasks.

## AI tool runtime rules

- Register tools during preload/page initialization or at the same top-level phase as event registration.
- Do not register tools inside `onPluginEnter`; AI clients may invoke tools without entering a UI feature first.
- Keep each tool single-purpose, parameter schema strict, and return values structured objects.
- For tasks that may take more than a few seconds, use `ctx.sendProgress?.({ progress, total, message })` when available.
- Throw explicit errors so AI clients can surface failures.

## Packaging and publishing checks

- Final package folder must include only runtime assets: built HTML/CSS/JS, `plugin.json`, logo/assets, preload, and required readable Node modules.
- Do not submit the whole source repository as the plugin package.
- Offline package version and market publish version are separate flows; do not assume one updates the other.
- Before publish, verify code readability constraints, manual/screenshots, plugin metadata, and generated output paths.
