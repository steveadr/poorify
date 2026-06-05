import re
import ast
import os
from . import db

BRANCH_KEYWORDS = [
    "if", "else", "elif", "match", "case", "for", "while",
    "switch", "catch", "except", "?"
]


def count_complexity_python(filepath: str) -> int:
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        source = f.read()
    try:
        tree = ast.parse(source)
        count = 0
        for node in ast.walk(tree):
            if isinstance(node, (ast.If, ast.For, ast.While,
                                 ast.Try, ast.With, ast.AsyncFor,
                                 ast.AsyncWith)):
                count += 1
            elif isinstance(node, ast.Match):
                count += len(node.cases)
        return count
    except SyntaxError:
        return _count_complexity_fallback(source)


def count_complexity_generic(filepath: str) -> int:
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        source = f.read()
    return _count_complexity_fallback(source)


def _count_complexity_fallback(source: str) -> int:
    count = 0
    for kw in BRANCH_KEYWORDS:
        pattern = rf'\b{re.escape(kw)}\b'
        count += len(re.findall(pattern, source, re.IGNORECASE))
    return count


def route_file(filepath: str) -> str:
    ext = os.path.splitext(filepath)[1].lower()
    if ext == ".py":
        complexity = count_complexity_python(filepath)
    else:
        complexity = count_complexity_generic(filepath)

    mode = "FULL" if complexity >= 5 else "SKELETON"
    db.set_router_entry(filepath, complexity, mode)
    return mode


def skeletonize_file(filepath: str) -> str:
    ext = os.path.splitext(filepath)[1].lower()
    if ext == ".py":
        return _skeletonize_python(filepath)
    return _skeletonize_generic(filepath)


def _skeletonize_python(filepath: str) -> str:
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        source = f.read()
    try:
        tree = ast.parse(source)
        lines = source.splitlines(keepends=True)

        removals = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                                 ast.ClassDef)):
                body = node.body
                if not body:
                    continue
                first = body[0]
                last = body[-1]
                start = first.lineno - 1
                end = last.end_lineno if hasattr(last,
                                                 "end_lineno") else last.lineno
                removals.append((start, end))

        removals.sort(reverse=True)
        for start, end in removals:
            for i in range(start, min(end, len(lines))):
                stripped = lines[i].strip()
                if stripped and not stripped.startswith((
                        "#", "'''", '"""', "def ", "async def ", "class ",
                        "    ", "\t", "@")):
                    lines[i] = _indent(lines[i]) + "# ...\n"

        return "".join(lines)
    except SyntaxError:
        return _skeletonize_generic(filepath)


def _skeletonize_generic(filepath: str) -> str:
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        source = f.read()
    pattern = r'\{[^}]*\}'
    return re.sub(pattern, '{\n    // ...\n}', source)


def _indent(line: str) -> str:
    return re.match(r'^\s*', line).group() if re.match(r'^\s*',
                                                        line) else ""


def analyze_file(filepath: str) -> dict:
    ext = os.path.splitext(filepath)[1].lower()
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        source = f.read()
    size = len(source.encode("utf-8"))
    functions = classes = 0
    imports = []
    if ext == ".py":
        try:
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    functions += 1
                elif isinstance(node, ast.ClassDef):
                    classes += 1
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imports.append(node.module)
        except SyntaxError:
            pass

    _cx_fn = count_complexity_python if ext == ".py" else count_complexity_generic
    complexity = _cx_fn(filepath)
    entry = db.get_router_entry(filepath)
    mode = entry["ingestion_mode"] if entry else "unrouted"
    return {
        "size": size,
        "complexity": complexity,
        "mode": mode,
        "functions": functions,
        "classes": classes,
        "imports": imports,
    }


def get_skeleton_savings(filepath: str) -> int:
    entry = db.get_router_entry(filepath)
    if not entry or entry["ingestion_mode"] == "FULL":
        return 0
    full_size = os.path.getsize(filepath)
    skeleton = skeletonize_file(filepath)
    skeleton_size = len(skeleton.encode("utf-8"))
    return max(0, full_size - skeleton_size)
