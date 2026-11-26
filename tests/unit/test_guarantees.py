"""The register docs/GUARANTEES.md must cite only tests and files that exist."""
import ast
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
TESTS = ROOT / "tests"
ROW = re.compile(r"^\| (G\d\d) \| (.+?) \| (.+?) \| (.+?) \|$")


def _rows():
    text = (ROOT / "docs" / "GUARANTEES.md").read_text(encoding="utf-8")
    return [ROW.match(line).groups() for line in text.splitlines() if line.startswith("| G")]


def _test_functions(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {node.name for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test")}


def test_register_rows_are_well_formed_and_numbered():
    rows = _rows()
    ids = [row[0] for row in rows]
    assert ids == [f"G{i:02d}" for i in range(1, len(ids) + 1)]
    assert len(rows) >= 30


def test_every_guarantee_cites_existing_files_and_tests():
    problems = []
    for gid, _, kept_by, tests in _rows():
        for name in re.findall(r"`([^`]+)`", kept_by):
            if not (ROOT / name).is_file():
                problems.append(f"{gid}: missing file {name}")
        cited = re.findall(r"`([^`]+)`", tests)
        if not cited:
            problems.append(f"{gid}: no test")
        for item in cited:
            file, _, function = item.partition("::")
            path = TESTS / file
            if not path.is_file() or function not in _test_functions(path):
                problems.append(f"{gid}: missing test {item}")
    assert problems == []
