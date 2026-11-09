"""스킬 코드 트리의 약속을 지킨다. 구조를 일부러 바꾸면 이 시험도 함께 바꾼다."""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / ".claude/skills/computer/scripts"
PACKAGE = SCRIPTS / "computer"

UNITS = {"agent_desktop", "doctor"}

ALLOWED = {
    "agent_desktop": set(),
    "doctor": {"agent_desktop"},
}
CLI_ALLOWED = {"agent_desktop", "doctor"}


def unit_of(path: Path) -> str:
    return path.relative_to(PACKAGE).parts[0].removesuffix(".py")


def _module_exists(package: Path, parts) -> bool:
    target = package.joinpath(*parts)
    return target.is_dir() or target.with_suffix(".py").exists()


def imports_in(source: str, package_parts=(), package: Path = PACKAGE):
    """소스의 모든 import를 패키지 안 경로로 돌려준다. 함수 안 import도, `from x import 하위모듈`의 이름도 본다."""
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            for alias in node.names:
                parts = alias.name.split(".")
                if parts[0] == "computer":
                    yield tuple(parts[1:])
        elif isinstance(node, ast.ImportFrom):
            base = list(package_parts)[: len(package_parts) - node.level + 1] if node.level else []
            parts = base + (node.module.split(".") if node.module else [])
            if not parts or parts[0] != "computer":
                continue
            inner = tuple(parts[1:])
            for alias in node.names:
                if inner and not _module_exists(package, (*inner, alias.name)):
                    yield inner  # 유닛에서 이름을 가져온다
                else:
                    yield (*inner, alias.name)


def imports_of(path: Path):
    return imports_in(path.read_text(encoding="utf-8"), path.relative_to(SCRIPTS).parts[:-1])


def python_files():
    return sorted(SCRIPTS.rglob("*.py"))


def test_top_level_names_are_fixed():
    names = {p.name for p in SCRIPTS.iterdir() if p.name != "__pycache__"}
    assert names == {"cli.py", "computer"}


def test_units_exist():
    found = {unit_of(p) for p in PACKAGE.rglob("*.py") if p.name != "__init__.py" or p.parent != PACKAGE}
    assert found == UNITS


def test_import_edges_are_the_agreed_ones():
    for path in PACKAGE.rglob("*.py"):
        if path == PACKAGE / "__init__.py":
            continue
        unit = unit_of(path)
        for target in imports_of(path):
            if target and target[0] != unit:
                assert target[0] in ALLOWED[unit], f"{path}: {unit} -> {target[0]}"


def test_cli_only_calls_feature_units():
    for target in imports_of(SCRIPTS / "cli.py"):
        assert target and target[0] in CLI_ALLOWED, f"cli.py -> {target}"


def test_nothing_reaches_past_a_unit_interface():
    """하위 패키지의 안쪽 모듈은 그 패키지 바깥에서 부르지 못한다."""
    for path in [SCRIPTS / "cli.py", *PACKAGE.rglob("*.py")]:
        unit = unit_of(path) if path.is_relative_to(PACKAGE) and path != PACKAGE / "__init__.py" else None
        for target in imports_of(path):
            if target and target[0] != unit:
                assert len(target) == 1, f"{path}: {target}"
    for path in Path(__file__).parent.rglob("*.py"):
        for target in imports_in(path.read_text(encoding="utf-8")):
            assert len(target) <= 1, f"{path}: computer.{'.'.join(target)}"


def test_nothing_edits_sys_path():
    for path in python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr == "path":
                value = node.value
                if isinstance(value, ast.Name) and value.id == "sys":
                    raise AssertionError(f"{path}: sys.path를 건드린다")


def test_cli_declares_its_own_environment():
    text = "\n".join((SCRIPTS / "cli.py").read_text(encoding="utf-8").split("\n", 10))
    assert "# /// script" in text and 'requires-python = ">=3.12"' in text
    assert "dependencies = []" in text


def test_the_checker_sees_every_import_form(tmp_path):
    package = tmp_path / "computer"
    (package / "agent_desktop").mkdir(parents=True)
    (package / "agent_desktop" / "probe.py").write_text("", encoding="utf-8")
    seen = lambda source: list(imports_in(source, package=package))  # noqa: E731
    assert seen("from computer.agent_desktop import probe") == [("agent_desktop", "probe")]
    assert seen("from computer.agent_desktop.probe import x") == [("agent_desktop", "probe")]
    assert seen("import computer.agent_desktop.probe") == [("agent_desktop", "probe")]
    assert seen("from computer import agent_desktop") == [("agent_desktop",)]
    assert seen("from computer.agent_desktop import run") == [("agent_desktop",)]
