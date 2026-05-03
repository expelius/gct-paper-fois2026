"""workspace_config.py — portable workspace configuration for holonic-graph.

Reads `holonic_graph.toml` from the project root (walks up the directory tree
to find it) and exposes a typed `WorkspaceConfig` dataclass.  If no TOML is
found, sensible generic defaults are used so existing code doesn't break.

Usage (from any extractor or tool)::

    from core.workspace_config import WorkspaceConfig
    cfg = WorkspaceConfig.load()        # discovers from __file__ location
    cfg = WorkspaceConfig.load(start=Path("/some/project"))  # explicit root

Key properties::

    cfg.project_root        Path  — workspace root (contains CLAUDE.md / .git)
    cfg.experiments_log     Path  — absolute path to EXPERIMENTS-LOG.md
    cfg.results_dirs        list[Path]  — dirs to scan for results_d*/
    cfg.results_dir_pattern str   — regex for extracting D-IDs from dir names
    cfg.trace_did_field     str   — TRACE header key for the experiment ID
    cfg.terminal_states     set[str]  — states that block re-execution
    cfg.transient_states    set[str]  — states the wrapper may transition
    cfg.kg_dir              Path  — knowledge-graph/ directory
    cfg.snapshot_pattern    str   — glob for snapshot JSON files

TOML parsing uses Python 3.11+ stdlib `tomllib`; falls back to a minimal
hand-written parser for Python 3.10 environments without the `tomli` package.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ── TOML loader ──────────────────────────────────────────────────────────────
try:
    import tomllib as _tomllib          # Python 3.11+
except ImportError:
    try:
        import tomli as _tomllib        # third-party backport
    except ImportError:
        _tomllib = None                 # fall back to minimal parser


def _parse_toml_minimal(text: str) -> dict[str, Any]:
    """Minimal TOML parser — handles [sections], key = "string", and arrays.

    Only supports the subset used in holonic_graph.toml:
      [section] headers
      key = "string value"
      key = ["item1", "item2"]
      key = true / false
    Inline tables and nested arrays are not supported.
    """
    result: dict[str, Any] = {}
    current_section: dict[str, Any] = result

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        # Section header
        if line.startswith("[") and line.endswith("]"):
            section_name = line[1:-1].strip()
            if "." in section_name:
                # nested: [a.b] → result["a"]["b"]
                parts = section_name.split(".")
                d = result
                for p in parts[:-1]:
                    d = d.setdefault(p, {})
                current_section = d.setdefault(parts[-1], {})
            else:
                current_section = result.setdefault(section_name, {})
            continue
        # Key = value
        if "=" not in line:
            continue
        key, _, val_raw = line.partition("=")
        key = key.strip()
        val_raw = val_raw.strip()
        # Strip inline comment
        # String
        if val_raw.startswith('"') or val_raw.startswith("'"):
            q = val_raw[0]
            val_raw = val_raw.strip(q)
            current_section[key] = val_raw
        # Array of strings
        elif val_raw.startswith("["):
            items = re.findall(r'["\'](.*?)["\']', val_raw)
            current_section[key] = items
        # Boolean
        elif val_raw in ("true", "false"):
            current_section[key] = val_raw == "true"
        # Number
        elif re.match(r"^-?\d+(\.\d+)?$", val_raw):
            current_section[key] = (float if "." in val_raw else int)(val_raw)
        else:
            current_section[key] = val_raw
    return result


def _load_toml(path: Path) -> dict[str, Any]:
    """Load a TOML file using stdlib or fallback parser."""
    if _tomllib is not None:
        with path.open("rb") as f:
            return _tomllib.load(f)
    return _parse_toml_minimal(path.read_text(encoding="utf-8"))


# ── Config discovery ─────────────────────────────────────────────────────────
_CONFIG_NAME = "holonic_graph.toml"
_ANCHOR_FILES = (".git", "CLAUDE.md", "pyproject.toml")


def _find_project_root(start: Path) -> Path | None:
    """Walk up from `start` to find the workspace root."""
    for p in [start, *start.parents]:
        if any((p / a).exists() for a in _ANCHOR_FILES):
            return p
    return None


def _find_toml(start: Path) -> Path | None:
    """Walk up to find holonic_graph.toml, checking both root and kg_dir."""
    for p in [start, *start.parents]:
        candidate = p / _CONFIG_NAME
        if candidate.exists():
            return candidate
        # Also check inside knowledge-graph/ sub-dir
        candidate2 = p / "knowledge-graph" / _CONFIG_NAME
        if candidate2.exists():
            return candidate2
    return None


# ── Defaults (generic, project-agnostic) ─────────────────────────────────────
_DEFAULTS: dict[str, Any] = {
    "workspace": {
        "name": "(unknown project)",
        "encoding": "utf-8",
    },
    "experiments": {
        "log": "EXPERIMENTS-LOG.md",
        "results_dirs": ["results"],
        "results_dir_pattern": r"^results_(d\d+[a-z]?)_?",
        "trace_did_field": "D-ID",
        "terminal_states": ["OK", "FAIL", "SUPERSEDED", "INCONCLUSIVE", "NOT CONFIRMED"],
        "transient_states": ["QUEUED", "RUN"],
    },
    "knowledge_graph": {
        "snapshot_pattern": "tensegrity_graph_phase*_complete.json",
        "kg_dir": "knowledge-graph",
    },
}


def _deep_merge(base: dict, override: dict) -> dict:
    """Merge override into base (non-destructive)."""
    result = dict(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(result.get(k), dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


# ── WorkspaceConfig dataclass ─────────────────────────────────────────────────
@dataclass
class WorkspaceConfig:
    """Typed workspace configuration derived from holonic_graph.toml."""

    project_root:         Path
    workspace_name:       str
    experiments_log:      Path
    results_dirs:         list[Path]
    results_dir_pattern:  str
    trace_did_field:      str
    terminal_states:      set[str]
    transient_states:     set[str]
    kg_dir:               Path
    snapshot_pattern:     str
    toml_path:            Path | None  = field(default=None, repr=False)

    # ── Factory ─────────────────────────────────────────────────────────────
    @classmethod
    def load(cls, start: Path | None = None) -> "WorkspaceConfig":
        """Discover and load holonic_graph.toml; fall back to defaults."""
        if start is None:
            # Walk up from this file's location
            start = Path(__file__).parent

        toml_path = _find_toml(start)
        if toml_path is not None:
            raw = _load_toml(toml_path)
            merged = _deep_merge(_DEFAULTS, raw)
            project_root = toml_path.parent
            # If the TOML lives inside knowledge-graph/, root is one level up
            if toml_path.parent.name == "knowledge-graph":
                project_root = toml_path.parent.parent
        else:
            merged = _DEFAULTS
            project_root = _find_project_root(start) or start
            toml_path = None

        exp = merged["experiments"]
        kg  = merged["knowledge_graph"]
        ws  = merged["workspace"]

        return cls(
            project_root        = project_root,
            workspace_name      = ws.get("name", "(unknown)"),
            experiments_log     = project_root / exp["log"],
            results_dirs        = [
                project_root / d for d in exp["results_dirs"]
            ],
            results_dir_pattern = exp["results_dir_pattern"],
            trace_did_field     = exp.get("trace_did_field", "D-ID"),
            terminal_states     = set(exp.get("terminal_states",
                                              _DEFAULTS["experiments"]["terminal_states"])),
            transient_states    = set(exp.get("transient_states",
                                              _DEFAULTS["experiments"]["transient_states"])),
            kg_dir              = project_root / kg.get("kg_dir", "knowledge-graph"),
            snapshot_pattern    = kg.get("snapshot_pattern",
                                         _DEFAULTS["knowledge_graph"]["snapshot_pattern"]),
            toml_path           = toml_path,
        )

    # ── Helpers ──────────────────────────────────────────────────────────────
    def scan_results_dids(self) -> dict[str, Path]:
        """Scan all results_dirs and return {D-ID: results_dir_path}."""
        pat = re.compile(self.results_dir_pattern, re.IGNORECASE)
        found: dict[str, Path] = {}
        for rdir in self.results_dirs:
            if not rdir.is_dir():
                continue
            for entry in rdir.iterdir():
                if not entry.is_dir():
                    continue
                m = pat.match(entry.name)
                if not m:
                    continue
                raw = m.group(1)
                digits = re.sub(r"^[dD]", "", raw)
                did = f"D-{digits}"
                found[did] = entry
        return found

    def find_snapshot(self, prefer_most_ghosts: bool = False) -> Path | None:
        """Return the best snapshot JSON from kg_dir."""
        snaps = sorted(self.kg_dir.glob(self.snapshot_pattern))
        if not snaps:
            return None
        if not prefer_most_ghosts:
            return snaps[-1]
        # Pick snapshot with most ghost_experiment nodes
        import json
        best, best_n = snaps[-1], 0
        for s in snaps:
            try:
                with s.open(encoding="utf-8") as f:
                    data = json.load(f)
                n = sum(1 for nd in data["nodes"]
                        if (nd.get("metadata") or {}).get("node_type") == "ghost_experiment")
                if n > best_n:
                    best_n, best = n, s
            except Exception:
                pass
        return best

    def __repr__(self) -> str:
        return (
            f"WorkspaceConfig(name={self.workspace_name!r}, "
            f"root={self.project_root}, "
            f"log={self.experiments_log.name}, "
            f"results_dirs={[d.name for d in self.results_dirs]}, "
            f"toml={self.toml_path})"
        )


# ── Code-holon meta ───────────────────────────────────────────────────────────
from .holon_meta import HolonMeta as _HolonMeta
__holon__ = _HolonMeta(
    name="workspace_config",
    scale=1,
    aristotelian_cause="formal",
    container=["core"],
    substrate=["core.schema"],
    effect=["WorkspaceConfig — typed config from holonic_graph.toml"],
    description=(
        "Reads holonic_graph.toml to make anti-ghost mechanisms portable "
        "across workspaces. Falls back to generic defaults when no TOML found."
    ),
)
