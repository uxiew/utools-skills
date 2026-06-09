# Skill overlay

> Current skill overlay (2026-06-09): treat this as a quick lookup for `window.utools` methods. For architecture decisions, also read `utools-api-reference.md`; for source-to-dist preload rules, trust `SKILL.md` and `ver5-vite-plugin-utools.md`.

---

# uTools API 速查手册

> uTools 宿主 API 通过 `window.utools.*` 访问；Node/Electron/文件系统等能力应在 `utools/preload.ts` 中用 TypeScript 命名导出封装，再通过 `window.preload.*`（或自定义 `window[name].*`）给 UI 调用。
> 类型定义参考：[utools-api-types](https://github.com/uTools-Labs/utools-api-types)

---

## 目录

1. [插件生命周期](#1-插件生命周期)
2. [窗口与界面控制](#2-窗口与界面控制)
3. [数据存储](#3-数据存储)
4. [文件与路径](#4-文件与路径)
5. [系统交互](#5-系统交互)
6. [搜索与列表模式](#6-搜索与列表模式)
7. [用户与环境信息](#7-用户与环境信息)
8. [AI 工具（Tools）](#8-ai-工具tools)
9. [完整 TypeScript 类型签名](#9-完整-typescript-类型签名)

---

## 1. 插件生命周期

### `utools.onPluginEnter(callback)`

插件被唤起时触发（每次进入都会触发）。

```typescript
window.utools.onPluginEnter(({ code, type, payload }) => {
  // code    → plugin.json features[].code，标识当前触发的功能
  // type    → 触发类型（见下表）
  // payload → 随 type 变化（见下表）
})
```

| `type` | `payload` 类型 | 触发场景 |
|--------|--------------|---------|
| `"text"` | `string` | 搜索框关键词 / 剪贴板文本匹配 |
| `"img"` | `string`（base64 DataURL） | 截图或图像内容匹配 |
| `"files"` | `FilePayload[]` | 拖入或选中文件 |
| `"window"` | `WindowPayload` | 活跃窗口匹配 |
| `"regex"` | `string` | 正则匹配剪贴板/选中文本 |
| `"over"` | `string` | 超级面板划词触发 |

```typescript
// FilePayload 结构
interface FilePayload {
  isFile: boolean
  isDirectory: boolean
  name: string           // 文件名（不含路径）
  path: string           // 绝对路径
}

// WindowPayload 结构
interface WindowPayload {
  title: string          // 窗口标题
  pid: number            // 进程 ID
  app: string            // 应用名（如 "Google Chrome"）
}
```

---

### `utools.onPluginOut(callback)`

插件窗口隐藏时触发（用户按 Esc 或插件调用 hideMainWindow）。

```typescript
window.utools.onPluginOut(() => {
  // 清理定时器、取消监听、保存状态等
})
```

---

### `utools.onPluginDetach(callback)`

插件被彻底卸载时触发（uTools 退出 / 用户手动卸载插件）。

```typescript
window.utools.onPluginDetach(() => {
  // 关闭数据库连接、写入最终状态等
})
```

---

### `utools.onMainPush(callback)`

> **仅适用于 `mode: "none"` 无 UI 插件**

接收来自 uTools 主进程的推送数据。

```typescript
window.utools.onMainPush(({ type, payload }) => {
  // 无 UI 插件通过此 API 接收触发信号
})
```

---

## 2. 窗口与界面控制

### 窗口高度

```typescript
// 动态设置插件内容区高度（不含 uTools 搜索框的高度）
// 范围：[0, 屏幕高度]，0 表示收起内容区
window.utools.setExpendHeight(height: number): void

// 示例：内容高度自适应（配合 ResizeObserver）
const ro = new ResizeObserver(([e]) =>
  window.utools.setExpendHeight(Math.ceil(e.contentRect.height))
)
ro.observe(document.getElementById('app')!)
```

---

### 窗口显隐

```typescript
// 隐藏插件窗口，回到系统前台（保持插件进程存活）
window.utools.hideMainWindow(): void

// 隐藏插件窗口，并在隐藏后使前一个活跃应用重新获得焦点
window.utools.hideMainWindow(isRestoreOnMain?: boolean): void

// 彻底退出插件（回收内存，下次使用重新初始化）
window.utools.outPlugin(): void

// 显示插件主窗口（从隐藏状态唤回）
window.utools.showMainWindow(): void
```

---

### 子窗口（多窗口）

```typescript
// 创建附属子窗口（替代 new BrowserWindow()）
// ⚠️ 必须在 webPreferences 中配置 preload，否则子窗口无法使用 Node.js 能力
window.utools.createBrowserWindow(
  url: string,                           // HTML 路径（相对于插件根目录）
  options: BrowserWindowConstructorOptions,  // 兼容 Electron 原生选项
  callback?: () => void                  // 窗口创建完成回调
): void

// 示例
window.utools.createBrowserWindow('child.html', {
  width: 800,
  height: 600,
  frame: false,          // 无边框
  transparent: true,     // 透明背景
  alwaysOnTop: true,
  webPreferences: {
    preload: window.preload.join(__dirname, 'preload.js'),
  },
})
```

---

### 系统主题

```typescript
// 获取当前是否为深色模式（推荐替代 CSS @media prefers-color-scheme）
window.utools.isDarkColors(): boolean

// 示例：初始化主题
document.documentElement.classList.toggle('dark', window.utools.isDarkColors())
```

---

### 通知

```typescript
// 显示系统级通知（右下角弹出）
window.utools.showNotification(
  body: string,          // 通知内容
  clickHandler?: () => void  // 点击通知的回调
): void

// 示例
window.utools.showNotification('文件处理完成！', () => {
  window.utools.showMainWindow()
})
```

---

## 3. 数据存储

uTools 提供两套存储 API，均支持**自动云同步**（用户开启后）。

### 3.1 dbStorage（简单键值对）

接口与 `localStorage` 完全一致，但数据持久化且支持云同步。

```typescript
// 读取
window.utools.dbStorage.getItem(key: string): any | null

// 写入（value 支持任意 JSON 可序列化类型）
window.utools.dbStorage.setItem(key: string, value: any): void

// 删除
window.utools.dbStorage.removeItem(key: string): void

// 示例
window.utools.dbStorage.setItem('theme', 'dark')
const theme = window.utools.dbStorage.getItem('theme')  // 'dark'
window.utools.dbStorage.setItem('config', { fontSize: 14, lang: 'zh' })
```

---

### 3.2 db（文档型存储，类 CouchDB）

适合复杂数据结构、批量查询、附件存储场景。

```typescript
// ── 读取 ──
window.utools.db.get(id: string): DbDoc | null

// ── 写入/更新（⚠️ 更新时必须携带 _rev，否则 409 冲突）──
window.utools.db.put(doc: DbDoc): DbResult

// ── 删除 ──
window.utools.db.remove(doc: DbDoc): DbResult
window.utools.db.remove(id: string, rev: string): DbResult

// ── 批量查询（前缀匹配）──
window.utools.db.allDocs(prefix?: string): DbDoc[]

// ── 附件操作 ──
window.utools.db.putAttachment(
  id: string,
  attachmentId: string,
  attachment: Uint8Array | Buffer,
  type: string            // MIME 类型，如 'image/png'
): DbResult

window.utools.db.getAttachment(
  id: string,
  attachmentId: string
): Uint8Array | null

window.utools.db.getAttachmentType(
  id: string,
  attachmentId: string
): string | null

// ── 异步版本（db.promises.*，与同步版参数相同）──
window.utools.db.promises.get(id)
window.utools.db.promises.put(doc)
window.utools.db.promises.remove(doc)
window.utools.db.promises.allDocs(prefix)
```

```typescript
// 类型定义
interface DbDoc {
  _id: string            // 文档 ID（唯一标识）
  _rev?: string          // 修订号（每次更新后由 db 自动生成，更新时必传）
  [key: string]: any     // 业务数据字段
}

interface DbResult {
  id: string
  ok: boolean
  rev: string            // 新的 _rev 值
  error?: boolean
  name?: string          // 错误名称
  message?: string       // 错误信息
}
```

```ts
// 最佳实践：封装 set 操作自动处理 _rev
function dbSet(id: string, data: unknown) {
  const existing = window.utools.db.get(id)
  return window.utools.db.put(
    existing ? { ...existing, data } : { _id: id, data }
  )
}

// 最佳实践：语义化 _id 路径策略
// 'settings/ui/theme'     → 主题设置
// 'settings/network'      → 网络配置
// 'notes/2025/06/01'      → 按日期分组的笔记
// 'cache/search/keywords' → 搜索缓存
const notes = window.utools.db.allDocs('notes/2025/')  // 前缀查询
```

---

## 4. 文件与路径

### 系统路径

```typescript
// 获取系统特殊路径
window.utools.getPath(name: PathName): string

type PathName =
  | 'home'        // 用户主目录（~）
  | 'appData'     // 系统应用数据目录
  | 'userData'    // 当前 uTools 用户数据目录（插件数据推荐存放处）
  | 'temp'        // 系统临时目录
  | 'desktop'     // 桌面
  | 'documents'   // 文档目录
  | 'downloads'   // 下载目录
  | 'music'       // 音乐目录
  | 'pictures'    // 图片目录
  | 'videos'      // 视频目录

// 示例
const userDataDir = window.utools.getPath('userData')
// macOS: /Users/xxx/Library/Application Support/uTools/xxx
// Windows: C:\Users\xxx\AppData\Roaming\uTools\xxx
```

---

### 文件对话框

```typescript
// 打开文件/目录选择框（同步，返回选择结果）
window.utools.showOpenDialog(options: OpenDialogOptions): {
  canceled: boolean
  filePaths: string[]
} | null

interface OpenDialogOptions {
  title?: string
  defaultPath?: string
  buttonLabel?: string
  filters?: Array<{ name: string; extensions: string[] }>
  properties?: Array<
    | 'openFile'           // 选择文件
    | 'openDirectory'      // 选择目录
    | 'multiSelections'    // 多选
    | 'showHiddenFiles'    // 显示隐藏文件
    | 'createDirectory'    // macOS 允许创建新目录
    | 'promptToCreate'     // Windows 询问是否创建
    | 'noResolveAliases'   // macOS 不解析符号链接
    | 'treatPackageAsDirectory' // macOS 将 .app 包作为目录处理
  >
}

// 示例：选择图片文件（多选）
const result = window.utools.showOpenDialog({
  title: '选择图片',
  filters: [{ name: '图片文件', extensions: ['jpg', 'jpeg', 'png', 'gif', 'webp'] }],
  properties: ['openFile', 'multiSelections'],
})
if (!result?.canceled) {
  console.log(result.filePaths)  // string[]
}
```

```typescript
// 保存文件对话框
window.utools.showSaveDialog(options: SaveDialogOptions): {
  canceled: boolean
  filePath?: string
} | null

interface SaveDialogOptions {
  title?: string
  defaultPath?: string
  buttonLabel?: string
  filters?: Array<{ name: string; extensions: string[] }>
  properties?: Array<'showHiddenFiles' | 'createDirectory' | 'treatPackageAsDirectory'>
}

// 示例
const result = window.utools.showSaveDialog({
  title: '保存文件',
  defaultPath: '~/Documents/output.txt',
  filters: [{ name: '文本文件', extensions: ['txt'] }],
})
if (!result?.canceled && result?.filePath) {
  // 写入文件
  window.preload.writeFile(result.filePath, content)
}
```

```typescript
// 消息对话框
window.utools.showMessageBox(options: MessageBoxOptions): {
  response: number      // 点击的按钮索引
  checkboxChecked: boolean
}

interface MessageBoxOptions {
  type?: 'none' | 'info' | 'error' | 'question' | 'warning'
  buttons?: string[]    // 按钮文本数组
  defaultId?: number    // 默认选中的按钮索引
  cancelId?: number     // 取消按钮索引
  title?: string
  message: string
  detail?: string
  checkboxLabel?: string
  checkboxChecked?: boolean
}

// 示例：确认删除
const { response } = window.utools.showMessageBox({
  type: 'warning',
  buttons: ['删除', '取消'],
  defaultId: 1,
  cancelId: 1,
  title: '确认删除',
  message: '此操作不可撤销，确认删除？',
})
if (response === 0) { /* 执行删除 */ }
```

---

### 剪贴板

```typescript
// 复制文本到剪贴板（⚠️ 不推荐用 navigator.clipboard，这个更可靠）
window.utools.copyText(text: string): boolean

// 复制文件到剪贴板（供粘贴到资源管理器等）
window.utools.copyFile(filePath: string | string[]): boolean

// 复制图片到剪贴板（base64 DataURL 或本地路径）
window.utools.copyImage(image: string): boolean

// 示例
window.utools.copyText('Hello, uTools!')
window.utools.copyFile(['/path/to/file1.txt', '/path/to/file2.txt'])
window.utools.copyImage('/path/to/image.png')
```

---

## 5. 系统交互

### Shell 操作

```typescript
// 在系统默认程序中打开文件/URL
window.utools.shellOpenExternal(url: string): void
// 等同于 preload 中的 require('electron').shell.openExternal(url)

// 在文件管理器中定位并高亮显示文件
window.utools.shellShowItemInFolder(fullPath: string): void

// 在终端中执行命令（macOS 打开 Terminal，Windows 打开 CMD/PowerShell）
// ⚠️ 此 API 在不同版本中可能有差异，建议用 preload 中的 child_process
window.utools.shellOpenPath(fullPath: string): void
```

---

### 系统信息

```typescript
// 获取当前操作系统类型
window.utools.getPlatform(): 'darwin' | 'win32' | 'linux'

// 获取 uTools 版本号
window.utools.getAppVersion(): string

// 获取当前用户的 uTools 账号 ID（未登录返回 null）
window.utools.getNativeId(): string | null

// 判断当前是否在开发者模式下运行
window.utools.isDev(): boolean

// 示例：平台适配
const isMac = window.utools.getPlatform() === 'darwin'
const isWin = window.utools.getPlatform() === 'win32'
```

---

### 剪贴板读取（进入时的上下文内容）

```typescript
// 获取用户进入插件时的剪贴板文本（onPluginEnter 的 text 类型 payload 即此值）
window.utools.getClipboardText(): string

// 进入插件时选中的文件列表（onPluginEnter 的 files 类型 payload 即此值）
window.utools.getClipboardFiles(): FilePayload[]
```

---

## 6. 搜索与列表模式

当插件使用 `mode: "list"` 时，uTools 提供原生的搜索框与滚动列表渲染优化。

```typescript
// 设置列表模式下的搜索关键词变化回调
window.utools.setSubInput(
  callback: (word: { word: string }) => void,
  placeholder?: string,
  isFocus?: boolean           // 是否自动获取焦点
): boolean

// 移除子输入框
window.utools.removeSubInput(): boolean

// 设置子输入框的值（程序化修改）
window.utools.setSubInputValue(value: string): boolean

// 获取当前子输入框的值
window.utools.getSubInput(): { word: string }

// 示例：实时搜索过滤
window.utools.setSubInput(({ word }) => {
  filteredList.value = allItems.filter(item =>
    item.title.toLowerCase().includes(word.toLowerCase())
  )
}, '搜索...')
```

---

## 7. 用户与环境信息

```typescript
// 获取当前登录用户信息（未登录返回 null）
window.utools.getUser(): {
  avatar: string    // 头像 URL
  nickname: string  // 昵称
  type: number      // 账号类型
} | null

// 获取当前插件的安装路径（plugin.json 所在目录）
window.utools.getPluginPath(): string

// 判断是否是第一次运行此版本（版本更新后首次启动返回 true）
window.utools.isFirstWindowLoad(): boolean

// 示例：版本更新引导
if (window.utools.isFirstWindowLoad()) {
  showWhatsNewDialog()
}
```

---

## 8. AI 工具（Tools）

> uTools 4+ 新特性，需在 `plugin.json` 中声明 `tools` 字段。

```typescript
// 注册 AI 工具调用处理器
// 当 AI Agent 调用插件声明的工具时触发
window.utools.onToolCall(
  callback: (toolName: string, input: Record<string, any>) => Promise<any> | any
): void

// 示例
window.utools.onToolCall(async (toolName, input) => {
  switch (toolName) {
    case 'read_local_file':
      return { content: window.preload.readFile(input.path) }
    case 'list_directory':
      return { files: window.preload.readDir(input.path) }
    default:
      throw new Error(`未知工具: ${toolName}`)
  }
})
```

---

## 9. 完整 TypeScript 类型签名

> 安装 `@ver5/vite-plugin-utools` 或 `utools-api-types` 后自动获得以下类型。
> 也可在 `tsconfig.json` 中添加 `"types": ["@ver5/vite-plugin-utools/utools"]`。

```typescript
interface UTools {
  // ── 生命周期 ──
  onPluginEnter(callback: (payload: PluginEnterPayload) => void): void
  onPluginOut(callback: () => void): void
  onPluginDetach(callback: () => void): void
  onMainPush(callback: (payload: any) => void): void
  onToolCall(callback: (name: string, input: any) => Promise<any> | any): void

  // ── 窗口控制 ──
  setExpendHeight(height: number): void
  hideMainWindow(isRestoreOnMain?: boolean): void
  showMainWindow(): void
  outPlugin(): void
  createBrowserWindow(url: string, options: any, callback?: () => void): void

  // ── 主题 ──
  isDarkColors(): boolean

  // ── 通知 ──
  showNotification(body: string, clickHandler?: () => void): void

  // ── 存储 ──
  dbStorage: {
    getItem(key: string): any | null
    setItem(key: string, value: any): void
    removeItem(key: string): void
  }
  db: {
    get(id: string): DbDoc | null
    put(doc: DbDoc): DbResult
    remove(doc: DbDoc): DbResult
    remove(id: string, rev: string): DbResult
    allDocs(prefix?: string): DbDoc[]
    putAttachment(id: string, attId: string, data: Uint8Array, type: string): DbResult
    getAttachment(id: string, attId: string): Uint8Array | null
    getAttachmentType(id: string, attId: string): string | null
    promises: {
      get(id: string): Promise<DbDoc | null>
      put(doc: DbDoc): Promise<DbResult>
      remove(doc: DbDoc): Promise<DbResult>
      allDocs(prefix?: string): Promise<DbDoc[]>
    }
  }

  // ── 文件与路径 ──
  getPath(name: PathName): string
  showOpenDialog(options: OpenDialogOptions): OpenDialogResult | null
  showSaveDialog(options: SaveDialogOptions): SaveDialogResult | null
  showMessageBox(options: MessageBoxOptions): MessageBoxResult

  // ── 剪贴板 ──
  copyText(text: string): boolean
  copyFile(path: string | string[]): boolean
  copyImage(image: string): boolean
  getClipboardText(): string
  getClipboardFiles(): FilePayload[]

  // ── 系统 ──
  shellOpenExternal(url: string): void
  shellShowItemInFolder(path: string): void
  shellOpenPath(path: string): void
  getPlatform(): 'darwin' | 'win32' | 'linux'
  getAppVersion(): string
  getNativeId(): string | null
  isDev(): boolean
  isFirstWindowLoad(): boolean
  getPluginPath(): string

  // ── 子输入框（列表模式）──
  setSubInput(callback: (word: { word: string }) => void, placeholder?: string, isFocus?: boolean): boolean
  removeSubInput(): boolean
  setSubInputValue(value: string): boolean
  getSubInput(): { word: string }

  // ── 用户 ──
  getUser(): { avatar: string; nickname: string; type: number } | null
}

declare global {
  interface Window {
    utools: UTools
  }
}
```
