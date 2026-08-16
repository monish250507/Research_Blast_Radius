"""Python static adapter: deterministic AST extraction.

Builds IMPORTS / CALLS / READS / WRITES edges from Python `ast`. Dynamic
constructs (importlib, eval/exec, subprocess, reflection, plugin loading) are
emitted as coverage gaps — never guessed as dependencies.
"""

from __future__ import annotations

import ast
import hashlib
import posixpath
from dataclasses import dataclass, field
from typing import Any

from ..logging import get_logger
from ..schemas import (
    CoverageLayer,
    EdgeRelation,
    Evidence,
    EvidenceSourceType,
    GraphEdge,
    GraphNode,
    NodeType,
    ProvenanceType,
    ids,
)
from .base import AdapterContext, AdapterOutput

log = get_logger(__name__)

_FILE_EXTS = (".csv", ".json", ".yaml", ".yml", ".png", ".pkl", ".joblib", ".npz",
              ".npy", ".txt", ".parquet", ".h5", ".hdf5", ".pth", ".pt", ".onnx",
              ".log", ".ipynb", ".md", ".tsv", ".xml", ".db", ".sqlite")

_READ_VERBS = {"read_csv", "read_json", "read_pickle", "load", "load_model", "read_table",
               "read", "load_state_dict", "safe_load", "from_pickle", "from_json"}
_WRITE_VERBS = {"to_csv", "to_json", "to_pickle", "dump", "save", "save_model", "write",
                "save_state_dict", "to_file", "to_parquet", "export", "writelines",
                "savefig", "imwrite", "write_bytes", "write_text"}


@dataclass
class ImportRec:
    module: str
    alias: str
    names: list[str] = field(default_factory=list)
    lineno: int = 0
    is_from: bool = False


@dataclass
class DefRec:
    name: str
    kind: str
    lineno: int = 0


@dataclass
class CallRec:
    target: str
    lineno: int = 0


@dataclass
class FileRefRec:
    path: str
    mode: str  # READ | WRITE | UNKNOWN
    lineno: int = 0
    resolved: bool = False
    resolved_path: str | None = None


@dataclass
class GapRec:
    kind: str
    lineno: int = 0
    detail: str = ""


@dataclass
class ParseResult:
    source_hash: str
    imports: list[ImportRec] = field(default_factory=list)
    defs: dict[str, DefRec] = field(default_factory=dict)
    calls: list[CallRec] = field(default_factory=list)
    file_refs: list[FileRefRec] = field(default_factory=list)
    dynamic_gaps: list[GapRec] = field(default_factory=list)
    error: str | None = None


