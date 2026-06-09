# Tauri → uTools 命令映射完整参考

> 将 Tauri 应用迁移到 uTools 插件时，本文档提供：
> - Rust Command → Node.js 实现的完整对照
> - `@tauri-apps/api` → uTools/preload 调用的对照
> - 按功能域分类，便于批量替换
>
> Skill 规则：所有 Node.js/uTools 替代实现都应写在 `utools/preload.ts` 中，并通过 TypeScript 命名导出挂载到 `window[name]`（默认 `window.preload`）。不要把旧式 `window.preload = { ... }` / 手写 `preload.js` 当作源码模板；如遇到旧片段，迁移为命名导出。

---

## 目录

1. [文件系统（fs）](#1-文件系统fs)
2. [路径（path）](#2-路径path)
3. [Shell 与进程（shell / process）](#3-shell-与进程shell--process)
4. [对话框（dialog）](#4-对话框dialog)
5. [剪贴板（clipboard）](#5-剪贴板clipboard)
6. [通知（notification）](#6-通知notification)
7. [HTTP 请求](#7-http-请求)
8. [窗口管理（window）](#8-窗口管理window)
9. [事件系统（event）](#9-事件系统event)
10. [存储（store）](#10-存储store)
11. [全局快捷键](#11-全局快捷键)
12. [系统信息](#12-系统信息)
13. [前端 API 替换速查](#13-前端-api-替换速查)

---

## 1. 文件系统（fs）

### Rust 实现 → `utools/preload.ts` TypeScript 实现

```rust
// ── 原 Tauri Rust Command ──

use std::fs;
use tauri::api::path;

// 读取文本文件
#[tauri::command]
fn read_text_file(path: String) -> Result<String, String> {
    fs::read_to_string(&path).map_err(|e| e.to_string())
}

// 写入文本文件
#[tauri::command]
fn write_text_file(path: String, content: String) -> Result<(), String> {
    fs::write(&path, &content).map_err(|e| e.to_string())
}

// 读取二进制文件
#[tauri::command]
fn read_binary_file(path: String) -> Result<Vec<u8>, String> {
    fs::read(&path).map_err(|e| e.to_string())
}

// 列出目录
#[tauri::command]
fn read_dir(path: String) -> Result<Vec<DirEntry>, String> { ... }

// 创建目录（含父目录）
#[tauri::command]
fn create_dir_all(path: String) -> Result<(), String> {
    fs::create_dir_all(&path).map_err(|e| e.to_string())
}

// 删除文件
#[tauri::command]
fn remove_file(path: String) -> Result<(), String> {
    fs::remove_file(&path).map_err(|e| e.to_string())
}

// 重命名 / 移动
#[tauri::command]
fn rename(old: String, new: String) -> Result<(), String> {
    fs::rename(&old, &new).map_err(|e| e.to_string())
}

// 复制文件
#[tauri::command]
fn copy_file(src: String, dst: String) -> Result<(), String> {
    fs::copy(&src, &dst).map(|_| ()).map_err(|e| e.to_string())
}

// 文件元数据
#[tauri::command]
fn file_metadata(path: String) -> Result<FileMetadata, String> { ... }
```

```ts
// ── utools/preload.ts：命名导出会挂载到 window.preload.* ──
import fs from 'node:fs'
import fsPromises from 'node:fs/promises'
import path from 'node:path'

export const readTextFile = (filePath: string): string => fs.readFileSync(filePath, 'utf-8')
export const readTextFileAsync = (filePath: string): Promise<string> => fsPromises.readFile(filePath, 'utf-8')
export const writeTextFile = (filePath: string, content: string): void => fs.writeFileSync(filePath, content, 'utf-8')
export const writeTextFileAsync = (filePath: string, content: string): Promise<void> => fsPromises.writeFile(filePath, content, 'utf-8')
export const readBinaryFile = (filePath: string): Buffer => fs.readFileSync(filePath)
export const readBinaryFileAsync = (filePath: string): Promise<Buffer> => fsPromises.readFile(filePath)

export function readDir(dirPath: string) {
  return fs.readdirSync(dirPath, { withFileTypes: true }).map(entry => ({
    name: entry.name,
    path: path.join(dirPath, entry.name),
    isFile: entry.isFile(),
    isDirectory: entry.isDirectory(),
    isSymlink: entry.isSymbolicLink(),
  }))
}

export const createDirAll = (dirPath: string): void => fs.mkdirSync(dirPath, { recursive: true })
export const removeFile = (filePath: string): void => fs.unlinkSync(filePath)
export const removeDir = (dirPath: string): void => fs.rmSync(dirPath, { recursive: true, force: true })
export const rename = (oldPath: string, newPath: string): void => fs.renameSync(oldPath, newPath)
export const copyFile = (src: string, dst: string): void => fs.copyFileSync(src, dst)
export const exists = (targetPath: string): boolean => fs.existsSync(targetPath)

export function fileMetadata(filePath: string) {
  const stat = fs.statSync(filePath)
  return {
    size: stat.size,
    isFile: stat.isFile(),
    isDirectory: stat.isDirectory(),
    mtime: stat.mtimeMs,
    ctime: stat.ctimeMs,
    readonly: false,
  }
}

export function watchFile(filePath: string, callback: (eventType: string) => void): () => void {
  const watcher = fs.watch(filePath, eventType => callback(eventType))
  return () => watcher.close()
}

export function watchDir(dirPath: string, callback: (event: { eventType: string; filename: string | null }) => void): () => void {
  const watcher = fs.watch(dirPath, { recursive: true }, (eventType, filename) => callback({ eventType, filename }))
  return () => watcher.close()
}
```
### 前端 `@tauri-apps/api/fs` → preload 调用

```typescript
// ── 原 Tauri 前端 ──
import {
  readTextFile, writeTextFile,
  readBinaryFile, writeBinaryFile,
  readDir, createDir, removeFile, renameFile, copyFile,
  exists, FileEntry
} from '@tauri-apps/api/fs'

const text = await readTextFile('/path/to/file.txt')
await writeTextFile('/path/to/file.txt', 'hello')
const entries = await readDir('/path/to/dir', { recursive: false })

// ── 迁移后 ──
const text = window.preload.readTextFile('/path/to/file.txt')
await window.preload.writeTextFileAsync('/path/to/file.txt', 'hello')
const entries = window.preload.readDir('/path/to/dir')
```

---

## 2. 路径（path）

### Rust → Node.js

```rust
// Tauri path API
use tauri::api::path::{
    home_dir, app_data_dir, app_local_data_dir, app_config_dir,
    app_cache_dir, app_log_dir, temp_dir, document_dir, download_dir,
    picture_dir, video_dir, audio_dir, desktop_dir, public_dir,
};
```

```ts
// ── utools/preload.ts（示意；实际用命名导出）──
const os = require('node:os')
const path = require('node:path')

// Compact mapping shape only; implement each property as a TypeScript named export in utools/preload.ts.
const preloadMapping = {
  // home_dir
  homeDir: () => os.homedir(),

  // app_data_dir（Tauri）→ uTools userData
  appDataDir: () => window.utools.getPath('userData'),

  // temp_dir
  tempDir: () => os.tmpdir(),

  // document_dir
  documentDir: () => {
    const home = os.homedir()
    const platform = process.platform
    if (platform === 'darwin') return path.join(home, 'Documents')
    if (platform === 'win32') return path.join(os.homedir(), 'Documents')
    return path.join(home, 'Documents')  // Linux
  },

  // download_dir
  downloadDir: () => path.join(os.homedir(), 'Downloads'),

  // desktop_dir
  desktopDir: () => path.join(os.homedir(), 'Desktop'),

  // 路径工具
  join: (...parts) => path.join(...parts),
  resolve: (...parts) => path.resolve(...parts),
  dirname: (p) => path.dirname(p),
  basename: (p, ext) => path.basename(p, ext),
  extname: (p) => path.extname(p),
  isAbsolute: (p) => path.isAbsolute(p),
  normalize: (p) => path.normalize(p),
}
```

```typescript
// ── 前端替换 ──
import { homeDir, appDataDir, join } from '@tauri-apps/api/path'

// 原来
const home = await homeDir()
const dataDir = await appDataDir()
const filePath = await join(dataDir, 'config.json')

// 迁移后
const home = window.preload.homeDir()
const dataDir = window.preload.appDataDir()
const filePath = window.preload.join(dataDir, 'config.json')
```

---

## 3. Shell 与进程（shell / process）

### Rust → Node.js

```rust
// 执行外部命令
use std::process::Command;

#[tauri::command]
fn run_command(cmd: String, args: Vec<String>) -> Result<String, String> {
    let output = Command::new(&cmd)
        .args(&args)
        .output()
        .map_err(|e| e.to_string())?;
    Ok(String::from_utf8_lossy(&output.stdout).to_string())
}

// 打开 URL 或文件（系统默认程序）
tauri::api::shell::open(&app.shell_scope(), url, None).unwrap();
```

```ts
// ── utools/preload.ts（示意；实际用命名导出）──
const { execSync, exec, spawn } = require('node:child_process')
const { shell } = require('electron')

// Compact mapping shape only; implement each property as a TypeScript named export in utools/preload.ts.
const preloadMapping = {
  // run_command（同步）
  execSync: (cmd, opts = {}) => execSync(cmd, { encoding: 'utf-8', ...opts }),

  // run_command（异步，返回 Promise）
  exec: (cmd, opts = {}) => new Promise((resolve, reject) => {
    exec(cmd, { encoding: 'utf-8', ...opts }, (err, stdout, stderr) => {
      if (err) reject({ code: err.code, stderr })
      else resolve({ stdout, stderr })
    })
  }),

  // spawn（流式输出，适合长时间运行的命令）
  spawn: (cmd, args = [], opts = {}) => {
    const child = spawn(cmd, args, { ...opts })
    const stopFn = () => child.kill()

    // 通过 window.dispatchEvent 将输出传给渲染层
    child.stdout?.on('data', (data) => {
      window.dispatchEvent(new CustomEvent('spawn:stdout', {
        detail: { data: data.toString() }
      }))
    })
    child.stderr?.on('data', (data) => {
      window.dispatchEvent(new CustomEvent('spawn:stderr', {
        detail: { data: data.toString() }
      }))
    })
    child.on('close', (code) => {
      window.dispatchEvent(new CustomEvent('spawn:close', { detail: { code } }))
    })

    return stopFn  // 返回停止函数
  },

  // open URL（替代 tauri shell::open）
  openUrl: (url) => shell.openExternal(url),
  openPath: (path) => shell.openPath(path),
  showInFolder: (path) => shell.showItemInFolder(path),
}
```

---

## 4. 对话框（dialog）

```typescript
// ── 原 @tauri-apps/api/dialog ──
import { open, save, message, ask, confirm } from '@tauri-apps/api/dialog'

const file = await open({ multiple: false, filters: [...] })
const savePath = await save({ defaultPath: '~/output.txt' })
await message('操作完成', { title: '提示', type: 'info' })
const yes = await ask('确定删除？', { title: '确认', type: 'warning' })
const confirmed = await confirm('此操作不可逆！')
```

```typescript
// ── 迁移后（uTools API，参数基本兼容）──

// open → utools.showOpenDialog
const result = window.utools.showOpenDialog({
  properties: ['openFile'],
  filters: [{ name: 'Text', extensions: ['txt'] }],
})
const file = result?.canceled ? null : result?.filePaths[0]

// save → utools.showSaveDialog
const saveResult = window.utools.showSaveDialog({
  defaultPath: `${window.preload.homeDir()}/output.txt`,
})
const savePath = saveResult?.canceled ? null : saveResult?.filePath

// message → utools.showMessageBox
window.utools.showMessageBox({
  type: 'info',
  title: '提示',
  message: '操作完成',
  buttons: ['确定'],
})

// ask → utools.showMessageBox（两个按钮）
const { response: askResp } = window.utools.showMessageBox({
  type: 'warning',
  title: '确认',
  message: '确定删除？',
  buttons: ['确定', '取消'],
  cancelId: 1,
})
const yes = askResp === 0

// confirm → utools.showMessageBox（同 ask）
const { response: confirmResp } = window.utools.showMessageBox({
  type: 'warning',
  message: '此操作不可逆！',
  buttons: ['确认', '取消'],
  cancelId: 1,
})
const confirmed = confirmResp === 0
```

---

## 5. 剪贴板（clipboard）

```typescript
// ── 原 @tauri-apps/api/clipboard ──
import { readText, writeText } from '@tauri-apps/api/clipboard'

const text = await readText()
await writeText('hello clipboard')
```

```ts
// ── 迁移后 ──

// utools/preload.ts（推荐，更可靠，实际用命名导出）
const { clipboard } = require('electron')
// Compact mapping shape only; implement each property as a TypeScript named export in utools/preload.ts.
const preloadMapping = {
  clipboardRead:  () => clipboard.readText(),
  clipboardWrite: (t) => clipboard.writeText(t),
  clipboardReadImage: () => clipboard.readImage().toDataURL(),
  clipboardWriteImage: (dataURL) => {
    const { nativeImage } = require('electron')
    clipboard.writeImage(nativeImage.createFromDataURL(dataURL))
  },
}

// 渲染层（替代 @tauri-apps/api/clipboard）
const text = window.preload.clipboardRead()          // 同步
window.preload.clipboardWrite('hello clipboard')      // 同步

// 或者直接用 uTools API（仅写入）
window.utools.copyText('hello clipboard')
```

---

## 6. 通知（notification）

```typescript
// ── 原 @tauri-apps/api/notification ──
import { sendNotification, isPermissionGranted, requestPermission }
  from '@tauri-apps/api/notification'

const granted = await isPermissionGranted()
if (!granted) await requestPermission()

sendNotification({
  title: '任务完成',
  body: '文件处理已完成',
})
```

```typescript
// ── 迁移后（uTools 原生通知，无需权限申请）──
window.utools.showNotification(
  '文件处理已完成',
  () => {
    // 可选：点击通知时唤起插件
    window.utools.showMainWindow()
  }
)
```

---

## 7. HTTP 请求

```rust
// Tauri Rust HTTP
use tauri::api::http::{ClientBuilder, HttpRequestBuilder, ResponseType};

#[tauri::command]
async fn fetch_data(url: String) -> Result<String, String> {
    let client = ClientBuilder::new().build().unwrap();
    let response = client.send(
        HttpRequestBuilder::new("GET", &url).unwrap()
    ).await.map_err(|e| e.to_string())?;
    response.data().await.map_err(|e| e.to_string())
        .map(|d| String::from_utf8_lossy(&d.data).to_string())
}
```

```typescript
// ── 迁移后：渲染层直接用 fetch（uTools Chromium 渲染层支持全部 Web API）──

// 简单 GET
const data = await fetch(url).then(r => r.json())

// POST with JSON body
const result = await fetch('https://api.example.com/data', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ key: 'value' }),
}).then(r => r.json())

// 需要 Node.js 能力（如绕过 CORS、自定义 TLS）时用 preload
// utools/preload.ts
const https = require('node:https')
// Compact mapping shape only; implement each property as a TypeScript named export in utools/preload.ts.
const preloadMapping = {
  fetchRaw: (url, opts = {}) => new Promise((resolve, reject) => {
    https.get(url, opts, (res) => {
      let data = ''
      res.on('data', chunk => data += chunk)
      res.on('end', () => resolve({ status: res.statusCode, data }))
    }).on('error', reject)
  }),
}
```

---

## 8. 窗口管理（window）

```typescript
// ── 原 @tauri-apps/api/window ──
import { appWindow, WebviewWindow } from '@tauri-apps/api/window'

// 关闭窗口
await appWindow.close()

// 隐藏窗口
await appWindow.hide()

// 设置标题
await appWindow.setTitle('新标题')

// 最大化
await appWindow.maximize()

// 创建新窗口
const webview = new WebviewWindow('second', {
  url: 'child.html',
  width: 800,
  height: 600,
})
```

```typescript
// ── 迁移后 ──

// close → outPlugin（彻底退出）或 hideMainWindow（隐藏）
window.utools.outPlugin()           // 对应 close
window.utools.hideMainWindow()       // 对应 hide

// setTitle → 不支持（uTools 主窗口标题由 uTools 控制）
// 替代：修改 document.title（在部分版本有效）
document.title = '新标题'

// maximize → 不支持直接最大化，但可设置很大的高度
window.utools.setExpendHeight(window.screen.height)

// 创建子窗口
window.utools.createBrowserWindow('child.html', {
  width: 800,
  height: 600,
  webPreferences: {
    preload: window.preload.join(
      window.utools.getPluginPath(), 'preload.js'
    ),
  },
})
```

---

## 9. 事件系统（event）

```typescript
// ── 原 @tauri-apps/api/event ──
import { emit, listen, once } from '@tauri-apps/api/event'

// 监听事件（来自 Rust 或其他窗口）
const unlisten = await listen('file-changed', (event) => {
  console.log(event.payload)
})

// 发送事件到 Rust 或其他窗口
await emit('user-action', { type: 'click', target: 'button' })

// 取消监听
unlisten()
```

```ts
// ── utools/preload.ts（用 EventEmitter 替代，示意；实际用命名导出）──
const { EventEmitter } = require('node:events')
const bridge = new EventEmitter()
bridge.setMaxListeners(50)  // 防止内存泄漏警告

// Compact mapping shape only; implement each property as a TypeScript named export in utools/preload.ts.
const preloadMapping = {
  // listen → preload.on（返回 unlisten 函数）
  on: (event, handler) => {
    bridge.on(event, handler)
    return () => bridge.off(event, handler)  // unlisten
  },

  // once
  once: (event, handler) => {
    bridge.once(event, handler)
    return () => bridge.off(event, handler)
  },

  // emit（从 preload 向渲染层发送）
  emit: (event, payload) => {
    bridge.emit(event, payload)
    // 同时通过 CustomEvent 发到渲染层 window
    window.dispatchEvent(new CustomEvent(`tauri:${event}`, { detail: payload }))
  },
}

// 使用示例（渲染层）：
const unlisten = window.preload.on('file-changed', (payload) => {
  console.log(payload)
})
// 组件卸载时
onUnmounted(unlisten)
```

---

## 10. 存储（store）

```typescript
// ── 原 tauri-plugin-store ──
import { Store } from 'tauri-plugin-store-api'

const store = new Store('.settings.dat')
await store.set('theme', 'dark')
const theme = await store.get<string>('theme')
await store.save()
```

```typescript
// ── 迁移后（utools.dbStorage，支持云同步）──
// 封装成与 tauri-plugin-store 相似的接口
class UToolsStore {
  private prefix: string

  constructor(name: string) {
    this.prefix = `store:${name}:`
  }

  async set(key: string, value: unknown): Promise<void> {
    window.utools.dbStorage.setItem(`${this.prefix}${key}`, value)
  }

  async get<T>(key: string): Promise<T | null> {
    return window.utools.dbStorage.getItem(`${this.prefix}${key}`) as T | null
  }

  async delete(key: string): Promise<void> {
    window.utools.dbStorage.removeItem(`${this.prefix}${key}`)
  }

  // utools.dbStorage 是自动持久化的，无需 save()
  async save(): Promise<void> {}
}

// 使用
const store = new UToolsStore('.settings.dat')
await store.set('theme', 'dark')
const theme = await store.get<string>('theme')
```

---

## 11. 全局快捷键

```typescript
// ── 原 @tauri-apps/api/globalShortcut ──
import { register, unregisterAll } from '@tauri-apps/api/globalShortcut'

await register('CommandOrControl+Shift+P', () => {
  console.log('快捷键触发')
})
```

```
// ── uTools 中的替代方案 ──
// uTools 本身就是一个快捷键唤醒工具，不支持插件内注册全局快捷键。

// 替代思路：
// 1. 在 plugin.json features.cmds 中定义关键词，用户通过 uTools 搜索框触发
// 2. 用 uTools 的 "超级面板" 功能，让用户划词后选择插件功能
// 3. 如果必须要全局快捷键，需要使用 utools.createBrowserWindow 创建后台窗口
//    并在后台窗口的 utools/preload.ts 中注册（但此方式不官方支持，可能被安全策略拦截）
```

---

## 12. 系统信息

```rust
// 原 Tauri 系统信息
use tauri::api::process::current_binary;
use std::env;
```

```ts
// ── utools/preload.ts（示意；实际用命名导出）──
const os = require('node:os')

// Compact mapping shape only; implement each property as a TypeScript named export in utools/preload.ts.
const preloadMapping = {
  // 操作系统
  platform:    () => process.platform,          // 'darwin' | 'win32' | 'linux'
  arch:        () => process.arch,              // 'x64' | 'arm64'
  hostname:    () => os.hostname(),
  cpus:        () => os.cpus().length,
  totalMemory: () => os.totalmem(),
  freeMemory:  () => os.freemem(),
  osRelease:   () => os.release(),
  nodeVersion: () => process.version,
  electronVersion: () => process.versions.electron,
}

// uTools 原生 API
// window.utools.getPlatform()  → 'darwin' | 'win32' | 'linux'
// window.utools.getAppVersion() → uTools 版本号
// window.utools.isDev()        → 是否开发模式
```

---

## 13. 前端 API 替换速查

快速替换 `@tauri-apps/api` 包的导入语句：

| 原 import | 迁移后调用位置 | 迁移后写法 |
|-----------|-------------|-----------|
| `readTextFile(p)` | `window.preload` | `window.preload.readTextFile(p)` |
| `writeTextFile(p, c)` | `window.preload` | `window.preload.writeTextFile(p, c)` |
| `readDir(p)` | `window.preload` | `window.preload.readDir(p)` |
| `exists(p)` | `window.preload` | `window.preload.exists(p)` |
| `homeDir()` | `window.preload` | `window.preload.homeDir()` |
| `appDataDir()` | `window.utools` | `window.utools.getPath('userData')` |
| `tempDir()` | `window.preload` | `window.preload.tempDir()` |
| `join(...p)` | `window.preload` | `window.preload.join(...p)` |
| `open(opts)` | `window.utools` | `window.utools.showOpenDialog(opts)` |
| `save(opts)` | `window.utools` | `window.utools.showSaveDialog(opts)` |
| `message(msg)` | `window.utools` | `window.utools.showMessageBox({message: msg})` |
| `readText()` | `window.preload` | `window.preload.clipboardRead()` |
| `writeText(t)` | `window.utools` | `window.utools.copyText(t)` |
| `sendNotification(n)` | `window.utools` | `window.utools.showNotification(n.body)` |
| `appWindow.close()` | `window.utools` | `window.utools.outPlugin()` |
| `appWindow.hide()` | `window.utools` | `window.utools.hideMainWindow()` |
| `emit(event, p)` | `window.preload` | `window.preload.emit(event, p)` |
| `listen(event, cb)` | `window.preload` | `window.preload.on(event, cb)` |
| `invoke('cmd', args)` | `window.preload` | `window.preload[camelCase('cmd')](args)` 或 `window.__TAURI_IPC__` 拦截 |
| `convertFileSrc(p)` | 渲染层内联 | `'file://' + p` |
