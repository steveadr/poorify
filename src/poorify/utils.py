import os
import subprocess
import re


def find_workspace_anchor(target_file: str) -> str | None:
    abs_path = os.path.abspath(target_file)
    current = os.path.dirname(abs_path)
    markers = [
        "package.json", "Cargo.toml", "go.mod",
        "requirements.txt", "pyproject.toml", "pom.xml",
        "build.gradle", "CMakeLists.txt"
    ]
    while True:
        for marker in markers:
            if os.path.exists(os.path.join(current, marker)):
                return current
        parent = os.path.dirname(current)
        if parent == current:
            return None
        current = parent


def git_diff(target_file: str) -> str:
    try:
        result = subprocess.run(
            ["git", "diff", target_file],
            capture_output=True, text=True, cwd=os.getcwd(), timeout=30)
        return result.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return ""


def sample_adjacent_files(anchor_path: str, max_samples: int = 3) -> list[str]:
    samples = []
    try:
        entries = [os.path.join(anchor_path, e) for e in os.listdir(anchor_path)]
        code_files = [
            e for e in entries if os.path.isfile(e)
            and not e.endswith((".md", ".txt", ".db", ".bak"))
        ][:max_samples]
        for filepath in code_files:
            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                samples.append(f.read())
    except Exception:
        pass
    return samples


def grep_files(pattern: str, root: str,
               max_results: int = 10) -> list[tuple[str, int, str]]:
    results = []
    try:
        proc = subprocess.run(
            ["rg", "-n", pattern, "--max-count", str(max_results), root],
            capture_output=True, text=True, timeout=30)
        for line in proc.stdout.splitlines():
            parts = line.split(":", 2)
            if len(parts) >= 2:
                results.append((parts[0], int(parts[1]),
                                parts[2] if len(parts) > 2 else ""))
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return results


def backup_file(filepath: str) -> str:
    bak_path = os.path.join(
        os.getcwd(), ".poorify", "backup",
        os.path.basename(filepath) + ".bak")
    os.makedirs(os.path.dirname(bak_path), exist_ok=True)
    subprocess.run(
        ["cp", filepath, bak_path] if os.name != "nt"
        else ["copy", filepath, bak_path],
        capture_output=True, shell=(os.name == "nt"))
    return bak_path


def restore_backup(bak_path: str, original_path: str) -> None:
    subprocess.run(
        ["cp", bak_path, original_path] if os.name != "nt"
        else ["copy", bak_path, original_path],
        capture_output=True, shell=(os.name == "nt"))


def parse_search_replace(agent_output: str) -> list[tuple[str, str]]:
    patches = []
    pattern = r'<<<<<<< SEARCH\n(.*?)\n=======\n(.*?)\n>>>>>>> REPLACE'
    for match in re.finditer(pattern, agent_output, re.DOTALL):
        old = match.group(1)
        new = match.group(2)
        patches.append((old, new))
    return patches


def apply_patch(filepath: str, old: str, new: str) -> bool:
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()
    if old not in content:
        return False
    content = content.replace(old, new, 1)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    return True
