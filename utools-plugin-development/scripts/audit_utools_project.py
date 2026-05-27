#!/usr/bin/env python3
"""Audit a uTools plugin project for common manifest, preload, and Vite-plugin issues."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

MATCH_TYPES = {"regex", "over", "img", "files", "window"}
CATCH_ALL_REGEX = {"/.*/", "/.+/", "/(.)+/", "/[\\s\\S]*/"}
SNAKE_CASE_RE = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")


@dataclass
class Finding:
    """A single audit result."""

    level: str
    message: str
    path: str | None = None


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", nargs="?", default=".", help="Project root directory, defaults to cwd.")
    parser.add_argument("--config", help="Explicit plugin.json path. Relative paths resolve from project root.")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero when warnings are present.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON output.")
    return parser.parse_args()


def add(findings: list[Finding], level: str, message: str, path: str | None = None) -> None:
    """Append an audit finding."""

    findings.append(Finding(level=level, message=message, path=path))


def find_manifest(project: Path, explicit: str | None) -> Path | None:
    """Locate the most likely source plugin.json."""

    if explicit:
        candidate = Path(explicit)
        return candidate if candidate.is_absolute() else project / candidate

    candidates = [project / "utools" / "plugin.json", project / "plugin.json", project / "dist" / "plugin.json"]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    matches = sorted(project.glob("**/plugin.json"), key=lambda p: ("node_modules" in p.parts, len(p.parts)))
    return matches[0] if matches else None


def load_json(path: Path, findings: list[Finding]) -> dict[str, Any] | None:
    """Load JSON with a clear fatal finding on failure."""

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - diagnostic script should surface exact parser error.
        add(findings, "error", f"Cannot parse JSON: {exc}", str(path))
        return None
    if not isinstance(data, dict):
        add(findings, "error", "plugin.json root must be an object", str(path))
        return None
    return data


def rel_exists(base: Path, value: Any) -> bool:
    """Return whether a manifest-relative path exists."""

    return isinstance(value, str) and bool(value.strip()) and (base / value).exists()


def find_nearest_package_json(start: Path, stop: Path) -> Path | None:
    """Find the nearest package.json that controls Node module type for a path."""

    current = start if start.is_dir() else start.parent
    stop = stop.resolve()
    for directory in [current, *current.parents]:
        package_path = directory / "package.json"
        if package_path.exists():
            return package_path
        if directory == stop or directory.parent == directory:
            break
    return None


def read_package_type(package_path: Path) -> str | None:
    """Read a package.json `type` field without emitting findings."""

    try:
        data = json.loads(package_path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 - package type check is best-effort.
        return None
    package_type = data.get("type")
    return package_type if isinstance(package_type, str) else None


def load_project_package(project: Path, findings: list[Finding]) -> dict[str, Any] | None:
    """Load the project package.json when present."""

    package_path = project / "package.json"
    if not package_path.exists():
        return None
    return load_json(package_path, findings)


def has_ver5_plugin(package: dict[str, Any] | None) -> bool:
    """Return whether @ver5/vite-plugin-utools is declared in dependencies."""

    if not package:
        return False
    deps = {**package.get("dependencies", {}), **package.get("devDependencies", {})}
    return "@ver5/vite-plugin-utools" in deps


def check_path_field(
    findings: list[Finding], manifest_dir: Path, data: dict[str, Any], field: str, required: bool, suffix: str | None = None
) -> None:
    """Validate a manifest-relative path field."""

    value = data.get(field)
    if value in (None, ""):
        if required:
            add(findings, "error", f"Missing required `{field}` path")
        return
    if not isinstance(value, str):
        add(findings, "error", f"`{field}` must be a string")
        return
    if suffix and not value.endswith(suffix):
        if field == "preload" and value.endswith(".ts"):
            add(findings, "info", "Source manifest uses preload.ts; final generated uTools output must contain preload.js", value)
        else:
            add(findings, "warn", f"`{field}` should usually end with `{suffix}` in final uTools output", value)
    if not (manifest_dir / value).exists():
        add(findings, "warn", f"`{field}` target does not exist relative to plugin.json", str(manifest_dir / value))


def check_preload_module_scope(findings: list[Finding], project: Path, manifest_dir: Path, data: dict[str, Any]) -> None:
    """Warn when preload.js is under a package scope that treats .js as ESM."""

    preload = data.get("preload")
    if not isinstance(preload, str) or not preload.endswith(".js"):
        return
    preload_path = (manifest_dir / preload).resolve()
    package_json = find_nearest_package_json(preload_path, project)
    if package_json is None:
        return
    package_type = read_package_type(package_json)
    if package_type == "module":
        add(
            findings,
            "error",
            "preload.js is under a nearest package.json with `type: module`; uTools preload should run as CommonJS. Add a nearer package.json with `type: commonjs` to the packaged output or move preload out of that ESM scope.",
            str(package_json),
        )
    elif package_type == "commonjs":
        add(findings, "info", "Nearest package.json marks preload scope as CommonJS", str(package_json))


def check_source_preload_ts_constraint(
    findings: list[Finding], project: Path, manifest: Path, data: dict[str, Any], package: dict[str, Any] | None
) -> None:
    """Require utools/preload.ts for @ver5/vite-plugin-utools source manifests."""

    try:
        relative_manifest = manifest.resolve().relative_to(project.resolve())
    except ValueError:
        return
    if relative_manifest.parts[:2] != ("utools", "plugin.json"):
        return
    if not has_ver5_plugin(package):
        return
    preload = data.get("preload")
    if not isinstance(preload, str) or preload != "preload.ts":
        add(
            findings,
            "error",
            "@ver5/vite-plugin-utools source manifest `utools/plugin.json` must use `preload.ts` for development; final dist should still emit preload.js.",
            str(manifest),
        )
        return
    preload_path = manifest.parent / preload
    if not preload_path.exists():
        add(findings, "error", "`utools/plugin.json` points to preload.ts but the file is missing", str(preload_path))


def iter_cmds(feature: dict[str, Any]) -> Iterable[tuple[int, Any]]:
    """Yield command entries with indexes."""

    cmds = feature.get("cmds")
    if isinstance(cmds, list):
        yield from enumerate(cmds)


def check_features(findings: list[Finding], data: dict[str, Any]) -> None:
    """Validate feature definitions and command shapes."""

    features = data.get("features")
    tools_only = not data.get("main") and isinstance(data.get("tools"), dict)
    if features is None:
        if not tools_only:
            add(findings, "error", "Missing `features` for a UI-triggered plugin")
        return
    if not isinstance(features, list) or not features:
        add(findings, "error", "`features` must be a non-empty array")
        return

    seen_codes: set[str] = set()
    for feature_index, feature in enumerate(features):
        if not isinstance(feature, dict):
            add(findings, "error", f"features[{feature_index}] must be an object")
            continue
        code = feature.get("code")
        if not isinstance(code, str) or not code.strip():
            add(findings, "error", f"features[{feature_index}].code is required")
        elif code in seen_codes:
            add(findings, "error", f"Duplicate feature code `{code}`")
        else:
            seen_codes.add(code)

        cmds = feature.get("cmds")
        if not isinstance(cmds, list) or not cmds:
            add(findings, "error", f"feature `{code or feature_index}` must define non-empty cmds")
            continue
        for cmd_index, cmd in iter_cmds(feature):
            prefix = f"feature `{code or feature_index}` cmds[{cmd_index}]"
            if isinstance(cmd, str):
                if not cmd.strip():
                    add(findings, "error", f"{prefix} is an empty command")
                if len(cmd.strip()) > 24:
                    add(findings, "warn", f"{prefix} is long; uTools commands should be concise")
                continue
            if not isinstance(cmd, dict):
                add(findings, "error", f"{prefix} must be a string or object")
                continue
            cmd_type = cmd.get("type")
            if cmd_type not in MATCH_TYPES:
                add(findings, "error", f"{prefix}.type must be one of {sorted(MATCH_TYPES)}")
            if not isinstance(cmd.get("label"), str) or not cmd.get("label", "").strip():
                add(findings, "warn", f"{prefix} should define a clear label")
            match = cmd.get("match")
            if cmd_type == "regex":
                if not isinstance(match, str) or not match:
                    add(findings, "error", f"{prefix}.match is required for regex commands")
                elif match in CATCH_ALL_REGEX:
                    add(findings, "warn", f"{prefix}.match looks catch-all and may be ignored by uTools")
            if cmd_type == "files" and cmd.get("extensions") is not None and not isinstance(cmd.get("extensions"), list):
                add(findings, "error", f"{prefix}.extensions must be an array when present")
            if cmd_type == "window" and not isinstance(cmd.get("match"), dict):
                add(findings, "error", f"{prefix}.match must be an object for window commands")


def check_tools(findings: list[Finding], data: dict[str, Any]) -> None:
    """Validate AI Agent tool manifest entries."""

    tools = data.get("tools")
    if tools is None:
        return
    if not isinstance(tools, dict) or not tools:
        add(findings, "error", "`tools` must be a non-empty object when present")
        return
    if not data.get("preload"):
        add(findings, "error", "`tools` requires `preload` so runtime can register handlers")
    for name, tool in tools.items():
        if not SNAKE_CASE_RE.match(str(name)):
            add(findings, "error", f"tool key `{name}` must be lower snake_case")
        if not isinstance(tool, dict):
            add(findings, "error", f"tool `{name}` must be an object")
            continue
        if not isinstance(tool.get("description"), str) or not tool.get("description", "").strip():
            add(findings, "warn", f"tool `{name}` should have a clear description")
        input_schema = tool.get("inputSchema")
        if not isinstance(input_schema, dict):
            add(findings, "error", f"tool `{name}` must define object inputSchema")


def check_package_integration(findings: list[Finding], project: Path, package: dict[str, Any] | None) -> None:
    """Check package.json, Vite config, and TypeScript integration hints."""

    package_path = project / "package.json"
    if not package_path.exists():
        add(findings, "warn", "No package.json found; skip Vite/plugin integration checks")
        return
    if not package:
        return
    has_plugin = has_ver5_plugin(package)
    if not has_plugin:
        add(findings, "warn", "@ver5/vite-plugin-utools is not declared; install it for Vite-based projects")

    vite_files = list(project.glob("vite.config.*"))
    if has_plugin and vite_files:
        joined = "\n".join(p.read_text(encoding="utf-8", errors="ignore") for p in vite_files)
        if "@ver5/vite-plugin-utools" not in joined or "configFile" not in joined:
            add(findings, "warn", "Vite config does not appear to initialize @ver5/vite-plugin-utools with configFile")

    tsconfig = project / "tsconfig.json"
    if has_plugin and tsconfig.exists():
        ts_text = tsconfig.read_text(encoding="utf-8", errors="ignore")
        if "@ver5/vite-plugin-utools/utools" not in ts_text:
            add(findings, "warn", "tsconfig does not include @ver5/vite-plugin-utools/utools types")


def check_manifest(project: Path, manifest: Path) -> tuple[dict[str, Any] | None, list[Finding]]:
    """Run manifest-specific checks."""

    findings: list[Finding] = []
    data = load_json(manifest, findings)
    if data is None:
        return None, findings
    package = load_project_package(project, findings)

    manifest_dir = manifest.parent
    ui_mode = bool(data.get("main")) or bool(data.get("features"))
    tools_only = not data.get("main") and isinstance(data.get("tools"), dict)

    check_path_field(findings, manifest_dir, data, "logo", required=True)
    check_path_field(findings, manifest_dir, data, "main", required=ui_mode and not tools_only, suffix=".html")
    check_path_field(findings, manifest_dir, data, "preload", required=bool(data.get("tools")), suffix=".js")
    check_source_preload_ts_constraint(findings, project, manifest, data, package)
    check_preload_module_scope(findings, project, manifest_dir, data)

    settings = data.get("pluginSetting")
    if settings is not None:
        if not isinstance(settings, dict):
            add(findings, "error", "`pluginSetting` must be an object")
        else:
            height = settings.get("height")
            if height is not None and (not isinstance(height, (int, float)) or height <= 0):
                add(findings, "error", "`pluginSetting.height` must be a positive number")

    if data.get("preload") and not rel_exists(manifest_dir, data.get("preload")):
        ts_candidate = manifest_dir / str(data.get("preload")).removesuffix(".js")
        if ts_candidate.with_suffix(".ts").exists():
            add(findings, "info", "Source preload.ts exists; ensure build outputs preload.js for final uTools runtime", str(ts_candidate.with_suffix(".ts")))

    check_features(findings, data)
    check_tools(findings, data)
    check_package_integration(findings, project, package)
    return data, findings


def print_findings(findings: list[Finding], as_json: bool) -> None:
    """Print findings as human text or JSON."""

    if as_json:
        print(json.dumps([finding.__dict__ for finding in findings], ensure_ascii=False, indent=2))
        return
    if not findings:
        print("OK: no findings")
        return
    for finding in findings:
        location = f" ({finding.path})" if finding.path else ""
        print(f"[{finding.level.upper()}] {finding.message}{location}")


def main() -> int:
    """Run the audit and return a shell exit code."""

    args = parse_args()
    project = Path(args.project).expanduser().resolve()
    findings: list[Finding] = []
    if not project.exists() or not project.is_dir():
        add(findings, "error", "Project root does not exist or is not a directory", str(project))
        print_findings(findings, args.json)
        return 2

    manifest = find_manifest(project, args.config)
    if manifest is None or not manifest.exists():
        add(findings, "error", "Cannot locate plugin.json; pass --config explicitly", str(project))
        print_findings(findings, args.json)
        return 2

    add(findings, "info", "Using plugin.json", str(manifest))
    _, audit_findings = check_manifest(project, manifest)
    findings.extend(audit_findings)
    print_findings(findings, args.json)

    has_error = any(f.level == "error" for f in findings)
    has_warn = any(f.level == "warn" for f in findings)
    if has_error or (args.strict and has_warn):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
