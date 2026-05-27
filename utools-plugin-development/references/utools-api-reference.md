# uTools API capability reference

Snapshot: 2026-05-10. Sources: official uTools developer API pages under `https://www.u-tools.cn/docs/developer/utools-api/` and Context7 `/websites/u-tools_cn_developer`.

Use this file when implementing `preload.ts`, routing `onPluginEnter`, designing browser mocks, or choosing the right `window.utools` API. It is a capability map, not a full replacement for the official docs.

## Mental model

- `window.utools` is the host bridge. It gives plugin code access to uTools lifecycle events, host window control, clipboard/input, OS helpers, local db, screen/user info, automation, AI, and integrations.
- `preload` is the safest place to centralize native/host calls. UI components should call a narrow bridge such as `window.preload.saveConfig(...)`, not raw `window.utools.db.put(...)` everywhere.
- `plugin.json.features[].code` is the stable route key. Command labels are user-facing text and should not drive business logic.
- Browser dev mocks must emulate API shape and return contract-correct values. Avoid blanket `undefined`; use realistic strings, arrays, booleans, db docs, file paths, and payload objects.
- Some API names preserve official spelling: `setExpendHeight`, `getCopyedFiles`, `reirect` in older type text. Do not silently rename host APIs.

## Choose the API by job

| Job | Prefer | Notes |
| --- | --- | --- |
| React to plugin entry, matched text/file/image/window | `onPluginEnter` | Route by `code`; branch by `type`; validate `payload` shape. |
| Search-box suggestions from selected content | `onMainPush` + `mainPush` | Return concise choices; `onSelect` may enter UI or run silently. |
| Resize/use host input | `setExpendHeight`, `setSubInput`, `removeSubInput` | Good for compact search/filter plugins. |
| Close/hide after direct action | `hideMainWindow`, `outPlugin(true?)` | Use direct feedback before hiding when action may fail. |
| Copy data for user | `copyText`, `copyFile`, `copyImage` | Changes clipboard only. |
| Paste/type into previous app | `hideMainWindowPasteText/File/Image`, `hideMainWindowTypeString` | Requires previous focused app context; mock with visible logs/toasts. |
| Open files/URLs/finder, notifications | system shell APIs | Keep URL/path validation in preload. |
| Store app data | `db.promises`, `dbStorage`, `dbCryptoStorage` | Use repositories and doc prefixes; split mutable records. |
| Screen/window geometry, capture, color pick | screen APIs | Use for screenshot/capture/color tools and detached windows. |
| Automate websites visibly | `ubrowser` | Chain actions then `run()`; prefer over invisible scraping when user interaction matters. |
| Expose plugin as AI/MCP-like tool | `plugin.json.tools` + `registerTool` | Register at initialization, never only inside `onPluginEnter`. |
| Call uTools AI model | `utools.ai`, `allAiModels` | Provide abort/progress UX for long calls. |
| Image/video processing | `sharp`, `runFFmpeg` | Keep heavy work in preload/tool handlers; report progress. |

## Events and routing

Methods:

- `utools.onPluginEnter(callback)`
- `utools.onPluginOut(callback)`
- `utools.onMainPush(callback, onSelect)`
- `utools.onPluginDetach(callback)`
- `utools.onDbPull(callback)`

`onPluginEnter` receives a `PluginEnterAction` with:

- `code`: `plugin.json.features[].code`.
- `type`: one of text/img/file/regex/over/window depending on command match.
- `payload`: string, image/base64-like data, `MatchFile[]`, or `MatchWindow`.
- `from`: host entry source such as main/panel/hotkey/redirect spelling variant.
- `option`: currently important for `mainPush` paths.

Pattern:

```ts
utools.onPluginEnter((action) => {
  switch (action.code) {
    case 'open_file_tools':
      return window.preload.handleFiles(action.payload)
    case 'translate_text':
      return window.preload.translate(String(action.payload ?? ''))
    default:
      console.warn('Unknown feature code', action.code)
  }
})
```

Mock guidance: provide a helper that can emit representative `PluginEnterAction` fixtures for each feature code and match type.

## Host window and UX APIs

Methods:

