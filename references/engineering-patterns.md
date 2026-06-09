# Skill overlay

> Current skill overlay (2026-06-09): use `@ver5/vite-plugin-utools + TypeScript` as the default engineering workflow. Author source preload only as `utools/preload.ts`, set source `utools/plugin.json` to `"preload": "preload.ts"`, and expose services with TypeScript named exports mounted to `window[name]` (`window.preload` by default). Browser mock is only for simple UI preview in a normal browser. The production package should still contain generated `dist/preload.js`, and that final `.js` must not sit under a `type: module` package scope unless a nearer `{ "type": "commonjs" }` package file overrides it. When this file conflicts with live official docs or the skill root, trust the skill root and live runtime first.

---

# uTools 插件工程化转换全景指南

> **定位**：本文是 `uxiew/utools-skills` 的核心参考文档。覆盖 uTools 底层沙箱机制、
> 六大前端框架接入、Electron 应用降维、Tauri 多语言桥接、原生模块重编译，以及完整的
> 工程化工具链体系。
>
> **配套工具**：[`@ver5/vite-plugin-utools`](https://github.com/uxiew/vite-plugin-utools)

---

## 目录

1. [底层架构透视](#1-底层架构透视)
2. [plugin.json 配置全解](#2-pluginjson-配置全解)
3. [preload.ts 工程化](#3-preloadts-工程化)
4. [Bridge 层设计：跨环境 API 适配](#4-bridge-层设计跨环境-api-适配)
5. [构建工具链选型与配置](#5-构建工具链选型与配置)
6. [Web 框架迁移（Vue / React / Angular / Svelte / Solid）](#6-web-框架迁移)
7. [Electron 应用 → uTools 降维迁移](#7-electron-应用--utools-降维迁移)
8. [Tauri 应用 → uTools 跨语言桥接](#8-tauri-应用--utools-跨语言桥接)
9. [数据持久化重构与云同步](#9-数据持久化重构与云同步)
10. [原生模块（Native Modules）ABI 重编译](#10-原生模块-abi-重编译)
11. [通用工程化模式](#11-通用工程化模式)
12. [常见陷阱与解决方案](#12-常见陷阱与解决方案)

---

## 1. 底层架构透视

uTools 本质是一个**经深度定制的 Electron 宿主容器**，结合了 Node.js 本地能力与 Chromium
渲染技术，形成"双引擎"沙箱架构。

### 1.1 三层运行模型

```
┌──────────────────────────────────────────────────────────────────┐
│                    uTools 宿主进程（Electron Main）               │
│                                                                  │
│   ┌──── 插件渲染进程（Chromium Renderer）────────────────────┐    │
│   │                                                          │    │
│   │   index.html + 前端框架（Vue/React/…）                   │    │
│   │         │ window.utools.*                               │    │
│   │         │ window.exports.* / window.preload.*           │    │
│   │   ┌─────▼──────────────────┐                            │    │
│   │   │   dist/preload.js      │  ← 由 preload.ts 构建生成    │    │
│   │   │   (CommonJS · Node)    │  ← 禁止压缩混淆             │    │
│   │   │   require('fs')        │                            │    │
│   │   │   require('electron')  │  ← 仅限渲染进程子集         │    │
│   │   └────────────────────────┘                            │    │
│   └──────────────────────────────────────────────────────────┘    │
│                                                                  │
│   uTools API：文件对话框 / 通知 / 数据库 / 窗口 / 主题 / AI Tools  │
└──────────────────────────────────────────────────────────────────┘
```

### 1.2 关键约束速查

| 约束项 | 规则 | 违反后果 |
|--------|------|---------|
| preload 源码 | **必须使用 `utools/preload.ts` + 命名导出** | mock/类型/构建失效 |
| dist/preload.js | 由 `@ver5/vite-plugin-utools` 生成，需 CommonJS 可执行 | 运行时报错 |
| preload 安全 | **禁止压缩/混淆**，需明文通过安全审查 | 上架审核拒绝 |
| Node.js 版本 | uTools 内置 **Node 16.x**，勿单独安装 electron | ABI 冲突崩溃 |
| Electron API 范围 | 仅渲染进程子集（`clipboard` / `shell` / `ipcRenderer`） | 调用报错 |
| 渲染层路由 | 必须 **Hash 路由**，不能 HTML5 History | 深层路由白屏 |
| 资源路径 | Vite 必须 `base: './'`（相对路径） | 资源 404 |
| 主进程概念 | uTools 插件**没有主进程**，无 BrowserWindow、Menu 等 | 架构重构 |

---

## 2. plugin.json 配置全解

`plugin.json` 是插件的核心配置与指令路由中枢。

### 2.1 完整字段注释

```jsonc
{
  // IDE 字段提示（推荐）
  "$schema": "../node_modules/@ver5/vite-plugin-utools/utools.schema.json",

  // ── 基础元信息（发布后 pluginName 不可更改）──
  "pluginName": "my-awesome-plugin",
  "version": "1.0.0",
  "description": "插件功能简述",
  "author": "your-name",
  "homepage": "https://github.com/your-name/my-plugin",

  // ── 运行入口 ──
  "main": "index.html",     // 前端页面入口（相对路径）
  "preload": "preload.ts",  // 源码清单：由 @ver5/vite-plugin-utools 构建为 dist/preload.js
  "logo": "logo.png",       // 插件图标（推荐 256×256 PNG）

  // ── 窗口配置 ──
  "singleton": true,        // 单例模式（默认 true）
  "height": 400,            // 初始内容区高度（px），可通过 API 动态修改

  // ── 无 UI 静默模式（适合纯后台脚本插件）──
  // "mode": "none",         // 无界面静默运行，不渲染 main

  // ── AI Agent 工具暴露（uTools 4+ 新特性）──
  // 将插件能力以 JSON Schema 格式暴露给 AI 大模型
  "tools": [
    {
      "name": "read_local_file",
      "description": "读取本地指定路径的文件内容",
      "inputSchema": {
        "type": "object",
        "properties": {
          "path": { "type": "string", "description": "文件绝对路径" }
        },
        "required": ["path"]
      },
      "outputSchema": {
        "type": "object",
        "properties": {
          "content": { "type": "string" }
        }
      }
    }
  ],

  // ── 功能指令列表（意图识别路由）──
  "features": [
    {
      "code": "main",           // 对应 onPluginEnter 的 code
      "explain": "打开主功能",
      "cmds": ["关键词", "另一个关键词"]  // 关键词触发
    },
    {
      "code": "open-url",
      "explain": "打开链接",
      "cmds": [
        {
          "type": "regex",      // 正则匹配剪贴板/选中内容
          "label": "识别 URL",
          "match": "/^https?:\\/\\//i",
          "minLength": 8,
          "maxLength": 2048
        }
      ]
    },
    {
      "code": "handle-image",
      "explain": "处理图片文件",
      "cmds": [
        {
          "type": "files",      // 拖入/选中文件触发
          "label": "图片文件",
          "fileType": "image",  // image | video | audio | directory
          "minCount": 1,
          "maxCount": 20
        }
      ]
    },
    {
      "code": "window-action",
      "explain": "对当前窗口执行操作",
      "cmds": [
        {
          "type": "window",     // 捕获活跃窗口进程名
          "label": "浏览器窗口",
          "match": "/chrome|firefox|safari/i"
        }
      ]
    },
    {
      "code": "clipboard-action",
      "explain": "超级面板（划词触发）",
      "cmds": [
        {
          "type": "over"        // 任意选中内容触发超级面板
        }
      ]
    }
  ]
}
```

### 2.2 features.cmds 类型一览

| type | 触发方式 | payload 类型 | 关键字段 |
|------|---------|-------------|---------|
| *(string)* | 主搜索框关键词 | `string` | — |
| `"regex"` | 剪贴板/选中文本正则 | `string` | `match`, `minLength`, `maxLength` |
| `"files"` | 拖入或选中文件 | `Array<{name, path, isFile, isDirectory}>` | `fileType`, `minCount`, `maxCount` |
| `"window"` | 活跃窗口进程名正则 | `{title, pid, app}` | `match` |
| `"img"` | 截图/图像内容 | `string`（base64） | — |
| `"over"` | 超级面板划词 | `string` | — |

---

## 3. preload.ts 工程化

### 3.1 模块化 preload（TypeScript → CJS，配合 @ver5/vite-plugin-utools）

```typescript
// utools/preload.ts

import fs from 'node:fs'
import path from 'node:path'
import os from 'node:os'
import { clipboard, shell } from 'electron'

// ── 命名导出 → 挂载到 window[name]（配置 name: 'preload' 时即 window.preload）──

export const readFile = (filePath: string): string =>
  fs.readFileSync(filePath, 'utf-8')

export const writeFile = (filePath: string, content: string): void =>
  fs.writeFileSync(filePath, content, 'utf-8')

export const exists = (p: string): boolean => fs.existsSync(p)

export const readDir = (dir: string): fs.Dirent[] =>
  fs.readdirSync(dir, { withFileTypes: true })

export const exec = (cmd: string): string => {
  const { execSync } = require('node:child_process')
  return execSync(cmd, { encoding: 'utf-8' })
}

export const clipboardRead = (): string => clipboard.readText()
export const clipboardWrite = (text: string): void => clipboard.writeText(text)

export const openExternal = (url: string): void => { shell.openExternal(url) }
export const openPath = (p: string): void => { shell.openPath(p) }

export const homedir = (): string => os.homedir()
export const tmpdir = (): string => os.tmpdir()
export const joinPath = (...args: string[]): string => path.join(...args)

// ── 生命周期钩子（在 preload 中注册）──

window.utools.onPluginEnter(({ code, type, payload }) => {
  // 记录进入信息供渲染层读取
  ;(window as any).__utools_enter__ = { code, type, payload }
})

window.utools.onPluginOut(() => {
  ;(window as any).__utools_enter__ = null
  // 清理资源、关闭数据库连接等
})

window.utools.onPluginDetach(() => {
  // 插件被彻底卸载，做最终清理
})

// ── 默认导出 → 直接挂载到 window（用于简单的全局属性）──
export default {
  pluginVersion: '1.0.0',
}
```

### 3.2 不再推荐手写 JS preload 源码

本 Skill 的工程路径是 `@ver5/vite-plugin-utools + TypeScript`：

- 源码只维护 `utools/preload.ts`。
- 源码 `utools/plugin.json` 写 `"preload": "preload.ts"`。
- 页面服务通过 `preload.ts` 命名导出暴露，并由插件配置 `name` 挂载到 `window[name]`，默认 `window.preload`。
- `preload.js` 只作为 `vite build` 后的运行时产物存在，不作为手写源码模板。

如果旧项目已有手写 `window.preload = { readFile() {} }`，迁移时应改为：

```ts
// utools/preload.ts
import { readFileSync } from 'node:fs'

/** Read a UTF-8 text file. */
export function readFile(path: string): string {
  return readFileSync(path, 'utf-8')
}
```

页面层仍按 `window.preload.readFile(path)` 调用，因为命名导出会由插件挂载到默认命名空间。

### 3.3 可用的 Electron API 子集

```ts
// dist/preload.js 运行时 require('electron') 可用部分
const {
  // ✅ 渲染进程 API — 可用
  clipboard,      // 剪贴板读写（文本/图片/RTF/HTML）
  shell,          // 打开文件/URL，在文件管理器显示
  ipcRenderer,    // IPC 通信（谨慎使用）
  nativeImage,    // 图片格式转换
  crashReporter,  // 崩溃上报

  // ❌ 主进程 API — 不可用，使用 utools.* 替代
  // app, BrowserWindow, Menu, Tray, dialog
  // globalShortcut, powerMonitor, screen
} = require('electron')

// ── uTools 对应替代 API ──
// dialog.showOpenDialog   → window.utools.showOpenDialog()
// dialog.showSaveDialog   → window.utools.showSaveDialog()
// dialog.showMessageBox   → window.utools.showMessageBox()
// app.getPath('userData') → window.utools.getPath('userData')
// new BrowserWindow()     → window.utools.createBrowserWindow()
// Notification            → window.utools.showNotification()
```

---

## 4. Bridge 层设计：跨环境 API 适配

Bridge 层让同一套业务代码在**浏览器开发态**和 **uTools 生产态**均可运行，
这是工程化迁移的核心设计模式。

### 4.1 接口定义

```typescript
// src/bridge/types.ts

export interface BridgeFS {
  readFile(path: string): string
  writeFile(path: string, content: string): void
  exists(path: string): boolean
  readDir(path: string): Array<{ name: string; isDir: boolean }>
  homedir(): string
  tmpdir(): string
}

export interface BridgeClipboard {
  read(): string
  write(text: string): void
  readImage?(): string  // base64 data URL
}

export interface BridgeSystem {
  openExternal(url: string): void
  openPath(path: string): void
  exec?(cmd: string): string
}

export interface Bridge {
  fs: BridgeFS
  clipboard: BridgeClipboard
  system: BridgeSystem
}
```

### 4.2 uTools 生产环境实现

```typescript
// src/bridge/utools.ts
import type { Bridge } from './types'

declare global {
  interface Window {
    preload: {
      readFile(p: string): string
      writeFile(p: string, c: string): void
      exists(p: string): boolean
      readDir(p: string): Array<{ name: string; isDirectory(): boolean }>
      homedir(): string
      tmpdir(): string
      clipRead(): string
      clipWrite(t: string): void
      clipImage(): string
      openURL(url: string): void
      openPath(p: string): void
      exec(cmd: string): string
    }
  }
}

export const utoolsBridge: Bridge = {
  fs: {
    readFile:  (p) => window.preload.readFile(p),
    writeFile: (p, c) => window.preload.writeFile(p, c),
    exists:    (p) => window.preload.exists(p),
    readDir:   (p) => window.preload.readDir(p).map(e => ({
      name: e.name,
      isDir: e.isDirectory(),
    })),
    homedir:   () => window.preload.homedir(),
    tmpdir:    () => window.preload.tmpdir(),
  },
  clipboard: {
    read:       () => window.preload.clipRead(),
    write:      (t) => window.preload.clipWrite(t),
    readImage:  () => window.preload.clipImage(),
  },
  system: {
    openExternal: (url) => window.preload.openURL(url),
    openPath:     (p) => window.preload.openPath(p),
    exec:         (cmd) => window.preload.exec(cmd),
  },
}
```

### 4.3 浏览器 Mock 实现（开发态）

```typescript
// src/bridge/mock.ts
import type { Bridge } from './types'

// 内存文件系统（开发态模拟）
const memFS: Record<string, string> = {}

export const mockBridge: Bridge = {
  fs: {
    readFile:  (p) => {
      if (!(p in memFS)) throw new Error(`[mock] File not found: ${p}`)
      return memFS[p]
    },
    writeFile: (p, c) => { memFS[p] = c },
    exists:    (p) => p in memFS,
    readDir:   (_p) => [],
    homedir:   () => '/mock/home/user',
    tmpdir:    () => '/mock/tmp',
  },
  clipboard: {
    read:  () => sessionStorage.getItem('__mock_clip__') ?? '',
    write: (t) => sessionStorage.setItem('__mock_clip__', t),
  },
  system: {
    openExternal: (url) => window.open(url, '_blank'),
    openPath:     (p)   => console.info('[mock] openPath:', p),
    exec:         (cmd) => { console.info('[mock] exec:', cmd); return '' },
  },
}
```

### 4.4 Bridge 工厂（自动选择环境）

```typescript
// src/bridge/index.ts
import type { Bridge } from './types'

const isUTools = (): boolean =>
  typeof window !== 'undefined' && 'utools' in window

let _instance: Bridge | null = null

export async function getBridge(): Promise<Bridge> {
  if (_instance) return _instance
  if (isUTools()) {
    const { utoolsBridge } = await import('./utools')
    _instance = utoolsBridge
  } else {
    const { mockBridge } = await import('./mock')
    _instance = mockBridge
  }
  return _instance
}

// 同步访问（需已调用 getBridge() 初始化）
export function bridge(): Bridge {
  if (!_instance) throw new Error('Bridge not initialized')
  return _instance
}
```

---

## 5. 构建工具链选型与配置

### 5.1 社区 Vite 插件横向对比

| 插件 | 核心特性 | 适用场景 |
|------|---------|---------|
| **`@ver5/vite-plugin-utools`** *(推荐)* | TypeScript preload 支持、自动 Mock 注入、Mock Badge、HMR、upx 打包、vConsole | 全功能推荐首选，适合本 repo 技术栈 |
| `@qc2168/vite-plugin-utools` | 零配置体验、多入口预加载、依赖自动剥离 | 快速原型、初中级开发者 |
| `vite-plugin-utools-helper` (csj8520) | 细粒度控制、强制禁止 preload 压缩 | 高级开发者，需绝对控制产物 |
| `vite-plugin-utools` (13enBi) | 最早期方案，预加载独立编译范式 | 历史项目维护，社区长期验证 |

### 5.2 @ver5/vite-plugin-utools 完整配置

```typescript
// vite.config.ts
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import utools from '@ver5/vite-plugin-utools'

export default defineConfig(({ command }) => {
  const isProd = command === 'build'
  return {
    // ⚠️ 关键：uTools 通过 file:// 加载，必须用相对路径
    base: './',

    plugins: [
      vue(),
      utools({
        // plugin.json 路径（唯一必填项）
        configFile: './utools/plugin.json',

        // preload 命名导出挂载到 window[name]
        name: 'preload',

        // 生产环境压缩 preload
        // ⚠️ 注意：uTools 应用市场要求 preload.js 明文，
        //          此选项仅适用于不上架应用市场的私有插件
        minify: false,

        // 排除不需要打包的依赖
        external: ['better-sqlite3'],

        // 开发 Mock：仅用于普通浏览器里的 UI 预览/契约检查
        mock: { enabled: !isProd, showBadge: !isProd },

        // vConsole 调试（仅开发态）
        vconsole: !isProd,

        // 生产打 .upx 包
        upx: isProd ? {
          outDir: 'dist',
          outName: '[pluginName]_[version].upx',
        } : false,

        // 合并到 preload 子构建的 Vite 配置
        viteConfig: {
          define: {
            __PLUGIN_VERSION__: JSON.stringify(process.env.npm_package_version),
          },
        },
      }),
    ],

    build: {
      rollupOptions: {
        output: {
          // 分离 vendor，减小首屏体积（uTools 插件对冷启动敏感）
          manualChunks: { vendor: ['vue', 'pinia'] },
        },
      },
    },
  }
})
```

### 5.3 TypeScript 配置

```jsonc
// tsconfig.json
{
  "compilerOptions": {
    "types": [
      "@ver5/vite-plugin-utools/utools"  // window.utools 类型提示
    ]
  },
  "include": [
    "src",
    "utools/**/*.ts"  // preload.ts 类型提示
  ]
}
```

---

## 6. Web 框架迁移

### 6.1 框架选型与性能分析

在 uTools 的使用场景中，插件需要百毫秒级冷启动以达到"用完即走"的体验。

| 框架 | uTools 适配度 | 冷启动性能 | 迁移复杂度 | 关键注意事项 |
|------|-------------|---------|-----------|------------|
| **Svelte** | ⭐⭐⭐⭐⭐ | 极快 | 低 | 编译时优化，无虚拟 DOM，体积最小 |
| **Solid** | ⭐⭐⭐⭐⭐ | 极快 | 低 | 细粒度响应式，直接操作真实 DOM |
| **Vue 3** | ⭐⭐⭐⭐ | 快 | 低 | Tree-shaking 效果好，生态丰富 |
| **React** | ⭐⭐⭐⭐ | 中等 | 低 | 运行时体积大，注意 Tree-shaking |
| **Angular** | ⭐⭐⭐ | 较慢 | 高 | Zone.js 会劫持 Node.js 异步，需 Zone-less |

> **Svelte / Solid 特别说明**：由于无虚拟 DOM、体积极小，在 `mode: "list"` 列表
> 渲染场景下，帧率表现显著优于 React/Vue。优先推荐用于新插件开发。

### 6.2 通用迁移清单

```
✅ 路由：History → Hash（createWebHashHistory / HashRouter）
   或：抛弃路由，改用状态机做视图切换（更简洁）

✅ 存储：localStorage → utools.dbStorage / utools.db
   （详见第 9 节）

✅ 通知：new Notification() → window.utools.showNotification()

✅ 深色模式：@media prefers-color-scheme → utools.isDarkColors()
   （详见 6.3）

✅ 构建：base → './'（相对路径）

✅ 添加 utools/preload.ts + utools/plugin.json

✅ 接入 uTools 生命周期（onPluginEnter / onPluginOut）
```

### 6.3 深色主题正确接入方式

```typescript
// src/composables/useTheme.ts（Vue 示例，其他框架同理）

// ❌ 错误：Web 标准媒体查询在 uTools 中不够精准
// window.matchMedia('(prefers-color-scheme: dark)').matches

// ✅ 正确：使用 uTools 原生 API 获取宿主主题
export function useTheme() {
  const isDark = ref(false)

  const syncTheme = () => {
    isDark.value = window.utools?.isDarkColors() ?? false
    document.documentElement.classList.toggle('dark', isDark.value)
    // 注入 CSS 自定义属性
    document.documentElement.style.setProperty(
      '--bg-primary',
      isDark.value ? '#1a1a1a' : '#ffffff'
    )
  }

  onMounted(() => {
    syncTheme()
    // 监听主题变更（uTools 提供的事件）
    window.utools?.onPluginEnter(() => syncTheme())
  })

  return { isDark }
}
```

### 6.4 Vue 3 完整迁移示例

```typescript
// vite.config.ts（见 5.2，已覆盖）

// src/composables/useUTools.ts
import { ref, onMounted, onUnmounted } from 'vue'

interface EnterPayload {
  code: string
  type: 'text' | 'img' | 'files' | 'window' | 'regex' | 'over'
  payload: any
}

export function useUTools() {
  const enterPayload = ref<EnterPayload | null>(null)

  onMounted(() => {
    const stored = (window as any).__utools_enter__
    if (stored) enterPayload.value = stored
  })

  const setHeight = (h: number) => window.utools?.setExpendHeight(h)
  const notify    = (msg: string) => window.utools?.showNotification(msg)
  const hide      = () => window.utools?.hideMainWindow()
  const quit      = () => window.utools?.outPlugin()

  return { enterPayload, setHeight, notify, hide, quit }
}
```

```vue
<!-- src/App.vue -->
<script setup lang="ts">
import { computed } from 'vue'
import { useUTools } from './composables/useUTools'
import { useTheme } from './composables/useTheme'
import MainView from './views/MainView.vue'
import SearchView from './views/SearchView.vue'

const { enterPayload } = useUTools()
const { isDark } = useTheme()

const currentView = computed(() => enterPayload.value?.code ?? 'main')
</script>

<template>
  <div :class="['app', { dark: isDark }]">
    <SearchView v-if="currentView === 'search'" />
    <MainView v-else />
  </div>
</template>

<style>
body { margin: 0; overflow: hidden; }
.app { height: 100vh; }
</style>
```

### 6.5 React 迁移示例

```typescript
// src/hooks/useUTools.ts
import { useState, useEffect, useCallback, useRef } from 'react'

export function useUTools() {
  const [enterCode, setEnterCode] = useState('')
  const [enterPayload, setEnterPayload] = useState<any>(null)

  useEffect(() => {
    const stored = (window as any).__utools_enter__
    if (stored) {
      setEnterCode(stored.code)
      setEnterPayload(stored.payload)
    }
  }, [])

  const setHeight = useCallback((h: number) => {
    (window as any).utools?.setExpendHeight(h)
  }, [])

  // 内容区高度自适应
  const containerRef = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!containerRef.current) return
    const observer = new ResizeObserver(([entry]) => {
      setHeight(Math.ceil(entry.contentRect.height))
    })
    observer.observe(containerRef.current)
    return () => observer.disconnect()
  }, [setHeight])

  return { enterCode, enterPayload, setHeight, containerRef }
}
```

```tsx
// src/App.tsx
import { useUTools } from './hooks/useUTools'

export function App() {
  const { enterCode, containerRef } = useUTools()
  return (
    <div ref={containerRef}>
      {enterCode === 'search' ? <SearchPage /> : <MainPage />}
    </div>
  )
}
```

### 6.6 Angular 迁移关键点（Zone-less）

```typescript
// main.ts — Angular 必须用 Hash 路由 + 避免 Zone.js 劫持
import { bootstrapApplication } from '@angular/platform-browser'
import { AppComponent } from './app/app.component'
import { provideRouter, withHashLocation } from '@angular/router'

// ⚠️ Zone.js 会拦截 Node.js 的异步调用，导致内存泄漏
// 建议在 angular.json 中移除 "zone.js" polyfill，改用 Zone-less 模式
// 并在组件中手动 ChangeDetectorRef.markForCheck()

bootstrapApplication(AppComponent, {
  providers: [
    provideRouter(routes, withHashLocation()),
  ],
})
```

```typescript
// src/app/utools.service.ts
import { Injectable, NgZone } from '@angular/core'

@Injectable({ providedIn: 'root' })
export class UToolsService {
  constructor(private zone: NgZone) {}

  // 将 uTools 回调强制运行在 Angular Zone 内以触发变更检测
  onEnter(callback: (payload: any) => void) {
    ;(window as any).utools?.onPluginEnter((payload: any) => {
      this.zone.run(() => callback(payload))
    })
  }

  setHeight(h: number) { (window as any).utools?.setExpendHeight(h) }
}
```

### 6.7 Svelte 迁移示例

```typescript
// src/stores/utools.ts
import { writable, derived, get } from 'svelte/store'

const _enter = writable<any>(
  typeof window !== 'undefined' ? (window as any).__utools_enter__ : null
)

export const enterCode    = derived(_enter, $e => $e?.code    ?? 'main')
export const enterType    = derived(_enter, $e => $e?.type    ?? 'text')
export const enterPayload = derived(_enter, $e => $e?.payload ?? '')

export const utools = {
  setHeight: (h: number) => (window as any).utools?.setExpendHeight(h),
  notify:    (msg: string) => (window as any).utools?.showNotification(msg),
  hide:      () => (window as any).utools?.hideMainWindow(),
}
```

```svelte
<!-- App.svelte -->
<script lang="ts">
  import { enterCode, utools } from './stores/utools'
  import Main from './pages/Main.svelte'
  import Search from './pages/Search.svelte'
  import { onMount } from 'svelte'

  let container: HTMLElement
  onMount(() => {
    const ro = new ResizeObserver(([e]) =>
      utools.setHeight(Math.ceil(e.contentRect.height))
    )
    ro.observe(container)
    return () => ro.disconnect()
  })
</script>

<div bind:this={container}>
  {#if $enterCode === 'search'}
    <Search />
  {:else}
    <Main />
  {/if}
</div>
```

### 6.8 Solid.js 迁移示例

```typescript
// src/stores/utools.ts
import { createSignal } from 'solid-js'

const [enterPayload, setEnterPayload] = createSignal<any>(
  (window as any).__utools_enter__ ?? null
)

export { enterPayload }
export const enterCode = () => enterPayload()?.code ?? 'main'

export const setHeight = (h: number) =>
  (window as any).utools?.setExpendHeight(h)
```

```tsx
// src/App.tsx
import { Switch, Match, onMount } from 'solid-js'
import { enterCode, setHeight } from './stores/utools'

export function App() {
  let ref!: HTMLDivElement
  onMount(() => {
    const ro = new ResizeObserver(([e]) =>
      setHeight(Math.ceil(e.contentRect.height))
    )
    ro.observe(ref)
  })
  return (
    <div ref={ref}>
      <Switch fallback={<MainPage />}>
        <Match when={enterCode() === 'search'}>
          <SearchPage />
        </Match>
      </Switch>
    </div>
  )
}
```

---

## 7. Electron 应用 → uTools 降维迁移

### 7.1 核心架构变化

```
原 Electron 架构（双进程）：
┌─── 主进程 (Main Process) ──────────────────┐
│  app、BrowserWindow、Menu、Tray             │
│  ipcMain.handle('do-x', handler)           │
└───────────────────┬────────────────────────┘
                    │ IPC
┌─── 渲染进程 (Renderer) ────────────────────┐
│  ipcRenderer.invoke('do-x', args)          │
│  前端框架 UI                               │
└────────────────────────────────────────────┘

↓ 迁移后 uTools 架构（扁平化，去 IPC）

┌─── 渲染进程 ─────────────────────────────┐
│  window.preload.doX(args)   ← 直接调用   │
│  前端框架 UI                              │
└──────────────┬──────────────────────────┘
               │ window.preload.*（同进程）
┌─── utools/preload.ts ──────────────────────────┐
│  原主进程逻辑 → 移植到此处               │
│  const fs = require('fs')               │
│  window.preload.doX = (args) => ...     │
└─────────────────────────────────────────┘
```

> **性能红利**：去掉 IPC 跨进程序列化后，原本需要 5~50ms 的 IPC 往返
> 变为同进程直接调用，响应速度提升显著。

### 7.2 Electron API 完整映射表

| 原 Electron 能力 | uTools 替代方案 | 备注 |
|----------------|----------------|------|
| `app.getPath('home')` | `require('os').homedir()` (preload) | — |
| `app.getPath('userData')` | `window.utools.getPath('userData')` | — |
| `app.getPath('temp')` | `require('os').tmpdir()` (preload) | — |
| `app.quit()` | `window.utools.outPlugin()` | 退出插件 |
| `app.hide()` / `mainWin.hide()` | `window.utools.hideMainWindow()` | 隐藏到后台 |
| `BrowserWindow.setSize` | `window.utools.setExpendHeight(h)` | 仅高度可变 |
| `new BrowserWindow({...})` | `window.utools.createBrowserWindow(url, opts)` | 子窗口 |
| `dialog.showOpenDialog` | `window.utools.showOpenDialog({...})` | 参数基本兼容 |
| `dialog.showSaveDialog` | `window.utools.showSaveDialog({...})` | — |
| `dialog.showMessageBox` | `window.utools.showMessageBox({...})` | — |
| `Menu.buildFromTemplate` | 不支持 | 改为插件内自定义 UI |
| `Tray` | 不支持 | uTools 自身有 Tray 机制 |
| `ipcMain.handle(ch, fn)` | 移到 `utools/preload.ts` 命名导出 | 核心迁移动作 |
| `ipcRenderer.invoke(ch, args)` | `window.preload.ch(args)` | 直接调用 |
| `contextBridge.exposeInMainWorld` | 直接挂 `window.*`（uTools 已做沙箱） | — |
| `Notification` | `window.utools.showNotification(msg)` | — |
| `shell.openExternal` | `require('electron').shell.openExternal` (preload) | — |
| `autoUpdater` | 不支持（uTools 商店自动更新） | — |
| `electron-store` | `window.utools.dbStorage` / `utools.db` | 详见第 9 节 |

### 7.3 IPC 层迁移代码对照

```ts
// ── 原 Electron main.js ──
const { ipcMain, dialog } = require('electron')
const fs = require('fs')
const { execSync } = require('child_process')

ipcMain.handle('fs:read',   async (_e, path) => fs.readFileSync(path, 'utf-8'))
ipcMain.handle('fs:write',  async (_e, path, data) => fs.writeFileSync(path, data))
ipcMain.handle('dialog:open', async () => dialog.showOpenDialog({ properties: ['openFile'] }))
ipcMain.handle('exec',      async (_e, cmd) => execSync(cmd, { encoding: 'utf-8' }))
```

```ts
// ── 迁移后 uTools 源码：utools/preload.ts ──
import { execSync } from 'node:child_process'
import fs from 'node:fs'

/** ipcMain.handle('fs:read') → window.preload.fsRead() */
export function fsRead(path: string): string {
  return fs.readFileSync(path, 'utf-8')
}

/** ipcMain.handle('fs:write') → window.preload.fsWrite() */
export function fsWrite(path: string, data: string): void {
  fs.writeFileSync(path, data)
}

/** ipcMain.handle('dialog:open') → window.preload.dialogOpen() */
export function dialogOpen() {
  return window.utools.showOpenDialog({ properties: ['openFile'] })
}

/** ipcMain.handle('exec') → window.preload.exec() */
export function exec(cmd: string): string {
  return execSync(cmd, { encoding: 'utf-8' })
}
```

```typescript
// ── 原 Electron 渲染层 ──
import { ipcRenderer } from 'electron'

const content = await ipcRenderer.invoke('fs:read', '/path/to/file')
const { filePaths } = await ipcRenderer.invoke('dialog:open')
```

```typescript
// ── 迁移后 uTools 渲染层（直接调用，无 ipcRenderer）──
const content = window.preload.fsRead('/path/to/file')
const { filePaths } = await window.preload.dialogOpen()
```

### 7.4 多窗口迁移（BrowserWindow → createBrowserWindow）

```ts
// ── 原 Electron main.js ──
const win = new BrowserWindow({
  width: 800, height: 600,
  webPreferences: { preload: path.join(__dirname, 'preload.js') },
})
win.loadURL('https://example.com')

// ── 迁移后 uTools 渲染层 ──
// ⚠️ 关键：子窗口必须同样配置 preload，否则无法使用 Node.js 能力
window.utools.createBrowserWindow(
  'child.html',
  {
    width: 800, height: 600,
    // BrowserWindowConstructorOptions（大部分参数兼容 Electron 原生）
    webPreferences: {
      preload: window.preload.join(__dirname, 'preload.js'),
    },
  },
  () => { /* 窗口创建回调 */ }
)
```

### 7.5 主进程全局状态迁移

```ts
// ── 原主进程：全局状态存 JS 变量 ──
// let globalUser = null, globalConfig = {}

// ── 迁移后 uTools 源码：utools/preload.ts ──
// 会话内状态（插件关闭即清除）
const session = new Map<string, unknown>()

/** 读取会话状态，挂载为 window.preload.sessionGet()。 */
export function sessionGet(key: string): unknown {
  return session.get(key)
}

/** 写入会话状态，挂载为 window.preload.sessionSet()。 */
export function sessionSet(key: string, value: unknown): void {
  session.set(key, value)
}

/** 读取持久化配置。 */
export function configGet<T>(key: string): T | null {
  return window.utools.dbStorage.getItem(key) as T | null
}

/** 写入持久化配置。 */
export function configSet(key: string, value: unknown): void {
  window.utools.dbStorage.setItem(key, value)
}
```

---

## 8. Tauri 应用 → uTools 跨语言桥接

Tauri 迁移是最复杂的场景。前端 UI 代码几乎无需改动，
核心工作是将 Rust 后端命令在 `utools/preload.ts` 中用 Node.js/uTools API 重新实现，并通过命名导出挂载到 `window.preload`。

### 8.1 架构对比

```
Tauri 架构：
[WebView 前端]
    │ invoke('rust_command', args)
    ↓
[Tauri Core · Rust 后端]
    │ #[tauri::command] fn rust_command(args) { ... }
    ↓
[std::fs / std::process / Rust 生态]

↓ 迁移后 uTools 架构：

[Chromium 渲染层]
    │ window.preload.rustCommand(args)   ← 接口名保持一致
    ↓
[utools/preload.ts · TypeScript]
    │ import node:fs / node:child_process
    ↓
[系统 API / npm 生态]
```

### 8.2 Rust Command → Node.js 对照表

| Tauri Rust 能力 | Node.js/uTools 替代（utools/preload.ts） |
|----------------|--------------------------|
| `std::fs::read_to_string(path)` | `fs.readFileSync(path, 'utf-8')` |
| `std::fs::write(path, data)` | `fs.writeFileSync(path, data)` |
| `std::fs::read_dir(path)` | `fs.readdirSync(path, {withFileTypes:true})` |
| `std::fs::remove_file(path)` | `fs.unlinkSync(path)` |
| `std::process::Command::new("cmd")` | `child_process.execSync(cmd)` / `spawn()` |
| Rust 无畏并发（多线程）| `worker_threads`（防止阻塞主线程） |
| `tauri::api::dialog::open()` | `window.utools.showOpenDialog()` |
| `tauri::api::dialog::save()` | `window.utools.showSaveDialog()` |
| `tauri::api::shell::open(url)` | `shell.openExternal(url)` (electron) |
| `tauri::api::notification::send()` | `window.utools.showNotification()` |
| `tauri::api::http::fetch()` | 渲染层直接 `fetch()` |
| `tauri::api::path::home_dir()` | `os.homedir()` |
| `tauri::api::path::app_data_dir()` | `window.utools.getPath('userData')` |
| `tauri::api::clipboard::read_text()` | `clipboard.readText()` (electron) |
| `tauri::api::clipboard::write_text()` | `clipboard.writeText()` (electron) |
| `convertFileSrc(localPath)` | 直接返回 `'file://' + localPath` |

### 8.3 前端 invoke 迁移

```typescript
// ── 原 Tauri 前端（@tauri-apps/api）──
import { invoke }       from '@tauri-apps/api/tauri'
import { open }         from '@tauri-apps/api/dialog'
import { readTextFile } from '@tauri-apps/api/fs'
import { writeText }    from '@tauri-apps/api/clipboard'
import { convertFileSrc } from '@tauri-apps/api/tauri'

const content = await invoke<string>('read_file', { path: '/path/to/file' })
const selected = await open({ multiple: false })
const text = await readTextFile('/path/to/file')
await writeText('hello')
const src = convertFileSrc('/path/to/image.png')
```

```typescript
// ── 迁移后 uTools 渲染层 ──
// 方案A：直接替换调用（适合小项目）
const content = window.preload.readFile('/path/to/file')
const { filePaths } = await window.utools.showOpenDialog({ properties: ['openFile'] })
const selected = filePaths?.[0]
window.utools.copyText('hello')
const src = 'file://' + '/path/to/image.png'
```

### 8.4 方案B：`__TAURI_IPC__` 拦截（前端零改动）

> 此方案逆用 Tauri 官方测试 Mock 机制，通过拦截 `window.__TAURI_IPC__`，
> 将所有 `invoke()` 调用无感重定向到 `utools/preload.ts` 的 TypeScript 命名导出实现。
> **适合前端代码量大、不想批量修改 invoke 调用的项目。**

```ts
// utools/preload.ts — 在渲染层加载前注入拦截器

const fs = require('node:fs')
const { execSync } = require('node:child_process')
const os = require('node:os')

// 构造指令路由表（Rust command 名 → Node.js 实现）
const commandHandlers = {
  // 对应原 Rust #[tauri::command] fn read_file(path: String)
  'read_file': ({ path }) => {
    return fs.readFileSync(path, 'utf-8')
  },

  // 对应原 Rust #[tauri::command] fn write_file(path: String, content: String)
  'write_file': ({ path, content }) => {
    fs.writeFileSync(path, content, 'utf-8')
    return null
  },

  // 对应原 Rust #[tauri::command] fn exec_command(cmd: String)
  'exec_command': ({ cmd }) => {
    return execSync(cmd, { encoding: 'utf-8' })
  },

  // 对应 Tauri 窗口关闭
  'close_window': () => {
    window.utools.outPlugin()
    return null
  },

  // convertFileSrc 在 uTools 中直接用 file:// 协议
  'convert_file_src': ({ path }) => {
    return 'file://' + path
  },
}

// 拦截 Tauri IPC 通道
window.__TAURI_IPC__ = async (message) => {
  const { cmd, args = {} } = message
  const handler = commandHandlers[cmd]

  if (!handler) {
    console.warn(`[uTools-Tauri Bridge] 未实现的指令: ${cmd}`)
    throw new Error(`未实现的指令: ${cmd}`)
  }

  try {
    return handler(args)
  } catch (err) {
    throw new Error(`[${cmd}] ${err.message}`)
  }
}

// 模拟 convertFileSrc（前端代码不需要改）
window.__TAURI_INVOKE__ = window.__TAURI_IPC__
```

### 8.5 Tauri 安全沙箱重建（路径防御）

```ts
// utools/preload.ts — 重建等价于 Tauri Allowlist 的路径边界检查

const path = require('node:path')
const os = require('node:os')

// 允许访问的根目录白名单
const ALLOWED_ROOTS = [
  os.homedir(),
  window.utools.getPath('userData'),
  os.tmpdir(),
]

/**
 * 安全路径检查：防止目录穿越攻击（../../../etc/passwd）
 * 等价于 Tauri 的 fs allowlist
 */
function assertSafePath(targetPath) {
  // 1. 规范化路径，消除 .. 等
  const resolved = path.resolve(targetPath)

  // 2. 检查是否在白名单根目录内
  const isAllowed = ALLOWED_ROOTS.some(root => resolved.startsWith(root))

  if (!isAllowed) {
    throw new Error(
      `[安全] 路径越权：${resolved} 不在允许范围内\n` +
      `允许范围：${ALLOWED_ROOTS.join(', ')}`
    )
  }

  // 3. 检测路径穿越字符串
  if (targetPath.includes('..')) {
    throw new Error(`[安全] 路径包含穿越字符: ${targetPath}`)
  }

  return resolved
}

// 安全包装文件操作
// Compact mapping shape only; implement each property as a named export in utools/preload.ts.
const preloadMapping = {
  readFile: (p) => {
    const safe = assertSafePath(p)
    return require('node:fs').readFileSync(safe, 'utf-8')
  },
  writeFile: (p, content) => {
    const safe = assertSafePath(p)
    require('node:fs').writeFileSync(safe, content, 'utf-8')
  },
}
```

### 8.6 Tauri 事件系统迁移

```ts
// utools/preload.ts — 用 EventEmitter 替代 Tauri emit/listen

const { EventEmitter } = require('node:events')
const emitter = new EventEmitter()

// Compact mapping shape only; implement each property as a named export in utools/preload.ts.
const preloadMapping = {
  // 替代 tauri::api::event::emit()
  emit: (event, payload) => emitter.emit(event, payload),

  // 替代 listen()，返回取消函数
  listen: (event, handler) => {
    emitter.on(event, handler)
    return () => emitter.off(event, handler)  // unlisten
  },

  // 文件监听（替代 Tauri 的 watch 插件）
  watchFile: (filePath, callback) => {
    const watcher = require('node:fs').watch(filePath, callback)
    return () => watcher.close()  // 返回取消监听
  },
}
```

---

## 9. 数据持久化重构与云同步

### 9.1 存储方案对照表

| 原方案 | uTools 替代 | 特性 | 适用场景 |
|--------|------------|------|---------|
| `localStorage` | `utools.dbStorage` | 键值对，自动云同步 | 简单配置、用户偏好 |
| `sessionStorage` | JS 变量（内存） | 会话内有效 | 临时状态 |
| `electron-store` | `utools.dbStorage` + `utools.db` | 持久化，支持云同步 | 应用配置 |
| `indexedDB` | `utools.db`（CouchDB 风格） | 文档型，自动云同步 | 复杂结构数据 |
| `better-sqlite3` | `utools.db` 或重新编译 | 关系型 | 复杂查询需求（见第 10 节） |

### 9.2 统一存储封装（localStorage → utools.dbStorage）

```typescript
// src/utils/storage.ts
// 同一套 API 在浏览器和 uTools 中均可用

const isUTools = () => typeof window !== 'undefined' && 'utools' in window

export const storage = {
  get<T>(key: string, fallback?: T): T | undefined {
    if (isUTools()) {
      const val = window.utools.dbStorage.getItem(key)
      return val !== null ? (val as T) : fallback
    }
    const raw = localStorage.getItem(key)
    return raw !== null ? JSON.parse(raw) : fallback
  },

  set(key: string, value: unknown): void {
    if (isUTools()) {
      window.utools.dbStorage.setItem(key, value)
    } else {
      localStorage.setItem(key, JSON.stringify(value))
    }
  },

  remove(key: string): void {
    if (isUTools()) {
      window.utools.dbStorage.removeItem(key)
    } else {
      localStorage.removeItem(key)
    }
  },
}
```

### 9.3 utools.db 工程化封装（含 _rev 冲突处理）

```typescript
// src/utils/db.ts
// 封装 utools.db（类 CouchDB / PouchDB，支持自动云同步）

const PREFIX = 'myplugin:'  // 命名空间前缀，防止与其他插件冲突

type Doc<T> = { _id: string; _rev?: string; data: T }

export const db = {
  /** 读取文档 */
  get<T>(id: string): T | null {
    const doc = window.utools.db.get(`${PREFIX}${id}`) as Doc<T> | null
    return doc?.data ?? null
  },

  /**
   * 写入文档（自动处理 _rev 冲突）
   * ⚠️ utools.db.put 要求更新时必须携带最新 _rev，
   *    否则报版本冲突错误（类似 CouchDB 的 409 Conflict）
   */
  set<T>(id: string, data: T): boolean {
    const _id = `${PREFIX}${id}`
    const existing = window.utools.db.get(_id) as Doc<T> | null
    const doc: Doc<T> = existing
      ? { ...existing, data }    // 携带 _rev 进行更新
      : { _id, data }            // 新建文档
    const result = window.utools.db.put(doc)
    return result.ok
  },

  /** 删除文档 */
  remove(id: string): boolean {
    const existing = window.utools.db.get(`${PREFIX}${id}`)
    if (!existing) return false
    return window.utools.db.remove(existing).ok
  },

  /**
   * 前缀批量查询
   * _id 命名策略建议：使用语义路径，如 'settings/ui/theme'、'data/notes/2025'
   * 配合 allDocs 前缀查询，既支持细粒度同步，又能高效批量检索
   */
  getAll<T>(prefix: string): Array<{ id: string; data: T }> {
    const docs = window.utools.db.allDocs(`${PREFIX}${prefix}`) as Doc<T>[]
    return docs.map(doc => ({
      id: doc._id.replace(PREFIX, ''),
      data: doc.data,
    }))
  },

  /** 存储二进制附件（图片、文件等） */
  putAttachment(id: string, name: string, data: Uint8Array, mime: string) {
    return window.utools.db.putAttachment(`${PREFIX}${id}`, name, data, mime)
  },
}
```

### 9.4 大状态对象分拆策略（避免云同步冲突）

```typescript
// ❌ 错误：将所有配置堆在一个大文档 → 多端并发改写会引发大量版本冲突
db.set('config', {
  ui: { theme: 'dark', language: 'zh', fontSize: 14 },
  network: { proxy: '', timeout: 5000 },
  shortcuts: { /* 大量快捷键配置 */ },
})

// ✅ 正确：按语义维度拆分为细粒度文档 → 各自独立同步，互不干扰
db.set('config/ui/theme',    'dark')
db.set('config/ui/language', 'zh')
db.set('config/ui/fontSize', 14)
db.set('config/network',     { proxy: '', timeout: 5000 })
db.set('config/shortcuts/copy',  'Cmd+C')
db.set('config/shortcuts/paste', 'Cmd+V')

// 批量读取（前缀查询）
const uiConfigs = db.getAll('config/ui/')  // 一次拉取所有 UI 配置
```

---

## 10. 原生模块（Native Modules）ABI 重编译

### 10.1 问题根因

```
npm install better-sqlite3     ← 针对当前 Node.js 标准版本编译
        ↓
生成 better_sqlite3.node（.node 二进制文件，包含特定 ABI 版本号）

uTools 内置 Electron 的 Node.js 与标准 Node.js 的 ABI 不同：
- 原因：Electron 将 OpenSSL 替换为 Chromium 的 BoringSSL
- 表现：加载 .node 文件时报错 "Module did not self-register"
         或 "The module was compiled against a different Node.js version"
```

### 10.2 重编译方案

```bash
# 第一步：确认 uTools 内置的 Electron 版本
# （查阅 uTools 官方文档或通过插件内 process.versions.electron 获取）
ELECTRON_VERSION="29.0.0"   # 示例版本
NODE_VERSION="18.x"          # 对应 Node 版本

# 第二步：使用 node-gyp 针对 Electron 重新编译原生模块
npx electron-rebuild \
  --version $ELECTRON_VERSION \
  --module-dir ./node_modules/better-sqlite3

# 或者手动指定参数：
node-gyp rebuild \
  --target=$ELECTRON_VERSION \
  --arch=x64 \
  --dist-url=https://electronjs.org/headers \
  --module-name=better_sqlite3 \
  --module-path=./node_modules/better-sqlite3/build/Release
```

### 10.3 替代方案（推荐优先考虑）

| 原生模块 | 纯 JS/WASM 替代 | 说明 |
|---------|---------------|------|
| `better-sqlite3` | `sql.js`（WASM） | 无需编译，功能完整，性能略低 |
| `sharp`（图片处理） | `jimp`（纯 JS） | 功能基本等价 |
| `node-gyp` 编译模块 | 寻找对应 `.wasm` 版本 | WASM 跨平台兼容性好 |
| `ffi-napi`（调用 .dll） | 无等价方案 | 需重编译或放弃该功能 |

```typescript
// 使用 sql.js（WASM SQLite）替代 better-sqlite3
// utools/preload.ts
const initSqlJs = require('sql.js')  // 或 require('@jlongster/sql.js')

let _db = null

// Compact mapping shape only; implement each method as a named export in utools/preload.ts.
const preloadMapping = {
  async initDB(dbPath) {
    const SQL = await initSqlJs()
    const fs = require('node:fs')
    if (require('node:fs').existsSync(dbPath)) {
      const fileBuffer = fs.readFileSync(dbPath)
      _db = new SQL.Database(fileBuffer)
    } else {
      _db = new SQL.Database()
    }
    return true
  },

  query(sql, params = []) {
    if (!_db) throw new Error('DB not initialized')
    return _db.exec(sql, params)
  },

  run(sql, params = []) {
    if (!_db) throw new Error('DB not initialized')
    _db.run(sql, params)
    // 持久化到文件
    const data = _db.export()
    require('node:fs').writeFileSync(DB_PATH, Buffer.from(data))
  },
}
```

---

## 11. 通用工程化模式

### 11.1 完整生命周期管理

```ts
// utools/preload.ts — 生命周期全覆盖

let cleanupFns = []  // 收集所有需要清理的资源

window.utools.onPluginEnter(({ code, type, payload }) => {
  // type → payload 类型映射：
  // 'text'   → string（剪贴板/选中文本）
  // 'img'    → string（base64 图片数据）
  // 'files'  → Array<{ name, path, isFile, isDirectory }>
  // 'window' → { title, pid, app }（活跃窗口信息）
  // 'regex'  → string（正则匹配的文本）
  // 'over'   → string（超级面板划词内容）

  window.__utools_enter__ = { code, type, payload }

  // 基于 code 路由初始化逻辑
  if (code === 'watch-clipboard') {
    const timer = setInterval(() => {
      const text = require('electron').clipboard.readText()
      window.dispatchEvent(new CustomEvent('clipboard-change', { detail: text }))
    }, 500)
    cleanupFns.push(() => clearInterval(timer))
  }
})

window.utools.onPluginOut(() => {
  // 清理本次会话的所有资源
  cleanupFns.forEach(fn => fn())
  cleanupFns = []
  window.__utools_enter__ = null
})

window.utools.onPluginDetach(() => {
  // 插件被彻底卸载（uTools 退出或强制卸载），做最终清理
  // 例如：关闭数据库连接、保存未同步的数据
})
```

### 11.2 窗口高度自适应（ResizeObserver 方案）

```vue
<!-- src/components/AutoHeight.vue -->
<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'

const container = ref<HTMLElement>()

onMounted(() => {
  if (!container.value) return
  const observer = new ResizeObserver(([entry]) => {
    // setExpendHeight 设置内容区高度（不含 uTools 搜索框）
    window.utools?.setExpendHeight(Math.ceil(entry.contentRect.height))
  })
  observer.observe(container.value)
  onUnmounted(() => observer.disconnect())
})
</script>

<template>
  <div ref="container" style="overflow: hidden">
    <slot />
  </div>
</template>
```

### 11.3 AI Agent 工具对接（plugin.json tools + preload）

```ts
// utools/preload.ts — 实现 plugin.json 中声明的 AI Tools

// uTools 会调用这些 handler 来响应 AI Agent 的工具调用
window.utools.onToolCall(async (toolName, input) => {
  switch (toolName) {
    case 'read_local_file': {
      const { path } = input
      const content = require('node:fs').readFileSync(path, 'utf-8')
      return { content }
    }
    case 'list_directory': {
      const { path } = input
      const entries = require('node:fs').readdirSync(path, { withFileTypes: true })
      return {
        files: entries.map(e => ({ name: e.name, isDir: e.isDirectory() }))
      }
    }
    default:
      throw new Error(`未知工具: ${toolName}`)
  }
})
```

### 11.4 错误处理与日志

```typescript
// src/utils/logger.ts

type Level = 'debug' | 'info' | 'warn' | 'error'

const isUTools = () => 'utools' in window

export const log = (level: Level, message: string, data?: unknown) => {
  const prefix = `[Plugin][${level.toUpperCase()}]`
  console[level](prefix, message, data ?? '')

  // 可选：持久化错误日志到 utools.db（方便用户反馈问题）
  if (level === 'error' && isUTools()) {
    const errLog = {
      time: new Date().toISOString(),
      message,
      data: String(data),
    }
    const existing = window.utools.db.get('__error_log__') as any
    const logs = existing?.data ?? []
    logs.unshift(errLog)
    window.utools.db.put({
      ...(existing ?? { _id: '__error_log__' }),
      data: logs.slice(0, 50),  // 最多保留 50 条
    })
  }
}
```

---

## 12. 常见陷阱与解决方案

### ❌ 陷阱 1：把生成物规则误套到 TypeScript 源码

```ts
// ❌ 错误：把源码写成手工 window 挂载，绕过 @ver5 的导出分析与 mock 生成
const { readFileSync } = require('fs')
window.preload = { readFile: readFileSync }

// ✅ 正确：utools/preload.ts 用 TypeScript 命名导出
import { readFileSync } from 'node:fs'
export const readFile = (path: string) => readFileSync(path, 'utf-8')
```

### ❌ 陷阱 2：渲染层 require

```ts
// ❌ 错误：渲染层是浏览器环境，没有 require
const fs = require('fs')  // ReferenceError

// ✅ 正确：只在 utools/preload.ts 中导入 Node API，通过命名导出暴露
// utools/preload.ts: export const readFile = (p: string) => readFileSync(p, 'utf-8')
// 渲染层:    window.preload.readFile('/path')
```

### ❌ 陷阱 3：History 路由白屏

```typescript
// ❌ 错误：uTools 本地文件加载，History 路由深层跳转导致资源 404
createRouter({ history: createWebHistory() })

// ✅ 正确
createRouter({ history: createWebHashHistory() })
// 或：用状态机替代路由（推荐）
```

### ❌ 陷阱 4：调用不存在的主进程 API

```ts
// ❌ 错误：主进程 API 在 preload 中不可用（运行时崩溃）
const { BrowserWindow, app } = require('electron')  // 报错

// ✅ 正确：只使用渲染进程 API 子集
const { clipboard, shell } = require('electron')
// 其他功能通过 window.utools.* 替代
```

### ❌ 阱阱 5：preload 中事件监听泄漏

```ts
// ❌ 错误：每次进入插件都添加新监听器，永不清除
window.utools.onPluginEnter(() => {
  document.addEventListener('keydown', handler)  // 越积越多！
})

// ✅ 正确：在 onPluginOut 中配套清理
let _keyHandler = null
window.utools.onPluginEnter(() => {
  _keyHandler = (e) => { /* ... */ }
  document.addEventListener('keydown', _keyHandler)
})
window.utools.onPluginOut(() => {
  if (_keyHandler) {
    document.removeEventListener('keydown', _keyHandler)
    _keyHandler = null
  }
})
```

### ❌ 陷阱 6：utools.db.put 版本冲突

```ts
// ❌ 错误：更新时不携带 _rev，触发 409 冲突
window.utools.db.put({ _id: 'my-doc', data: 'new' })

// ✅ 正确：先 get 取出 _rev，再 put
const existing = window.utools.db.get('my-doc')
if (existing) {
  window.utools.db.put({ ...existing, data: 'new' })  // 带 _rev 更新
} else {
  window.utools.db.put({ _id: 'my-doc', data: 'new' })  // 新建
}
```

### ❌ 陷阱 7：Angular Zone.js 劫持 Node.js 异步

```typescript
// ❌ 问题：Zone.js 拦截 Node.js 的异步宏任务，导致内存泄漏
// Zone.js 会劫持 preload.ts 命名导出暴露的基于 Node 的异步 API

// ✅ 解决方案 A：Zone-less 模式（推荐）
// angular.json 中移除 "zone.js" polyfill

// ✅ 解决方案 B：对特定异步调用使用 NgZone.runOutsideAngular
class MyService {
  constructor(private zone: NgZone) {}

  watchFile(path: string, callback: () => void) {
    // Node.js 文件监听在 Zone 外运行，避免被 Zone.js 拦截
    this.zone.runOutsideAngular(() => {
      window.preload.watchFile(path, () => {
        // 需要更新视图时，再进入 Zone
        this.zone.run(callback)
      })
    })
  }
}
```

### ❌ 陷阱 8：Tauri 路径安全漏洞

```ts
// ❌ 危险：直接把用户输入的路径传给 fs，可能被利用做路径穿越攻击
window.__TAURI_IPC__ = async ({ cmd, args }) => {
  if (cmd === 'read_file') {
    return fs.readFileSync(args.path, 'utf-8')  // ← 危险！
  }
}

// ✅ 安全：必须对路径做白名单校验（见第 8.5 节 assertSafePath）
window.__TAURI_IPC__ = async ({ cmd, args }) => {
  if (cmd === 'read_file') {
    const safePath = assertSafePath(args.path)  // 白名单 + 穿越检测
    return fs.readFileSync(safePath, 'utf-8')
  }
}
```

---

## 参考资源

| 资源 | 地址 |
|------|------|
| uTools 官方开发者文档 | https://u.tools/docs/developer/ |
| plugin.json 配置说明 | https://www.u-tools.cn/docs/developer/information/plugin-json.html |
| preload.js 说明 | https://u.tools/docs/developer/information/preload-js/preload-js.html |
| utools-api-types（TS 类型定义） | https://github.com/uTools-Labs/utools-api-types |
| **@ver5/vite-plugin-utools（推荐构建工具）** | https://github.com/uxiew/vite-plugin-utools |
| utools-plugins（示例插件集合） | https://github.com/uxiew/utools-plugins |
| Tauri 官方测试 Mock 文档 | https://tauri.app/v1/guides/testing/mocking |

## 关联参考文件

本文档与以下 `references/` 文件配套使用：

- `references/plugin-json-schema.md` — plugin.json 字段完整 Schema 说明
- `references/utools-api-cheatsheet.md` — uTools API 速查手册
- `references/framework-quirks.md` — 各框架适配细节与怪异行为记录
- `references/native-module-recompile.md` — 原生模块 ABI 重编译详细步骤
- `references/tauri-command-mapping.md` — Tauri Rust Command 完整映射表
