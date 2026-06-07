# Skill overlay

> Current skill overlay (2026-06-07): use this as an extended manifest checklist, especially for publish metadata and trigger shapes. Official uTools docs and generated `@ver5/vite-plugin-utools/utools.schema.json` remain the final source for field availability. In source projects using `@ver5/vite-plugin-utools`, prefer `utools/plugin.json` + `utools/preload.ts`; in generated dist, `plugin.json` should point to `preload.js`.

---

# plugin.json 字段完整 Schema 说明

> uTools 插件配置清单，每个插件必须在根目录放置此文件。
> 构建产物中的 `plugin.json` 路径决定其他所有相对路径的基准。

---

## 顶层字段

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `pluginName` | `string` | ✅ | 插件唯一标识。**发布后不可更改**，更改等于换一个新插件 |
| `version` | `string` | ✅ | 语义版本号，格式 `major.minor.patch`，如 `"1.2.0"` |
| `description` | `string` | ✅ | 插件功能描述（显示在应用市场） |
| `author` | `string` | ✅ | 作者名 |
| `homepage` | `string` | — | 项目主页（GitHub 等），用于跳转反馈 |
| `main` | `string` | ✅* | 前端页面入口 HTML 文件路径（相对路径）。`mode:"none"` 时不需要 |
| `preload` | `string` | — | Node.js 预加载脚本路径。提供系统能力时必填 |
| `logo` | `string` | ✅ | 插件图标路径（推荐 256×256 PNG，建议不超过 512KB） |
| `singleton` | `boolean` | — | 是否单例模式，默认 `true`。设为 `false` 可允许多实例 |
| `height` | `number` | — | 初始内容区高度（px），默认 380。范围 [0, 屏幕高度] |
| `mode` | `string` | — | 运行模式（见下节） |
| `features` | `Feature[]` | ✅ | 功能指令列表（触发方式定义） |
| `tools` | `Tool[]` | — | AI Agent 工具声明（uTools 4+） |
| `development` | `object` | — | 开发模式配置（通常由构建工具自动写入） |
| `$schema` | `string` | — | JSON Schema 路径，用于 IDE 字段提示 |

---

## `mode` 字段

| 值 | 说明 |
|----|------|
| *(不填)* | 默认模式：有 UI 的普通插件 |
| `"none"` | 无 UI 静默执行。不渲染 `main` 页面，仅执行 `preload.js`。适合系统脚本、一键操作类插件 |
| `"list"` | 列表模式（已被 features cmds 覆盖，通常不需要单独设置） |

---

## `features` 数组

每个 Feature 定义一个独立的功能入口。

```typescript
interface Feature {
  code: string          // 功能唯一 ID，对应 onPluginEnter 的 code 字段
  explain: string       // 功能说明（显示在 uTools 搜索结果列表）
  icon?: string         // 该功能的独立图标（可选，不填用插件 logo）
  platform?: Platform[] // 支持的平台过滤，不填表示全平台
  cmds: Cmd[]          // 触发方式数组
}

type Platform = 'darwin' | 'win32' | 'linux'
```

---

## `cmds` 触发方式详解

### 关键词触发（string）

最简单的触发方式，用户在搜索框输入匹配关键词时触发。

```jsonc
{
  "cmds": ["翻译", "translate", "划词翻译"]
}
```

支持**多语言关键词**混写，关键词区分大小写。

---

### regex — 正则匹配触发

匹配剪贴板内容或当前选中文本。

```jsonc
{
  "code": "open-url",
  "explain": "打开链接",
  "cmds": [
    {
      "type": "regex",
      "label": "识别 URL",      // 显示在触发卡片上的说明
      "match": "/^https?:\\/\\//i",  // 正则字符串（必须以 / 开头结尾）
      "minLength": 8,            // 最小匹配字符长度
      "maxLength": 2048          // 最大匹配字符长度（防止超长内容误触）
    }
  ]
}
```

**正则字符串格式**：`"/pattern/flags"` — 注意两端必须有斜杠，且需要 JSON 转义反斜杠。

常用正则示例：
```
"/^https?:\\/\\//i"          → URL
"/(\\d{4}-\\d{2}-\\d{2})/"  → 日期
"/^1[3-9]\\d{9}$/"          → 手机号
"/^[\\w.+-]+@[\\w-]+\\.\\w+$/" → 邮箱
"/^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/" → HEX 颜色
```

---

### files — 文件触发

拖入文件或通过系统文件管理器选中文件触发。

```jsonc
{
  "code": "compress-image",
  "explain": "压缩图片",
  "cmds": [
    {
      "type": "files",
      "label": "图片压缩",
      "fileType": "image",      // 文件类型过滤
      "minCount": 1,            // 最少文件数量
      "maxCount": 10            // 最多文件数量
    }
  ]
}
```

| `fileType` 值 | 匹配范围 |
|--------------|---------|
| `"image"` | jpg/jpeg/png/gif/bmp/webp/svg 等图片 |
| `"video"` | mp4/mov/avi/mkv 等视频 |
| `"audio"` | mp3/wav/flac/aac 等音频 |
| `"directory"` | 目录（文件夹） |
| *(不填)* | 任意文件类型 |

---

### window — 活跃窗口触发

当特定应用处于前台（活跃窗口）时，在超级面板中出现。

