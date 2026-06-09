# 原生模块 ABI 重编译详细指南

> 当 `utools/preload.ts` 引入或调用原生模块后，生成的 `dist/preload.js` 报
> `Module did not self-register` 或 `NODE_MODULE_VERSION mismatch` 时，
> 使用本指南进行重编译。

---

## 目录

1. [为什么会 ABI 不兼容](#1-为什么会-abi-不兼容)
2. [确认 uTools 目标版本](#2-确认-utools-目标版本)
3. [重编译流程（electron-rebuild）](#3-重编译流程electron-rebuild)
4. [重编译流程（手动 node-gyp）](#4-重编译流程手动-node-gyp)
5. [各平台注意事项](#5-各平台注意事项)
6. [常见错误排查](#6-常见错误排查)
7. [推荐的纯 JS/WASM 替代方案](#7-推荐的纯-jswasm-替代方案)
8. [自动化脚本示例](#8-自动化脚本示例)

---

## 1. 为什么会 ABI 不兼容

```
标准 Node.js 18.x
    ↓ 编译原生模块（.node 文件）
    → 生成：ABI version = 108（举例）
    → 使用：OpenSSL 3.x

uTools 内置 Electron（例如 Electron 29）
    → 对应 Node.js：18.x（版本号相同！）
    → 但 ABI version = 121（不同！）
    → 原因：Electron 用 BoringSSL 替换了 OpenSSL
            并打了若干 V8 私有补丁，导致 ABI 版本号不同

结论：
  即使 Node.js 版本号相同，Electron 的 ABI != 标准 Node.js 的 ABI
  → npm install 下载的 .node 文件无法在 uTools 内加载
```

---

## 2. 确认 uTools 目标版本

**方法 A：在插件内打印**（最准确）

```ts
// utools/preload.ts 中临时添加；通过命名导出挂载为 window.preload.logRuntimeVersions()
export function logRuntimeVersions(): void {
console.log({
  node:     process.version,               // e.g. "v18.17.0"
  electron: process.versions.electron,     // e.g. "29.0.0"
  abi:      process.versions.modules,      // e.g. "121"
  chrome:   process.versions.chrome,       // e.g. "120.0.6099.291"
  v8:       process.versions.v8,
})
}
```

**方法 B：查阅官方文档 / 更新日志**

uTools 官方通常在更新日志中注明基础 Electron 版本：
- 官网：https://www.u-tools.cn/changelog.html
- 每次 uTools 大版本升级可能变更 Electron 版本

---

## 3. 重编译流程（electron-rebuild，推荐）

```bash
# 第一步：安装 @electron/rebuild
npm install --save-dev @electron/rebuild
# 或
npm install -g @electron/rebuild

# 第二步：设置目标 Electron 版本（从第 2 节获取）
ELECTRON_VERSION="29.0.0"   # 替换为实际版本

# 第三步：重编译项目内所有原生模块
npx electron-rebuild \
  --version "$ELECTRON_VERSION" \
  --arch x64 \
  --module-dir ./node_modules

# 或只重编译特定模块
npx electron-rebuild \
  --version "$ELECTRON_VERSION" \
  --arch x64 \
  --only better-sqlite3 \
  --module-dir ./node_modules

# 第四步：验证编译结果
node -e "
const { createRequire } = require('module');
// 临时模拟 uTools Node 环境（粗略验证）
const db = require('./node_modules/better-sqlite3')('test.db');
db.prepare('SELECT 1').get();
console.log('✅ 编译成功');
db.close();
"
```

---

## 4. 重编译流程（手动 node-gyp）

当 `electron-rebuild` 失败或需要更细粒度控制时使用。

```bash
# 第一步：安装构建工具
npm install -g node-gyp

# macOS 需要 Xcode Command Line Tools
xcode-select --install

# Windows 需要（选其一）：
npm install -g windows-build-tools    # 旧方案
# 或安装 Visual Studio Build Tools 2022（新方案）

# 第二步：下载 Electron 头文件
ELECTRON_VERSION="29.0.0"
node-gyp configure \
  --target="$ELECTRON_VERSION" \
  --arch=x64 \
  --dist-url=https://electronjs.org/headers \
  --module-name=better_sqlite3 \
  --module-path=./node_modules/better-sqlite3

# 第三步：执行编译
cd node_modules/better-sqlite3
node-gyp rebuild \
  --target="$ELECTRON_VERSION" \
  --arch=x64 \
  --dist-url=https://electronjs.org/headers

# 第四步：确认产物位置
ls build/Release/*.node
# 应该看到 better_sqlite3.node
```

---

## 5. 各平台注意事项

### macOS

```bash
# Intel Mac (x64)
--arch x64

# Apple Silicon (M1/M2/M3)
--arch arm64

# 同时支持两种架构（Universal Binary）
npx electron-rebuild --version "$ELECTRON_VERSION" --arch universal

# 确认当前架构
uname -m
# x86_64 → x64
# arm64  → arm64
```

```bash
# macOS 上如果报 python3 找不到
brew install python3
npm config set python python3
```

---

### Windows

```powershell
# 检查 Visual Studio 构建工具是否安装
npm config get msvs_version

# 指定 VS 版本
npx electron-rebuild --version "29.0.0" --arch x64 ^
  --msvs_version 2022

# 如果报找不到 python
npm config set python C:\Python311\python.exe
```

---

### Linux

```bash
# 安装构建依赖
sudo apt-get install build-essential libssl-dev
# 或 (RedHat/CentOS)
sudo yum groupinstall "Development Tools"

# 编译
npx electron-rebuild --version "$ELECTRON_VERSION" --arch x64
```

---

## 6. 常见错误排查

### 错误：`Module did not self-register`

```
Error: Module did not self-register:
'/path/to/better_sqlite3.node'
```

**原因**：.node 文件编译时的 ABI 版本与当前 Electron 不匹配。

**解决**：按第 3 节步骤重编译，确认 `--version` 与实际 uTools 的 Electron 版本一致。

---

### 错误：`NODE_MODULE_VERSION mismatch`

```
Error: The module '.../better_sqlite3.node'
was compiled against a different Node.js version using
NODE_MODULE_VERSION X. This version of Node.js requires
NODE_MODULE_VERSION Y.
```

**解决**：同上，重编译时指定正确的 `--version`。

---

### 错误：`gyp: No Xcode or CLT version detected`（macOS）

```bash
# 重置 Xcode Command Line Tools
sudo rm -rf /Library/Developer/CommandLineTools
xcode-select --install

# 如果还报错
sudo xcode-select --switch /Library/Developer/CommandLineTools
```

---

### 错误：`MSBUILD : error MSB3428` （Windows）

```powershell
# 重新安装构建工具
npm install -g --production windows-build-tools
# 或安装最新 Visual Studio Build Tools 2022（手动）

# 然后重新编译
npx electron-rebuild --version "29.0.0" --arch x64
```

---

### 错误：编译成功但 uTools 内仍崩溃

可能原因：
1. **多份 .node 文件**：项目中有多个版本的 native 模块（npm workspaces、pnpm 软链接等）
2. **preload.ts 中导入/加载路径错误**：确认路径指向重编译后的版本，且生成的 `dist/preload.js` 能解析到同一份 `.node`
3. **arch 不匹配**：macOS 上 x64/arm64 混用

```ts
// utools/preload.ts 调试：打印实际加载的 .node 文件路径
import Module from 'node:module'

const orig = Module._resolveFilename.bind(Module)
Module._resolveFilename = function(request, ...args) {
  const result = orig(request, ...args)
  if (result.endsWith('.node')) console.log('[native]', result)
  return result
}
```

---

## 7. 推荐的纯 JS/WASM 替代方案

> **优先考虑纯 JS/WASM 替代，避免 ABI 问题。**
> WASM 模块无需重编译，跨平台兼容性好。

| 原生模块 | 替代方案 | 性能差距 | 功能覆盖 |
|---------|---------|---------|---------|
| `better-sqlite3` | `sql.js`（WASM） | 慢 2~5x | ✅ 完整 SQL |
| `better-sqlite3` | `@sqlite.org/sqlite-wasm`（OPFS） | 接近原生 | ✅ 完整 |
| `sharp`（图片） | `jimp`（纯 JS） | 慢 10x | ✅ 基本操作 |
| `sharp`（图片） | `@squoosh/lib`（WASM） | 慢 2~3x | ✅ 编解码 |
| `canvas` | 渲染层 `<canvas>` API | — | ✅ 可能更好 |
| `node-canvas` | 渲染层 `OffscreenCanvas` | — | ✅ 可能更好 |
| `bcrypt` | `bcryptjs`（纯 JS） | 慢 3x | ✅ 完整 |
| `argon2` | `argon2-browser`（WASM） | 接近原生 | ✅ 完整 |
| `leveldown` | `level-js`（IndexedDB）或 `utools.db` | — | ✅ 基本 |
| `ffi-napi` | 无等价纯 JS 方案 | — | ❌ 需重编译 |

### sql.js 使用示例（utools/preload.ts）

```ts
// utools/preload.ts
// ⚠️ sql.js 使用 WASM，首次加载需要几百毫秒，建议在插件初始化时预加载

import fs from 'node:fs'
import path from 'node:path'
import initSqlJs, { type Database, type SqlJsStatic } from 'sql.js'

// 插件目录（wasm 文件需要放在插件包内）
const wasmPath = path.join(
  window.utools.getPluginPath(),
  'node_modules/sql.js/dist/sql-wasm.wasm'
)

let _SQL: SqlJsStatic | null = null
let _db: Database | null = null
const DB_PATH = path.join(window.utools.getPath('userData'), 'app.sqlite')

/** 初始化 sql.js 数据库。 */
export async function initDB(): Promise<void> {
  if (_db) return

  _SQL = await initSqlJs({
    locateFile: () => wasmPath,
  })

  if (fs.existsSync(DB_PATH)) {
    const fileBuffer = fs.readFileSync(DB_PATH)
    _db = new _SQL.Database(fileBuffer)
    return
  }

  _db = new _SQL.Database()
  _db.run(`CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    content TEXT,
    created_at INTEGER DEFAULT (strftime('%s', 'now'))
  )`)
  persist()
}

/** 查询并返回行对象数组。 */
export function query(sql: string, params: unknown[] = []): Record<string, unknown>[] {
  if (!_db) throw new Error('DB 未初始化，请先调用 initDB()')
  const result = _db.exec(sql, params)
  if (!result.length) return []
  const [{ columns, values }] = result
  return values.map(row => Object.fromEntries(columns.map((col, i) => [col, row[i]])))
}

/** 执行写操作并立即持久化。 */
export function run(sql: string, params: unknown[] = []): void {
  if (!_db) throw new Error('DB 未初始化')
  _db.run(sql, params)
  persist()
}

/** 持久化到磁盘。 */
export function persist(): void {
  if (!_db) return
  const data = _db.export()
  fs.writeFileSync(DB_PATH, Buffer.from(data))
}

/** 关闭数据库。 */
export function closeDB(): void {
  _db?.close()
  _db = null
}

// 插件卸载时关闭数据库
window.utools.onPluginDetach(() => {
  persist()
  closeDB()
})
```

---

## 8. 自动化脚本示例

在 `package.json` 中添加重编译脚本，确保每次 `npm install` 后自动重编译：

```json
{
  "scripts": {
    "rebuild": "electron-rebuild --version $ELECTRON_VERSION --arch x64",
    "postinstall": "npm run rebuild"
  },
  "config": {
    "electron_version": "29.0.0"
  }
}
```

```bash
# scripts/rebuild-native.sh
#!/usr/bin/env bash
set -e

# 从 uTools 插件内部获取 Electron 版本（需先运行一次插件）
# 或者直接硬编码（推荐在 CI 中使用）
ELECTRON_VERSION="${ELECTRON_VERSION:-29.0.0}"
ARCH="${ARCH:-x64}"

echo "🔨 重编译原生模块..."
echo "  Electron: $ELECTRON_VERSION"
echo "  Arch:     $ARCH"

npx electron-rebuild \
  --version "$ELECTRON_VERSION" \
  --arch "$ARCH" \
  --module-dir ./node_modules \
  --only better-sqlite3,node-canvas

echo "✅ 重编译完成"
```