- `hideMainWindow(isRestorePreWindow?)`, `showMainWindow()`
- `setExpendHeight(height)`: official name uses `Expend`; default manifest height is `544`.
- `setSubInput(onChange, placeholder?, isFocus?)`, `removeSubInput()`, `setSubInputValue(text)`, `subInputFocus()`, `subInputBlur()`, `subInputSelect()`
- `outPlugin(isKill?)`, `redirect(label, payload?)`
- `showOpenDialog(options)`, `showSaveDialog(options)`
- `findInPage(text, options?)`, `stopFindInPage(action)`
- `startDrag(filePath)`
- `createBrowserWindow(url, options, callback?)`, `sendToParent(channel, ...args)`, `getWindowType()`, `isDarkColors()`

Guidance:

- Use `pluginSetting.height` for initial height and `setExpendHeight` for runtime resizing.
- Use sub input for keyboard-first search/filter UX instead of duplicating a large input inside the UI.
- For detached windows, `createBrowserWindow` uses relative HTML/preload paths; verify generated files exist in `dist`.
- `showOpenDialog` / `showSaveDialog` return user-selected paths or empty/undefined on cancel; always handle cancel.
- `redirect` can target another plugin/command and pass payload only when the target command can match that payload.

Theme adaptation:

- Use `utools.isDarkColors()` as the host truth for whether uTools is currently in dark colors.
- In browser dev, fall back to `window.matchMedia('(prefers-color-scheme: dark)')`.
- Apply a root `data-theme` or class and drive all colors through CSS variables; do not hardcode only a dark palette.
- Include a mock switch for `isDarkColors()` so UI can be tested in both light and dark themes.

Example:

```ts
export function syncUtoolsTheme(): void {
  const fallbackDark = window.matchMedia('(prefers-color-scheme: dark)').matches
  const isDark = window.utools?.isDarkColors?.() ?? fallbackDark
  document.documentElement.dataset.theme = isDark ? 'dark' : 'light'
}
```

## Clipboard and input APIs

Copy methods:

- `copyText(text)`
- `copyFile(filePath)`
- `copyImage(image)`
- `getCopyedFiles()` (official spelling)

Input methods:

- `hideMainWindowPasteFile(filePath)`
- `hideMainWindowPasteImage(image)`
- `hideMainWindowPasteText(text)`
- `hideMainWindowTypeString(text)`

Guidance:

- Copy APIs affect clipboard; paste/type APIs act on the previously active system window after hiding uTools.
- Choose paste/type APIs for direct workflow automation; choose copy APIs when the user should decide where to paste.
- In mocks, return `true`/reasonable arrays and log the action; UI should not depend on OS side effects in browser dev.

## System APIs

Methods:

- Notifications and shell: `showNotification`, `shellOpenPath`, `shellTrashItem`, `shellShowItemInFolder`, `shellOpenExternal`, `shellBeep`
- Identity/version/path: `getNativeId`, `getAppName`, `getAppVersion`, `getPath(name)`, `getFileIcon(filePath)`
- Context detection: `readCurrentFolderPath`, `readCurrentBrowserUrl`, `isDev`, `isMacOS`, `isWindows`, `isLinux`

Guidance:

- Use `getPath('home' | 'downloads' | 'temp' | ...)` for user directories; avoid hardcoded OS paths.
- Validate URLs before `shellOpenExternal`; validate paths before destructive `shellTrashItem`.
- `getNativeId` is useful for local machine identity, but do not treat it as a cross-device account id.

## Screen APIs

Methods:

- `screenColorPick(callback)`, `screenCapture(callback)`
- `getPrimaryDisplay()`, `getAllDisplays()`
- `getCursorScreenPoint()`, `getDisplayNearestPoint(point)`, `getDisplayMatching(rect)`
- `screenToDipPoint(point)`, `dipToScreenPoint(point)`, `screenToDipRect(rect)`, `dipToScreenRect(rect)`
- `desktopCaptureSources(options)`

Guidance:

- Use display APIs before positioning detached windows near cursor or capture regions.
- Convert screen/DIP coordinates explicitly when mixing Electron window APIs and screen APIs.
- Mock displays with at least one primary display and realistic scale factor.

## User APIs

Methods:

- `getUser()`
- `fetchUserServerTemporaryToken()`

Guidance:

- Treat user info/token as optional and failure-prone; logged-out users exist.
- Do not persist temporary server tokens in project state.
- Browser mocks should include both logged-in and logged-out fixtures when auth gates affect UI.

## Local database and storage APIs

Document DB methods have sync and promise forms:

