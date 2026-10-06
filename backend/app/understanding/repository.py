"""Bounded static analysis of explicitly permitted repository files. Never executes source."""
import json
import os
from pathlib import Path
import re
import stat
import time
from uuid import uuid4
from .rules import Collector, STACK, VENDORS, FEATURES, DATA, CAPABILITIES, SECRET, safe_lines
from .schemas import AccessMode, Evidence, RepoAnalysisResult, RepositoryRequest

IGNORED = {".git", "node_modules", "dist", "build", "target", "vendor", "cache", ".cache",
    "__pycache__", ".venv", "venv", ".testenv", ".testdeps", ".next", "coverage", ".ssh", ".aws"}
EXTENSIONS = {".py", ".js", ".jsx", ".ts", ".tsx", ".vue", ".json", ".toml", ".yaml", ".yml", ".md", ".txt", ".html", ".sql", ".lock"}
MANIFESTS = {"package.json", "requirements.txt", "requirements-dev.txt", "pyproject.toml", "poetry.lock"}
MAX_FILES, MAX_BYTES, MAX_TOTAL, MAX_ENTRIES = 1000, 256_000, 8_000_000, 20000


def ignored(name):
    lower = name.lower()
    return (lower in IGNORED or lower.startswith(".env") or SECRET.search(lower) is not None
        or lower.endswith((".pem", ".key", ".p12", ".pfx", ".crt", ".db", ".sqlite", ".sqlite3")))


def linked(path):
    return path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction())


def validate_root(request: RepositoryRequest, allowed_roots=None):
    if request.analysis_mode == AccessMode.NO_REPOSITORY:
        return None
    roots = allowed_roots if allowed_roots is not None else os.getenv("UNDERSTANDING_REPOSITORY_ROOTS", "").split(os.pathsep)
    candidate = Path(request.repository_path).absolute()
    if any(linked(p) for p in (candidate, *candidate.parents)):
        raise ValueError("Linked paths are not permitted")
    root = candidate.resolve(strict=True)
    if not root.is_dir() or not any(root.is_relative_to(Path(p).resolve()) for p in roots if p):
        raise ValueError("Repository is outside configured roots")
    if any(ignored(p) for p in root.parts[1:]):
        raise ValueError("Sensitive repository path")
    for value in request.selected_paths:
        path = Path(value)
        if not value or path.is_absolute() or ".." in path.parts or any(ignored(p) for p in path.parts):
            raise ValueError("Invalid selected path")
        selected = root / path
        if not selected.exists() or not selected.resolve().is_relative_to(root):
            raise ValueError("Selected path is unavailable")
        if any(linked(p) for p in (selected, *selected.parents)):
            raise ValueError("Linked selected paths are not permitted")
    return root


def metadata_file(path):
    name = path.name.lower()
    return name in MANIFESTS or name.startswith("readme") or name in {"dockerfile", "docker-compose.yml", "docker-compose.yaml", "compose.yml", "tsconfig.json", "vercel.json"}