```jsonc
{
  "code": "browser-action",
  "explain": "浏览器助手",
  "cmds": [
    {
      "type": "window",
      "label": "主流浏览器",
      "match": {
        "app": ["Google Chrome", "Safari", "Firefox", "Microsoft Edge"],
        // 也可以用正则匹配窗口标题
        // "title": "/GitHub/"
      }
    }
  ]
}
```

| 匹配字段 | 类型 | 说明 |
|---------|------|------|
| `app` | `string[]` | 应用名数组（精确匹配） |
| `title` | `string`（正则） | 窗口标题正则 |

---

### img — 图像内容触发

用户截图后出现该插件选项（超级面板图像模式）。

```jsonc
{
  "code": "ocr",
  "explain": "识别图片文字",
  "cmds": [
    {
      "type": "img",
      "label": "OCR 文字识别"
    }
  ]
}
```

---

### over — 超级面板（划词触发）

用户在任意应用中选中文本后，通过超级面板进入。

```jsonc
{
  "code": "translate-selection",
  "explain": "翻译选中文本",
  "cmds": [
    {
      "type": "over",
      "label": "划词翻译"
    }
  ]
}
```

---

## `tools` 数组（AI Agent 工具声明）

> uTools 4+ 功能。将插件能力以 JSON Schema 格式暴露给 AI 大模型 Agent。

```typescript
interface Tool {
  name: string           // 工具函数名（snake_case，对应 onToolCall 的 toolName）
  description: string    // 工具功能描述（AI 根据此判断何时调用）
  inputSchema: JSONSchema    // 输入参数的 JSON Schema
  outputSchema?: JSONSchema  // 输出结果的 JSON Schema（可选）
}
```

```jsonc
{
  "tools": [
    {
      "name": "search_local_files",
      "description": "在用户本地文件系统中搜索文件，返回匹配的文件路径列表",
      "inputSchema": {
        "type": "object",
        "properties": {
          "keyword": {
            "type": "string",
            "description": "搜索关键词"
          },
          "directory": {
            "type": "string",
            "description": "搜索起始目录，默认为用户主目录"
          },
          "maxResults": {
            "type": "number",
            "description": "最大返回数量，默认 20"
          }
        },
        "required": ["keyword"]
      },
      "outputSchema": {
        "type": "object",
        "properties": {
          "files": {
            "type": "array",
            "items": { "type": "string" },
            "description": "匹配的文件绝对路径列表"
          },
          "total": {
            "type": "number",
            "description": "实际找到的总数"
          }
        }
      }
    }
  ]
}
```

---

## `development` 字段（开发模式）

通常由 vite-plugin-utools 自动写入，无需手动配置。

```jsonc
{
  "development": {
    "main": "http://localhost:3000",  // 开发服务器地址（HMR 时覆盖 main）
    "preload": {
      "path": "./utools/preload.ts"   // preload 源文件路径
    }
  }
}
```

---

## 完整示例

```jsonc
{
  "$schema": "../node_modules/@ver5/vite-plugin-utools/utools.schema.json",

  "pluginName": "my-file-manager",
  "version": "2.1.0",
  "description": "本地文件快速访问与管理工具",
  "author": "your-name",
  "homepage": "https://github.com/your-name/my-file-manager",

  "main": "index.html",
  "preload": "preload.js",
  "logo": "logo.png",

  "singleton": true,
  "height": 480,

  "features": [
    {
      "code": "main",
      "explain": "打开文件管理器",
      "cmds": ["文件管理", "files", "fm"]
    },
    {
      "code": "recent",
      "explain": "最近访问的文件",
      "cmds": ["最近文件", "recent files"]
    },
    {
      "code": "compress",
      "explain": "压缩文件",
      "platform": ["darwin", "win32"],
      "cmds": [
        "压缩",
        {
          "type": "files",
          "label": "拖入文件压缩",
          "minCount": 1,
          "maxCount": 50
        }
      ]
    },
    {
      "code": "open-path",
      "explain": "直接打开路径",
      "cmds": [
        {
          "type": "regex",
          "label": "识别文件路径",
          "match": "/^(\\/|[A-Za-z]:\\\\)/",
          "minLength": 2,
          "maxLength": 512
        }
      ]
    }
  ],

  "tools": [
    {
      "name": "open_file",
      "description": "使用系统默认程序打开指定路径的文件",
      "inputSchema": {
        "type": "object",
        "properties": {
          "path": { "type": "string", "description": "文件的绝对路径" }
        },
        "required": ["path"]
      }
    }
  ]
}
```

---

## 常见配置错误

| 错误 | 原因 | 修复 |
|------|------|------|
| `main` 用绝对路径 | uTools 通过 `file://` 加载资源 | 改为相对路径 `"index.html"` |
| `version` 格式错误 | 必须是 `x.y.z` 格式 | `"1.0.0"` 而非 `"v1.0"` |
| `cmds` 为空数组 | 插件无法被触发 | 至少添加一个关键词 |
| `regex` 中 `match` 无斜杠 | 正则格式错误 | `"/pattern/"` 必须有前后斜杠 |
| `logo` 文件过大 | 加载缓慢，影响体验 | 建议 PNG 格式，不超过 512KB |
| `pluginName` 含特殊字符 | 可能导致上架审核失败 | 只用字母、数字、连字符 |
