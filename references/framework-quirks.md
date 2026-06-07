# 框架适配怪异行为记录（framework-quirks）

> 记录各前端框架在 uTools 容器内的非标准行为、已知 Bug 与最佳规避方案。
> 持续更新，欢迎补充。

---

## 目录

1. [通用怪异行为](#1-通用怪异行为)
2. [Vue 3](#2-vue-3)
3. [React](#3-react)
4. [Angular](#4-angular)
5. [Svelte](#5-svelte)
6. [Solid.js](#6-solidjs)
7. [CSS / 样式相关](#7-css--样式相关)

---

## 1. 通用怪异行为

### 1.1 `window.utools` 在框架初始化前可能未就绪

**现象**：在组件顶层（模块作用域）直接读取 `window.utools` 某些属性，偶发 `undefined`。

**原因**：uTools 的 preload 注入是异步完成的，极端情况下框架已开始解析模块但 `window.utools` 尚未完全就绪。

```typescript
// ❌ 危险：模块顶层立即读取
const isDark = window.utools.isDarkColors()  // 偶发 undefined

// ✅ 安全：在生命周期内读取
onMounted(() => {
  const isDark = window.utools?.isDarkColors() ?? false
})
```

---

### 1.2 `file://` 协议下 `fetch()` 跨域限制

**现象**：在渲染层用 `fetch('/api/...')` 请求本地 JSON 文件报 CORS 错误。

**原因**：`file://` 协议不支持相对路径 fetch，且 Chromium 对 `file://` → `file://` 有跨域限制。

```typescript
// ❌ 错误
const data = await fetch('/config/settings.json').then(r => r.json())

// ✅ 方案 A：在 preload.js 中用 fs 读取
window.preload.readJSON = (p) =>
  JSON.parse(require('fs').readFileSync(p, 'utf-8'))

// 渲染层：
const pluginPath = window.utools.getPluginPath()
const data = window.preload.readJSON(`${pluginPath}/config/settings.json`)

// ✅ 方案 B：将静态 JSON 数据打包进 JS bundle（import 语句）
import settings from './config/settings.json'  // Vite 直接支持
```

---

### 1.3 `localStorage` 数据不跨设备同步

**现象**：用 `localStorage` 存储的配置在另一台设备的同款插件中读不到。

**原因**：`localStorage` 是纯本地浏览器存储，uTools 没有同步机制。

```typescript
// ❌ 不同步
localStorage.setItem('theme', 'dark')

// ✅ 同步（uTools 云同步）
window.utools.dbStorage.setItem('theme', 'dark')
```

---

### 1.4 `window.location` 和 `history` API 行为异常

**现象**：`window.location.href` 值为 `file:///path/to/plugin/index.html`，
调用 `history.pushState()` 不会触发路由变化，或触发后刷新白屏。

**原因**：uTools 基于本地文件协议加载，没有 Web 服务器支持。

```typescript
// ❌ History 路由在 uTools 中不可靠
createRouter({ history: createWebHistory() })

// ✅ Hash 路由（URL 变化只改变锚点，不重新加载文件）
createRouter({ history: createWebHashHistory() })

// ✅ 最优：不使用路由，改用状态机
const view = ref<'main' | 'detail' | 'settings'>('main')
```

---

### 1.5 `ResizeObserver` 回调触发频率过高

**现象**：窗口高度抖动，`setExpendHeight` 被高频调用导致窗口闪烁。

**原因**：某些 CSS 动画或 transition 会导致 `ResizeObserver` 每帧触发。

```typescript
// ❌ 直接同步调用，每次 resize 都触发
const ro = new ResizeObserver(([e]) => {
  window.utools.setExpendHeight(e.contentRect.height)
})

// ✅ 用 requestAnimationFrame 节流
let rafId = 0
const ro = new ResizeObserver(([e]) => {
  cancelAnimationFrame(rafId)
  rafId = requestAnimationFrame(() => {
    window.utools.setExpendHeight(Math.ceil(e.contentRect.height))
  })
})
```

---

## 2. Vue 3

### 2.1 `<KeepAlive>` 与 uTools 生命周期冲突

**现象**：使用 `<KeepAlive>` 缓存组件时，`onActivated` / `onDeactivated` 的触发时机与
uTools 的 `onPluginEnter` / `onPluginOut` 不对齐，导致数据重复请求或状态不一致。

**原因**：uTools 的生命周期钩子在 `preload.js` 层注册，与 Vue 的组件激活周期相互独立。

```typescript
// ❌ 问题：onActivated 在插件首次加载时不触发（只有 onMounted 触发）
onActivated(() => {
  fetchLatestData()  // 可能漏掉首次加载
})

// ✅ 方案：用 provide/inject + 自定义事件桥接 uTools 生命周期
// main.ts
const app = createApp(App)
app.provide('utoolsEnter', ref(null))

// preload.js
window.utools.onPluginEnter((payload) => {
  window.dispatchEvent(new CustomEvent('utools:enter', { detail: payload }))
})

// 组件内
const payload = inject('utoolsEnter')
onMounted(() => {
  window.addEventListener('utools:enter', (e: CustomEvent) => {
    payload.value = e.detail
    fetchLatestData()
  })
})
```

---

### 2.2 Pinia 状态在插件重新进入后残留

**现象**：用户首次进入插件使用功能 A，退出后再进入，Pinia 中功能 A 的搜索结果还在。

**原因**：uTools 默认复用插件进程，不会重新初始化 JS 环境。

```typescript
// stores/search.ts
export const useSearchStore = defineStore('search', () => {
  const results = ref([])
  const keyword = ref('')

  // 在 uTools 进入事件时重置状态
  onMounted(() => {
    window.addEventListener('utools:enter', () => {
      results.value = []
      keyword.value = ''
    })
  })

  return { results, keyword }
})
```

---

### 2.3 Vue Router `scrollBehavior` 在 uTools 中无效

**现象**：配置了滚动行为，路由切换后页面不滚动到顶部。

**原因**：uTools 插件窗口的滚动容器不是 `window`，而是插件根 DOM 元素。

```typescript
// ❌ 标准 Web 的滚动恢复
createRouter({
  scrollBehavior: () => ({ top: 0 })  // 对 uTools 无效
})

// ✅ 手动在路由守卫中控制
router.afterEach(() => {
  document.getElementById('app')?.scrollTo(0, 0)
})
```

---

### 2.4 `v-model` 输入框在 macOS 下中文输入法冲突

**现象**：使用拼音输入法时，每敲一个拼音字母就触发 `input` 事件，导致实时搜索
过度请求。（非 uTools 特有，但在插件的紧凑 UI 中更明显）

```typescript
// ✅ 用 compositionstart / compositionend 屏蔽输入法过程中的事件
const isComposing = ref(false)

const handleInput = (e: Event) => {
  if (isComposing.value) return
  keyword.value = (e.target as HTMLInputElement).value
  doSearch()
}
```

---

## 3. React

### 3.1 `StrictMode` 导致 `onPluginEnter` 执行两次

**现象**：开发模式下，插件进入时执行了两次初始化逻辑（如发了两次请求）。

**原因**：React 18 StrictMode 在开发态会故意双重调用 `useEffect`，而 `onPluginEnter`
在 preload 中注册，不受 React 控制，两次 `useEffect` 会读取同一个 `__utools_enter__`。

```tsx
// ❌ 开发模式下 useEffect 被调用两次
useEffect(() => {
  const payload = (window as any).__utools_enter__
  if (payload) fetchData(payload)
}, [])

// ✅ 方案 A：去掉 StrictMode（仅限 uTools 开发）
// index.tsx: ReactDOM.createRoot(...).render(<App />) 不包 StrictMode

// ✅ 方案 B：用 ref 防止重复执行
const initialized = useRef(false)
useEffect(() => {
  if (initialized.current) return
  initialized.current = true
  const payload = (window as any).__utools_enter__
  if (payload) fetchData(payload)
}, [])
```

---

### 3.2 `useLayoutEffect` 在 SSR 警告

**现象**：控制台报 `Warning: useLayoutEffect does nothing on the server`（虽然 uTools
不是 SSR，但某些库会引入这个警告）。

```typescript
// 安全替换（uTools 永远是客户端环境）
const useIsomorphicLayoutEffect =
  typeof window !== 'undefined' ? useLayoutEffect : useEffect
```

---

### 3.3 React DevTools 无法连接

**现象**：安装了 React DevTools 浏览器扩展，但在 uTools 插件里无法使用。

**原因**：uTools 的 Chromium 不加载浏览器扩展。

**替代方案**：使用 Standalone React DevTools。

```bash
# 安装独立版 React DevTools
npm install -g react-devtools

# 启动（在插件加载前启动）
react-devtools

# 在 index.html 中临时添加连接脚本（仅开发态）
# <script src="http://localhost:8097"></script>
```

---

## 4. Angular

### 4.1 Zone.js 劫持 Node.js 异步导致内存泄漏

**现象**：插件运行一段时间后越来越卡，内存持续增长。

**原因**：Zone.js 会 patch 全局的 `setTimeout`、`Promise`、`EventEmitter` 等，
包括 `preload.js` 中 Node.js 暴露的异步 API，从而在 Angular 的变更检测周期内
积累大量待处理的微任务。

```typescript
// ✅ 方案 A：Zone-less 模式（Angular 17+，推荐）
// angular.json polyfills 中移除 "zone.js"

// main.ts
bootstrapApplication(AppComponent, {
  providers: [
    provideZonelessChangeDetection()  // Angular 18+ API
  ]
})

// ✅ 方案 B：NgZone.runOutsideAngular 隔离 Node.js 回调
@Injectable({ providedIn: 'root' })
class FileWatchService {
  private watcher: any = null

  constructor(private zone: NgZone) {}

  watch(path: string, callback: () => void) {
    // 在 Zone 外运行，防止 Zone.js 拦截 fs.watch 的回调
    this.zone.runOutsideAngular(() => {
      this.watcher = window.preload.watchFile(path, () => {
        // 需要触发 UI 更新时，显式进入 Zone
        this.zone.run(() => callback())
      })
    })
  }

  unwatch() {
    this.watcher?.()  // 调用返回的取消函数
  }
}
```

---

### 4.2 `HttpClient` 在 `file://` 协议下失败

**现象**：使用 `HttpClient` 发起请求时报跨域错误或 URL 解析错误。

**原因**：Angular `HttpClient` 默认使用 `XMLHttpRequest`，在 `file://` 协议下受限。

```typescript
// ❌ 错误：HttpClient 在 file:// 下请求本地文件
this.http.get('/assets/data.json').subscribe(...)

// ✅ 方案 A：静态数据用 import 打包
import data from '../assets/data.json'

// ✅ 方案 B：通过 preload 读取
@Injectable({ providedIn: 'root' })
class DataService {
  readJson(path: string): any {
    return JSON.parse(window.preload.readFile(path))
  }
}

// ✅ 方案 C：远程 API 用 fetch（比 HttpClient 在 uTools 中更可靠）
const data = await fetch('https://api.example.com/data').then(r => r.json())
```

---

### 4.3 `Router` 默认 `PathLocationStrategy` 白屏

```typescript
// ❌ 默认策略：HTML5 History，uTools 白屏
RouterModule.forRoot(routes)

// ✅ 改用 Hash 策略
RouterModule.forRoot(routes, { useHash: true })

// 或在 standalone app 中：
provideRouter(routes, withHashLocation())
```

---

## 5. Svelte

### 5.1 `onDestroy` 与 `onPluginOut` 不等价

**现象**：在 `onDestroy` 中清理资源，但实际上 uTools 隐藏插件（`onPluginOut`）时
并不会销毁 Svelte 组件，`onDestroy` 不触发。

**原因**：uTools 复用渲染进程，只有整个插件被卸载（`onPluginDetach`）时组件才销毁。

```typescript
// ❌ onDestroy 不在 onPluginOut 时触发
onDestroy(() => {
  clearInterval(timer)  // 此时 timer 可能仍在跑
})

// ✅ 监听 uTools 事件
import { onMount } from 'svelte'

onMount(() => {
  const handler = () => clearInterval(timer)
  window.addEventListener('utools:out', handler)
  return () => window.removeEventListener('utools:out', handler)
})

// preload.js 中发出事件
window.utools.onPluginOut(() => {
  window.dispatchEvent(new CustomEvent('utools:out'))
})
```

---

### 5.2 Svelte Store 持久化注意事项

**现象**：使用 `svelte-local-storage-store` 等库，数据不跨设备同步。

```typescript
// ❌ 基于 localStorage 的 store，不同步
import { localStorageStore } from 'svelte-local-storage-store'
const theme = localStorageStore('theme', 'light')

// ✅ 自定义 uTools DB store
import { writable } from 'svelte/store'

function utoolsStore<T>(key: string, defaultValue: T) {
  // 初始值从 utools.dbStorage 读取
  const stored = window.utools?.dbStorage.getItem(key) ?? defaultValue
  const { subscribe, set, update } = writable<T>(stored as T)

  return {
    subscribe,
    set: (value: T) => {
      window.utools?.dbStorage.setItem(key, value)
      set(value)
    },
    update,
  }
}

const theme = utoolsStore('theme', 'light')
```

---

## 6. Solid.js

### 6.1 `createEffect` 在 `window.utools` 未就绪前执行

**现象**：`createEffect` 比 `onMount` 更早执行，可能在 uTools API 就绪前调用。

```typescript
// ❌ createEffect 可能在 utools 初始化前跑
createEffect(() => {
  const dark = window.utools.isDarkColors()  // TypeError: cannot read property
  setIsDark(dark)
})

// ✅ 用 onMount 确保 DOM 和 preload 都已就绪
onMount(() => {
  setIsDark(window.utools?.isDarkColors() ?? false)
})
```

---

### 6.2 Solid Router `<Navigate>` 在 `file://` 协议下失效

```tsx
// ❌ 默认 History 路由
import { Router, Route } from '@solidjs/router'
<Router>...</Router>

// ✅ 使用 HashRouter
import { HashRouter, Route } from '@solidjs/router'
<HashRouter>
  <Route path="/" component={Main} />
  <Route path="/search" component={Search} />
</HashRouter>
```

---

## 7. CSS / 样式相关

### 7.1 `body` 默认 margin 导致内容区偏移

**现象**：插件内容与窗口边缘有 8px 空白。

```css
/* ✅ 重置 body margin（所有插件必做）*/
* { box-sizing: border-box; }
body { margin: 0; padding: 0; overflow: hidden; }
#app { height: 100vh; }
```

---

### 7.2 滚动条在 macOS 和 Windows 表现不一致

**现象**：macOS 滚动条悬浮覆盖内容，Windows 滚动条占据布局空间（约 17px）。

```css
/* ✅ 统一滚动条样式 */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb {
  background: rgba(128, 128, 128, 0.4);
  border-radius: 3px;
}
::-webkit-scrollbar-thumb:hover {
  background: rgba(128, 128, 128, 0.7);
}
```

---

### 7.3 `@font-face` 本地字体加载失败

**现象**：在 CSS 中引用本地字体文件，`file://` 协议下 Chromium 拒绝加载。

```css
/* ❌ 相对路径字体在 file:// 下可能被拒绝 */
@font-face {
  font-family: 'MyFont';
  src: url('./fonts/MyFont.woff2');
}

/* ✅ 方案 A：将字体转为 Base64 内联 */
@font-face {
  font-family: 'MyFont';
  src: url('data:font/woff2;base64,…');
}

/* ✅ 方案 B：使用系统字体栈（最推荐，无需加载，渲染快）*/
body {
  font-family:
    -apple-system, BlinkMacSystemFont,
    'Segoe UI', 'PingFang SC', 'Microsoft YaHei',
    sans-serif;
}
```

---

### 7.4 `transition` / `animation` 导致 setExpendHeight 抖动

**现象**：内容区高度变化时加了 CSS transition，导致 ResizeObserver 频繁回调，
窗口高度在动画过程中持续变化，体验差。

```css
/* ❌ 对高度加过渡 */
.content { transition: height 0.3s ease; }

/* ✅ 改用 max-height 过渡（或只对内部元素加动画，不影响容器高度）*/
.content { overflow: hidden; }
.content-inner { transition: transform 0.3s ease, opacity 0.3s ease; }
```

---

### 7.5 深色模式 CSS 变量与 uTools 原生面板不对齐

**现象**：插件内的白色背景在深色模式下与 uTools 深色搜索框形成突兀对比。

```css
/* ✅ 配合 utools.isDarkColors() 动态注入 CSS 变量 */
:root {
  --bg-primary: #ffffff;
  --bg-secondary: #f5f5f5;
  --text-primary: #1a1a1a;
  --border-color: rgba(0, 0, 0, 0.1);
}

:root.dark {
  --bg-primary: #1e1e1e;   /* 对齐 uTools 深色面板背景 */
  --bg-secondary: #2a2a2a;
  --text-primary: #e8e8e8;
  --border-color: rgba(255, 255, 255, 0.1);
}
```

```typescript
// 在应用初始化时同步主题
const applyTheme = () => {
  const isDark = window.utools?.isDarkColors() ?? false
  document.documentElement.classList.toggle('dark', isDark)
}

// 首次
applyTheme()

// 每次进入插件时同步（用户可能在插件运行期间切换系统主题）
window.utools?.onPluginEnter(() => applyTheme())
```