def analyze_repository(request: RepositoryRequest, allowed_roots=None):
    root = validate_root(request, allowed_roots)
    collector = Collector()
    collector.description(request.product_description)
    limitations = ["Static clues do not prove runtime behavior; confidence values are heuristic, not calibrated probabilities."]
    complete = request.analysis_mode in (AccessMode.FULL, AccessMode.SELECTED_PATHS)
    count = total = entries = 0
    started = time.monotonic()
    secret_seen = False
    if root is not None:
        selected = [root / p for p in request.selected_paths] if request.analysis_mode == AccessMode.SELECTED_PATHS else [root]
        pending = list(selected)
        seen = set()
        while pending:
            if entries >= MAX_ENTRIES or count >= MAX_FILES or total >= MAX_TOTAL or time.monotonic() - started > 30:
                complete = False
                limitations.append("Scan limit reached; unexamined content remains unknown.")
                break
            path = pending.pop()
            entries += 1
            if path in seen:
                continue
            seen.add(path)
            try:
                if ignored(path.name) or linked(path) or not path.resolve().is_relative_to(root):
                    continue
                if path.is_dir():
                    # Bound directory enumeration as well as file reads.
                    with os.scandir(path) as children:
                        for child in children:
                            if len(pending) + entries >= MAX_ENTRIES:
                                complete = False
                                limitations.append("Directory entry limit reached.")
                                break
                            if not ignored(child.name):
                                pending.append(Path(child.path))
                    continue
                metadata = metadata_file(path)
                if request.analysis_mode == AccessMode.METADATA_ONLY and not metadata:
                    continue
                if path.suffix.lower() not in EXTENSIONS and path.name.lower() != "dockerfile":
                    continue
                info = path.stat(follow_symlinks=False)
                if not stat.S_ISREG(info.st_mode) or info.st_nlink > 1:
                    continue
                if info.st_size > MAX_BYTES:
                    complete = False
                    continue
                flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0)
                descriptor = os.open(path, flags)
                with os.fdopen(descriptor, "rb") as stream:
                    actual = os.fstat(stream.fileno())
                    if not stat.S_ISREG(actual.st_mode) or actual.st_nlink > 1 or (actual.st_dev, actual.st_ino) != (info.st_dev, info.st_ino):
                        complete = False
                        continue
                    raw = stream.read(MAX_BYTES + 1)
                total += len(raw)
                if len(raw) > MAX_BYTES or total > MAX_TOTAL or b"\0" in raw:
                    complete = False
                    continue
                text = raw.decode("utf-8")
                count += 1
                relative = path.relative_to(root).as_posix()
                kind = "DEPENDENCY" if path.name.lower() in MANIFESTS else "METADATA" if metadata else "CODE"
                source = {"type": kind, "file": relative}
                language = {".py": "Python", ".ts": "TypeScript", ".tsx": "TypeScript", ".js": "JavaScript", ".jsx": "JavaScript"}.get(path.suffix)
                if language:
                    collector.add("stack", language, source, .9)
                if path.name.lower() == "package.json":
                    collector.add("stack", "Node.js", source, .85)
                    # Only package names establish dependency facts, not descriptions/scripts.
                    try:
                        manifest = json.loads(text)
                        for section in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
                            deps = manifest.get(section, {})
                            if isinstance(deps, dict):
                                for package in deps:
                                    if not SECRET.search(package):
                                        for group, rules in (("stack", STACK), ("vendors", VENDORS)):
                                            collector.scan(group, rules, package, source, .95 if section == "dependencies" else .75)
                    except (ValueError, AttributeError):
                        complete = False
                    continue
                if path.name.lower() == "dockerfile":
                    collector.add("stack", "Docker", source, .95)
                for line_number, line, sensitive in safe_lines(text):
                    secret_seen |= sensitive
                    if not line:
                        continue
                    line_source = dict(source, line_start=line_number, line_end=line_number)
                    import_or_dep = kind == "DEPENDENCY" or bool(re.search(r"\b(?:import|from|require)\b", line))
                    for group, rules in (("stack", STACK), ("vendors", VENDORS)):
                        collector.scan(group, rules, line, line_source, .9 if import_or_dep else .45,
                            "PRESENT" if import_or_dep else "PARTIAL")
                    # A regex match is an implementation clue, not proof of working capability.
                    if kind != "DEPENDENCY":
                        for group, rules in (("features", FEATURES), ("data_types", DATA), ("capabilities", CAPABILITIES)):
                            collector.scan(group, rules, line, line_source, .65 if kind == "CODE" else .4, "PARTIAL")
            except (OSError, UnicodeError):
                complete = False
        if request.analysis_mode == AccessMode.METADATA_ONLY:
            limitations.append("Only allowlisted metadata files were read; implementation capabilities remain unknown.")
        if request.analysis_mode == AccessMode.SELECTED_PATHS:
            limitations.append("Findings and non-detections apply only to selected paths.")
    else:
        limitations.append("NO_REPOSITORY: no filesystem access; only optional user-described clues.")
    if secret_seen:
        limitations.append("Potential secret/configuration detected.")
    complete = complete and count > 0
    collector.evidence.append(Evidence(evidence_id="scope", type="SCAN_SCOPE",
        reason=f"Examined {count} eligible files under {request.analysis_mode.value}; ignored sensitive/generated files. Non-detection is limited to this scope."))
    stack = list(collector.facts.get("stack", {}).values())
    return RepoAnalysisResult(repository_id=uuid4().hex, analysis_mode=request.analysis_mode,
        project_summary="Static product clues: " + ", ".join(collector.facts.get("features", {})) if collector.facts.get("features") else "UNKNOWN",
        detected_stack=[f.name for f in stack], stack_facts=stack,
        features=collector.complete("features", FEATURES, complete), data_types=list(collector.facts.get("data_types", {}).values()),
        vendors=list(collector.facts.get("vendors", {}).values()),
        capabilities={f.name: f for f in collector.complete("capabilities", CAPABILITIES, complete)},
        evidence=collector.evidence, files_scanned=count, coverage_complete=complete,
        confidence=.65 if complete else .35 if count else 0, limitations=list(dict.fromkeys(limitations)))