class PythonAdapter:
    def __init__(self) -> None:
        pass

    def parse(self, source: str) -> ParseResult:
        source_hash = hashlib.sha256(source.encode("utf-8")).hexdigest()
        try:
            tree = ast.parse(source)
        except SyntaxError as exc:
            return ParseResult(source_hash=source_hash, error=f"SyntaxError: {exc}")
        result = ParseResult(source_hash=source_hash)
        consumed: set[tuple[str, int]] = set()
        module_consts: dict[str, str] = {}
        func_arg_consts: dict[str, dict[str, str]] = {}
        for stmt_node in tree.body:
            if isinstance(stmt_node, ast.Assign) and len(stmt_node.targets) == 1 \
                    and isinstance(stmt_node.targets[0], ast.Name):
                _collect_const(module_consts, stmt_node.targets[0].id, stmt_node.value)
            elif isinstance(stmt_node, ast.AnnAssign) and isinstance(stmt_node.target, ast.Name) \
                    and stmt_node.value is not None:
                _collect_const(module_consts, stmt_node.target.id, stmt_node.value)
            elif isinstance(stmt_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                func_arg_consts[stmt_node.name] = _function_arg_consts(stmt_node, module_consts)

        parent_of: dict[ast.AST, ast.AST] = {}
        for walk_node in ast.walk(tree):
            for child in ast.iter_child_nodes(walk_node):
                parent_of[child] = walk_node

        for walk_node in ast.walk(tree):
            if isinstance(walk_node, ast.Import):
                for alias in walk_node.names:
                    result.imports.append(ImportRec(module=alias.name, alias=alias.asname or alias.name,
                                                    lineno=getattr(walk_node, "lineno", 0)))
            elif isinstance(walk_node, ast.ImportFrom) and walk_node.module:
                mod = walk_node.module
                names = [a.name for a in walk_node.names if a.name != "*"]
                for a in walk_node.names:
                    if a.name == "*":
                        continue
                    result.imports.append(ImportRec(module=mod, alias=a.asname or a.name,
                                                    names=[a.name], lineno=getattr(walk_node, "lineno", 0),
                                                    is_from=True))
                _ = names
            elif isinstance(walk_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                result.defs[walk_node.name] = DefRec(walk_node.name, "function",
                                                     getattr(walk_node, "lineno", 0))
            elif isinstance(walk_node, ast.ClassDef):
                result.defs[walk_node.name] = DefRec(walk_node.name, "class",
                                                     getattr(walk_node, "lineno", 0))
            elif isinstance(walk_node, ast.Call):
                result.calls.append(CallRec(_call_target(walk_node.func),
                                            getattr(walk_node, "lineno", 0)))
                result.dynamic_gaps.extend(_dynamic_in_call(walk_node))
                scope = _enclosing_function(walk_node, parent_of)
                const_map = {**module_consts, **func_arg_consts.get(scope, {})}
                _open_refs(walk_node, result, consumed, const_map)
            elif isinstance(walk_node, ast.Constant) and isinstance(walk_node.value, str):
                if (walk_node.value, getattr(walk_node, "lineno", 0)) in consumed:
                    continue
                refs = _string_file_refs(walk_node.value, getattr(walk_node, "lineno", 0))
                result.file_refs.extend(refs)
        result.dynamic_gaps.extend(_dynamic_in_module(tree))
        return result


class ModuleResolver:
    """Maps dotted module names to repository file paths (deterministic)."""

    def __init__(self, files: list[str]) -> None:
        self._module_map: dict[str, str] = {}
        for path in files:
            if not path.endswith(".py"):
                continue
            for candidate in _module_candidates(path):
                self._module_map.setdefault(candidate, path)

    def resolve(self, module: str) -> str | None:
        return self._module_map.get(module)


def _module_candidates(path: str) -> list[str]:
    stripped = path[:-3] if path.endswith(".py") else path
    parts = [p for p in stripped.split("/") if p]
    out: list[str] = []
    if parts[-1] == "__init__":
        out.append(".".join(parts[:-1]))
    for i in range(len(parts)):
        out.append(".".join(parts[i:]))
    return [c for c in out if c]


def _call_target(func: ast.AST) -> str:
    parts: list[str] = []
    node = func
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
        if len(parts) > 4:
            break
    if isinstance(node, ast.Name):
        parts.append(node.id)
    elif isinstance(node, ast.Call):
        parts.append("<call>")
    else:
        parts.append("<expr>")
    return ".".join(reversed(parts))


def _dynamic_in_call(node: ast.Call) -> list[GapRec]:
    target = _call_target(node.func)
    gaps: list[GapRec] = []
    if target.startswith("importlib") or target == "import_module":
        gaps.append(GapRec("dynamic_import", getattr(node, "lineno", 0), target))
    if target == "__import__":
        gaps.append(GapRec("dynamic_import", getattr(node, "lineno", 0), target))
    if target in ("eval", "exec", "compile"):
        gaps.append(GapRec("eval_exec", getattr(node, "lineno", 0), target))
    if target.startswith("subprocess") or target == "os.system":
        gaps.append(GapRec("subprocess", getattr(node, "lineno", 0), target))
    if target.startswith("getattr"):
        gaps.append(GapRec("reflection", getattr(node, "lineno", 0), target))
    if target.startswith("importlib.import_module"):
        gaps.append(GapRec("plugin_loading", getattr(node, "lineno", 0), target))
    if any(w in target for w in ("load_model", "from_pretrained")) and "<expr>" in target:
        gaps.append(GapRec("external_resource", getattr(node, "lineno", 0), target))
    return gaps


def _dynamic_in_module(tree: ast.AST) -> list[GapRec]:
    gaps: list[GapRec] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in ("importlib", "pkgutil", "pkg_resources"):
                    gaps.append(GapRec("plugin_loading", getattr(node, "lineno", 0),
                                       f"import {alias.name}"))
        if (isinstance(node, ast.Attribute)
                and node.attr in ("__getattr__", "load_dotenv")
                and isinstance(node.value, ast.Name) and node.value.id == "os"):
            gaps.append(GapRec("reflection", getattr(node, "lineno", 0), "os." + node.attr))
    return gaps


def _string_file_refs(value: str, lineno: int) -> list[FileRefRec]:
    if not value or len(value) > 400:
        return []
    lower = value.lower()
    is_path = any(c in value for c in ("/", "\\")) or lower.endswith(_FILE_EXTS)
    if not is_path:
        return []
    mode = "UNKNOWN"
    for verb in _READ_VERBS:
        if verb in lower:
            mode = "READ"
            break
    for verb in _WRITE_VERBS:
        if verb in lower:
            mode = "WRITE"
            break
    return [FileRefRec(path=value, mode=mode, lineno=lineno)]


def _collect_const(const_map: dict[str, str], name: str, node: ast.AST | None) -> None:
    if node is None:
        return
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        const_map[name] = node.value
    elif isinstance(node, ast.Name) and node.id in const_map:
        const_map[name] = const_map[node.id]


def _function_arg_consts(node: ast.FunctionDef | ast.AsyncFunctionDef,
                         module_consts: dict[str, str]) -> dict[str, str]:
    out: dict[str, str] = {}
    defaults = list(node.args.defaults)
    for i, a in enumerate(node.args.args):
        offset = len(node.args.args) - i - 1
        if offset < len(defaults):
            d = defaults[offset]
            if isinstance(d, ast.Constant) and isinstance(d.value, str):
                out[a.arg] = d.value
            elif isinstance(d, ast.Name) and d.id in module_consts:
                out[a.arg] = module_consts[d.id]
        elif a.arg in module_consts:
            out[a.arg] = module_consts[a.arg]
    return out


def _enclosing_function(node: ast.AST, parent_of: dict[ast.AST, ast.AST]) -> str:
    current: ast.AST | None = node
    while current is not None:
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return current.name
        current = parent_of.get(current)
    return ""


def _open_refs(node: ast.Call, result: ParseResult,
               consumed: set[tuple[str, int]],
               const_map: dict[str, str] | None = None) -> None:
    """Record open(path, mode) calls with an accurate READ/WRITE mode."""
    target = _call_target(node.func)
    if target.split(".")[-1] != "open":
        return
    if not node.args:
        return
    path_arg = node.args[0]
    value = None
    lineno = getattr(node, "lineno", 0)
    if isinstance(path_arg, ast.Constant) and isinstance(path_arg.value, str):
        value = path_arg.value
    elif isinstance(path_arg, ast.Name) and const_map and path_arg.id in const_map:
        value = const_map[path_arg.id]
    if value is None:
        return
    mode = "r"
    if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant) \
            and isinstance(node.args[1].value, str):
        mode = node.args[1].value
    else:
        for kw in node.keywords:
            if kw.arg == "mode" and isinstance(kw.value, ast.Constant) \
                    and isinstance(kw.value.value, str):
                mode = kw.value.value
                break
    mode_norm = "WRITE" if any(ch in mode for ch in "wax+") else "READ"
    result.file_refs.append(FileRefRec(path=value, mode=mode_norm, lineno=lineno))
    consumed.add((value, lineno))


class PythonGraphExtractor:
    """Combines parse results + repo file map into nodes/edges/evidence."""

    def __init__(self, repo_files: list[str], repo_root: str) -> None:
        self.repo_files = set(repo_files)
        self.resolver = ModuleResolver(repo_files)
        self.repo_root = repo_root
        self._parsed: dict[str, ParseResult] = {}

    def add_parse(self, relpath: str, result: ParseResult) -> None:
        self._parsed[relpath] = result

    def parse_result(self, relpath: str) -> ParseResult | None:
        return self._parsed.get(relpath)

    def extract(self, ctx: AdapterContext) -> AdapterOutput:
        out = AdapterOutput()
        cov = out.layer(CoverageLayer.STATIC)
        cov.scanned = len(self._parsed)

        file_nodes: dict[str, GraphNode] = {}
        symbol_nodes: dict[tuple[str, str], GraphNode] = {}
        file_ev: dict[str, Evidence] = {}

        # pass 1: create all nodes + evidence (so edges can reference any file)
        for relpath, result in self._parsed.items():
            cov.parsed += 1
            file_node = self._file_node(ctx, relpath)
            out.nodes.append(file_node)
            file_nodes[relpath] = file_node

            if result.dynamic_gaps:
                cov.unknown += 1
                for gap in result.dynamic_gaps:
                    out.gaps.append(
                        f"{relpath}:{gap.lineno}: dynamic/{gap.kind}: {gap.detail}"
                    )

            ev = self._file_evidence(ctx, relpath, result)
            out.evidence.append(ev)
            file_ev[relpath] = ev

            for name, defrec in result.defs.items():
                sym_node = self._symbol_node(ctx, relpath, name, defrec)
                out.nodes.append(sym_node)
                symbol_nodes[(relpath, name)] = sym_node

        # pass 2: edges (all referenced nodes now exist)
        for relpath, result in self._parsed.items():
            file_node = file_nodes[relpath]
            file_ev_id = file_ev[relpath].evidence_id

            for name, defrec in result.defs.items():
                out.edges.append(self._edge(ctx, file_node, symbol_nodes[(relpath, name)],
                                            EdgeRelation.CALLS, ProvenanceType.STATIC,
                                            [file_ev_id],
                                            locator=f"ast:{relpath}:{defrec.lineno}",
                                            dedupe=False))

            # imports
            for imp in result.imports:
                target_path = self.resolver.resolve(imp.module)
                if target_path is None:
                    continue
                target = file_nodes.get(target_path)
                if target is None:
                    continue
                out.edges.append(self._edge(ctx, file_node, target,
                                            EdgeRelation.IMPORTS, ProvenanceType.STATIC,
                                            [file_ev_id],
                                            locator=f"ast:{relpath}:{imp.lineno}"))
                for name in imp.names:
                    sym = symbol_nodes.get((target_path, name))
                    if sym is not None:
                        out.edges.append(self._edge(ctx, file_node, sym,
                                                    EdgeRelation.IMPORTS, ProvenanceType.STATIC,
                                                    [file_ev_id],
                                                    locator=f"ast:{relpath}:{imp.lineno}",
                                                    dedupe=False))

            # calls
            alias_map = _alias_map(result.imports)
            for call in result.calls:
                self._resolve_call(ctx, out, file_node, call, alias_map, relpath,
                                   file_nodes, symbol_nodes, file_ev_id)

            # file refs
            for ref in result.file_refs:
                resolved = self._resolve_path(relpath, ref.path)
                if resolved is None:
                    out.gaps.append(
                        f"{relpath}:{ref.lineno}: unresolved file ref {ref.path!r} (mode={ref.mode})"
                    )
                    cov.unknown += 1
                    continue
                target = file_nodes.get(resolved)
                rel = EdgeRelation.READS if ref.mode != "WRITE" else EdgeRelation.WRITES
                if target is not None:
                    out.edges.append(self._edge(ctx, file_node, target, rel,
                                                ProvenanceType.STATIC, [file_ev_id],
                                                locator=f"ast:{relpath}:{ref.lineno}"))
                else:
                    art = self._file_node(ctx, resolved, node_type=NodeType.ARTIFACT)
                    out.nodes.append(art)
                    out.edges.append(self._edge(ctx, file_node, art, rel,
                                                ProvenanceType.STATIC, [file_ev_id],
                                                locator=f"ast:{relpath}:{ref.lineno}"))
        return out

    def _resolve_call(self, ctx: AdapterContext, out: AdapterOutput, file_node: GraphNode,
                      call: CallRec, alias_map: dict[str, tuple[str | None, str | None]],
                      relpath: str, file_nodes: dict[str, GraphNode],
                      symbol_nodes: dict[tuple[str, str], GraphNode], ev_id: str) -> None:
        parts = call.target.split(".")
        if not parts or parts[0] in ("<call>", "<expr>", "print", "len", "range", "super",
                                     "isinstance", "type", "open", "list", "dict", "set",
                                     "int", "str", "float", "enumerate", "zip", "sum", "min",
                                     "max", "abs", "sorted", "next", "iter", "any", "all",
                                     "getattr", "hasattr", "setattr", "issubclass"):
            return
        first = parts[0]
        parsed = self._parsed.get(relpath)
        local_def = parsed.defs.get(first) if parsed else None
        if first in alias_map:
            module, symbol = alias_map[first]
            if module is not None and symbol is not None:
                target_path = self.resolver.resolve(module)
                if target_path is not None and (target_path, symbol) in symbol_nodes:
                    out.edges.append(self._edge(ctx, file_node, symbol_nodes[(target_path, symbol)],
                                                EdgeRelation.CALLS, ProvenanceType.STATIC, [ev_id],
                                                locator=f"ast:{relpath}:{call.lineno}", dedupe=False))
            elif module is not None:
                target_path = self.resolver.resolve(module)
                if target_path is not None:
                    rest = parts[1:]
                    if len(rest) == 1 and (target_path, rest[0]) in symbol_nodes:
                        out.edges.append(self._edge(
                            ctx, file_node, symbol_nodes[(target_path, rest[0])],
                            EdgeRelation.CALLS, ProvenanceType.STATIC, [ev_id],
                            locator=f"ast:{relpath}:{call.lineno}", dedupe=False))
        elif local_def is not None:
            sym = symbol_nodes.get((relpath, first))
            if sym is not None:
                out.edges.append(self._edge(ctx, file_node, sym, EdgeRelation.CALLS,
                                            ProvenanceType.STATIC, [ev_id],
                                            locator=f"ast:{relpath}:{call.lineno}", dedupe=False))

    def _resolve_path(self, from_rel: str, ref_path: str) -> str | None:
        ref = ref_path.replace("\\", "/").lstrip("/")
        if not ref:
            return None
        base_dir = posixpath.dirname(from_rel)
        candidates = [posixpath.normpath(posixpath.join(base_dir, ref)), ref]
        for cand in candidates:
            if cand in self.repo_files:
                return cand
        return None

    def _file_node(self, ctx: AdapterContext, relpath: str,
                   node_type: NodeType = NodeType.FILE) -> GraphNode:
        return GraphNode(node_id=ids.node_id(node_type.value, relpath), project_id=ctx.project_id,
                         node_type=node_type, label=relpath, ref=relpath)

    def _symbol_node(self, ctx: AdapterContext, relpath: str, name: str,
                     defrec: DefRec) -> GraphNode:
        ref = f"{relpath}:{name}"
        return GraphNode(node_id=ids.node_id(NodeType.SYMBOL.value, ref), project_id=ctx.project_id,
                         node_type=NodeType.SYMBOL, label=ref, ref=ref,
                         data={"kind": defrec.kind, "lineno": defrec.lineno})

    def _file_evidence(self, ctx: AdapterContext, relpath: str, result: ParseResult) -> Evidence:
        payload: dict[str, Any] = {
            "imports": [i.module for i in result.imports],
            "defs": list(result.defs.keys()),
            "calls": [c.target for c in result.calls],
            "file_refs": [{"path": r.path, "mode": r.mode} for r in result.file_refs],
            "dynamic_gaps": [g.kind for g in result.dynamic_gaps],
        }
        locator = f"ast:file:{relpath}"
        return Evidence(
            evidence_id=ids.evidence_id(EvidenceSourceType.PYTHON_AST.value, locator,
                                        result.source_hash, ctx.extractor),
            project_id=ctx.project_id, source_type=EvidenceSourceType.PYTHON_AST,
            locator=locator, content_hash=result.source_hash, extractor=ctx.extractor,
            payload=payload, snapshot_id=ctx.snapshot_id,
        )

    def _edge(self, ctx: AdapterContext, src: GraphNode, tgt: GraphNode,
              relation: EdgeRelation, provenance: ProvenanceType, evidence_ids: list[str],
              locator: str = "", dedupe: bool = True) -> GraphEdge:
        if dedupe:
            edge_id = ids.edge_id(src.node_id, tgt.node_id, relation.value)
        else:
            edge_id = ids.edge_id(src.node_id, tgt.node_id, f"{relation.value}|{locator}")
        return GraphEdge(edge_id=edge_id, project_id=ctx.project_id, source_id=src.node_id,
                         target_id=tgt.node_id, relation=relation, provenance_type=provenance,
                         evidence_ids=evidence_ids, locator=locator,
                         snapshot_id=ctx.snapshot_id, extractor_version=ctx.extractor)


def _alias_map(imports: list[ImportRec]) -> dict[str, tuple[str | None, str | None]]:
    m: dict[str, tuple[str | None, str | None]] = {}
    for imp in imports:
        if imp.is_from:
            m[imp.alias] = (imp.module, imp.names[0] if imp.names else None)
        else:
            m[imp.alias] = (imp.module, None)
    return m