- `utools.db.put(doc)` / `utools.db.promises.put(doc)`
- `get(id)`, `remove(docOrId)`, `bulkDocs(docs)`, `allDocs(idStartsWith?)`
- attachments: `postAttachment(id, attachment, type)`, `getAttachment(id)`, `getAttachmentType(id)`
- sync: `replicateStateFromCloud()`

Key-value wrappers:

- `dbStorage.setItem/getItem/removeItem`
- `dbCryptoStorage.setItem/getItem/removeItem`

Guidance:

- Prefer `db.promises` in new TypeScript code.
- Official docs note a document content limit around 1 MB; split large/mutable data.
- Use `_id` prefixes: `settings/main`, `item/${id}`, `cache/${key}`.
- Cloud sync can create conflicts; design writes to minimize concurrent edits of one large doc.
- Use `dbCryptoStorage` for local encrypted plugin data, but still avoid storing unrelated credentials.

## Dynamic feature APIs

Methods:

- `getFeatures(codes?)`
- `setFeature(feature)`
- `removeFeature(code)`
- `redirectHotKeySetting(cmdLabel, autocopy?)`
- `redirectAiModelsSetting()`

Guidance:

- Use dynamic features for user-created commands or runtime enable/disable flows.
- Keep generated `code` stable and namespaced to avoid collisions.
- Do not dynamically mutate features during every render; centralize updates in preload/service actions.

## Simulated input APIs

Methods:

- `simulateKeyboardTap(key, ...modifiers)`
- `simulateMouseMove(x, y)`, `simulateMouseClick(x, y)`, `simulateMouseDoubleClick(x, y)`, `simulateMouseRightClick(x, y)`

Guidance:

- Use only for explicit automation features; surface risk/preview in UI when coordinates or target app matter.
- Prefer higher-level paste/type APIs when possible.
- Mocks should record requested key/mouse actions for assertions.

## ubrowser programmable browser

Core chain methods:

- Navigation/view: `goto`, `useragent`, `viewport`, `hide`, `show`, `device`, `devTools`
- Page modification/execution: `css`, `evaluate`, `markdown`, `pdf`, `screenshot`
- Interaction: `press`, `click`, `mousedown`, `mouseup`, `dblclick`, `hover`, `input`, `value`, `check`, `focus`, `scroll`, `paste`
- Files/downloads: `file`, `drop`, `download`
- Wait/control: `wait`, `when`, `end`, `run`
- Cookies: `cookies`, `setCookies`, `removeCookies`, `clearCookies`
- Management: `getIdleUBrowsers`, `setUBrowserProxy`

Guidance:

- Build chains declaratively and finish with `run()`.
- Use visible ubrowser for workflows where the user may need to observe/login/intervene.
- Use `markdown(selector)` for page-to-Markdown extraction before inventing custom scraping.
- Always close/end long-lived flows when done or expose a cancel path.

## AI APIs and AI Agent tools

AI model calls:

- `utools.ai(option, streamCallback?)`
- `utools.allAiModels()`

AI Agent tool registration:

- `utools.registerTool(name, handler)`

Guidance:

- `utools.ai` returns a promise-like object with `abort()`. Keep an abort handle in UI for long streaming calls.
- Tool schemas in `plugin.json.tools` must match runtime `registerTool` names exactly.
- Register tools during initialization; do not wait for `onPluginEnter`.
- For long tools, use `ctx.sendProgress?.({ progress, total, message })`.
- Return structured objects and throw explicit errors.

## Sharp and FFmpeg integrations

Methods:

- `utools.sharp(input?, options?)`
- `utools.runFFmpeg(args, onProgress?)`

Guidance:

- Keep image/video processing in preload or AI tool handlers; UI should receive task status and output paths.
- Use `runFFmpeg` progress callback to update UI or AI Agent progress.
- Validate input/output paths and avoid overwriting user files without confirmation.

## Mock design checklist

For each API used by a project, define a browser mock answer:

- Events: fixture actions per `feature.code` and match type.
- Window: booleans for success, tracked sub-input state, no-op dialogs returning sample/cancel paths.
- Clipboard/input: log/toast action and return success.
- System: deterministic `getPath`, platform flags, app/version strings.
- Screen: at least one realistic display and cursor point.
- User: logged-in and logged-out variants.
- DB: in-memory map with `_rev`-like behavior if revision conflicts matter.
- ubrowser: chainable object whose `run()` resolves realistic values.
- AI/Tools: deterministic text/tool results, abort handle, progress callback simulation.
