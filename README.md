# uTools Plugin Development Skill

面向 Codex / Agents 的 uTools 插件开发与迁移 Skill，用于把 Web 应用、Electron 应用、Tauri 应用转换为可维护的 uTools 插件，并辅助调试 `plugin.json`、`preload.ts`、浏览器 mock、UPX 打包和运行时问题。

## 适用场景

- 从 Vue / React / Angular / Svelte / Solid 等前端应用迁移到 uTools 插件。
- 从 Electron 应用降维迁移：将 `main` / `ipcMain` / `BrowserWindow` / `dialog` / `shell` 等能力映射到 uTools preload 服务与 host API。
- 从 Tauri 应用迁移：将 `#[tauri::command]` / `invoke()` / `@tauri-apps/api` 映射到 Node.js + uTools preload bridge。
- 使用 `@ver5/vite-plugin-utools` 设计、构建、mock、打包 uTools 插件。
- 排查 `preload.js` CommonJS/ESM 作用域、原生模块 ABI、明暗主题、uTools API 契约、UPX 内容缺失等问题。

## 核心约束

- 源码工程默认使用：`utools/plugin.json` + `utools/preload.ts` + `utools/logo.png`。
- 使用 `@ver5/vite-plugin-utools` 时，源码 `utools/plugin.json` 的 `preload` 必须是 `"preload.ts"`。
- 生产构建输出仍应生成 `dist/preload.js`，并确保它不落在 `"type": "module"` 的 package scope 下；必要时在 `dist/package.json` 写入 `{ "type": "commonjs" }`。
- UI 与宿主能力分层：前端只调用窄桥接 API，文件系统、Electron renderer API、uTools DB、AI tools 等放在 preload/service 层。

## 目录结构

```text
SKILL.md                         # Skill 入口与任务导航
agents/openai.yaml               # UI 元数据
scripts/audit_utools_project.py  # uTools 项目审计脚本
references/                      # 按需加载的迁移与 API 参考
```

重点参考：

- `references/app-migration-playbook.md`：Web / Electron / Tauri 迁移总入口。
- `references/framework-quirks.md`：Vue / React / Angular / Svelte / Solid 在 uTools 容器中的适配注意事项。
- `references/tauri-command-mapping.md`：Tauri command / API 到 uTools preload 的映射。
- `references/native-module-recompile.md`：原生 `.node` 模块 ABI 重编译。
- `references/utools-api-reference.md` 与 `references/utools-api-cheatsheet.md`：uTools API 能力图与速查。
- `references/ver5-vite-plugin-utools.md`：`@ver5/vite-plugin-utools` 配置、mock、UPX、排错。

## 安装

安装到 Agents skills 目录：

```bash
git clone https://github.com/uxiew/utools-skills.git ~/.agents/skills/utools-plugin-development
```

如果使用 Codex skills 目录：

```bash
git clone https://github.com/uxiew/utools-skills.git ~/.codex/skills/utools-plugin-development
```

## 使用示例

```text
Use $utools-plugin-development to migrate this Electron app into a uTools plugin.
```

```text
Use $utools-plugin-development to convert this Tauri invoke-based app to uTools preload services.
```

```text
Use $utools-plugin-development to audit this Vue/Vite app before packaging it as a uTools plugin.
```

## 审计脚本

在目标项目根目录运行：

```bash
python3 ~/.agents/skills/utools-plugin-development/scripts/audit_utools_project.py . --strict
```

脚本会检查并提示：

- `plugin.json` 基础字段、feature/cmd/tool 结构。
- `@ver5/vite-plugin-utools` 是否配置完整。
- `utools/plugin.json` 是否使用 `preload.ts` 作为源码入口。
- 生成的 `preload.js` 是否受 `"type": "module"` 影响。
- 是否存在 Web 框架、Electron、Tauri 迁移信号。

## 验证 Skill

```bash
python3 -m py_compile scripts/audit_utools_project.py
python3 /path/to/quick_validate.py .
```

## License

MIT. See [LICENSE](./LICENSE).
