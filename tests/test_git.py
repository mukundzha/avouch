import ast
import subprocess
from unittest.mock import Mock, patch

import pytest

from scrut.cli import (
    get_reviewable_files,
    get_depth,
    read_file,
    get_changed_files,
    is_gitrepo,
    analyze_file,
    check_depth,
    main,
)
from scrut.config.loader import load_config, merge_limits
from scrut.config.default import DEFAULT_LIMITS


@patch("subprocess.run")
def test_is_gitrepo_true(mock_run):

    mock_run.return_value = Mock(returncode=0)

    assert is_gitrepo() is True


@patch("subprocess.run")
def test_is_gitrepo_false(mock_run):

    mock_run.return_value = Mock(returncode=1)

    assert is_gitrepo() is False


@patch("subprocess.run")
def test_get_changed_files(mock_run):

    mock_run.return_value = Mock(
        stdout="main.py\nhello.py\nREADME.md\n",
        returncode=0,
    )

    assert get_changed_files() == ["main.py", "hello.py", "README.md"]


def test_get_reviewable_files(tmp_path):

    py1 = tmp_path / "a.py"
    py2 = tmp_path / "b.py"
    txt = tmp_path / "c.txt"
    missing = tmp_path / "d.py"

    py1.write_text("")
    py2.write_text("")
    txt.write_text("")

    result = get_reviewable_files([str(py1), str(txt), str(py2), str(missing)])

    assert result == [str(py1), str(py2)]


def test_read_file(tmp_path):

    file = tmp_path / "sample.py"
    file.write_text("print('Hello')")

    assert read_file(file) == "print('Hello')"


def test_read_file_missing(tmp_path):

    assert read_file(tmp_path / "missing.py") is None


def test_get_depth_no_nesting():

    tree = ast.parse("def foo():\n    pass\n")

    assert get_depth(tree.body[0]) == 0


def test_get_depth_nested():

    tree = ast.parse(
        "def foo():\n"
        "    if True:\n"
        "        while True:\n"
        "            for i in range(5):\n"
        "                pass\n"
    )

    assert get_depth(tree.body[0]) == 3


def test_get_depth_all_block_nodes():

    cases = [
        ("def foo():\n    if True:\n        pass\n", 1),
        ("def foo():\n    for i in range(3):\n        pass\n", 1),
        ("def foo():\n    while True:\n        pass\n", 1),
        ("async def foo():\n    async for i in aiter():\n        pass\n", 1),
        ("def foo():\n    with open('f') as f:\n        pass\n", 1),
        ("async def foo():\n    async with conn:\n        pass\n", 1),
        (
            "def foo():\n"
            "    try:\n"
            "        pass\n"
            "    except Exception:\n"
            "        pass\n",
            1,
        ),
        ("def foo():\n    match x:\n        case 1:\n            pass\n", 1),
    ]

    for code, expected in cases:
        assert get_depth(ast.parse(code).body[0]) == expected


def test_get_depth_mixed_chain():

    code = (
        "def foo():\n"
        "    if True:\n"
        "        for i in range(3):\n"
        "            with open('f') as f:\n"
        "                try:\n"
        "                    match x:\n"
        "                        case 1:\n"
        "                            pass\n"
        "                except Exception:\n"
        "                    pass\n"
    )

    assert check_depth(code) == 5


def test_get_depth_sibling_blocks():

    code = (
        "def foo():\n"
        "    if True:\n"
        "        pass\n"
        "    for i in range(3):\n"
        "        pass\n"
        "    with open('f') as f:\n"
        "        pass\n"
    )

    assert check_depth(code) == 1


def test_get_depth_non_block_constructs():

    code = (
        "def foo():\n"
        "    items = [x for x in range(10)]\n"
        "    double = lambda x: x * 2\n"
        "    total = sum(x for x in range(5))\n"
        "    def inner():\n"
        "        return 1\n"
    )

    assert check_depth(code) == 0


def test_get_depth_nested_function_blocks_count_from_same_level():

    code = (
        "def outer():\n"
        "    def inner():\n"
        "        if True:\n"
        "            pass\n"
        "    return inner\n"
    )

    assert check_depth(code) == 1


def test_check_depth_returns_depth():

    code = "def foo():\n    if True:\n        for i in range(3):\n            pass\n"

    assert check_depth(code) == 2


def test_check_depth_no_function_raises():

    with pytest.raises(ValueError):
        check_depth("x = 1\n")


def test_analyze_file_nesting_warning(tmp_path):

    deep = tmp_path / "deep.py"
    deep.write_text(
        "def foo():\n"
        "    if True:\n"
        "        for i in range(3):\n"
        "            with open('f') as f:\n"
        "                pass\n"
    )

    limits = {**DEFAULT_LIMITS, "max_nesting": 2}

    funcs, files, classes = analyze_file(str(deep), limits)

    assert funcs[0]["nesting_depth"] == 3
    assert funcs[0]["issues"] == [
        {"severity": "WARNING", "message": "Nesting too deep (3/2)"}
    ]


def test_load_config_default(tmp_path, monkeypatch):

    monkeypatch.chdir(tmp_path)

    assert load_config()["limits"] == DEFAULT_LIMITS


def test_load_config_with_toml(tmp_path, monkeypatch):

    (tmp_path / "scrut.toml").write_text("[limits]\nmax_parameters = 3\n")
    monkeypatch.chdir(tmp_path)

    config = load_config()["limits"]

    assert config["max_parameters"] == 3
    assert config["max_nesting"] == 4


def test_merge_limits():

    merged = merge_limits({"max_parameters": 2})

    assert merged["max_parameters"] == 2
    assert merged["max_file_lines"] == 400


def test_main_reviews_all_files(tmp_path, monkeypatch, capsys):

    good = tmp_path / "good.py"
    bad = tmp_path / "bad.py"
    broken = tmp_path / "broken.py"

    good.write_text("def ok():\n    pass\n")
    bad.write_text("def bad(a, b):\n    if True:\n        pass\n")
    broken.write_text("def broken(\n")

    monkeypatch.chdir(tmp_path)
    (tmp_path / "scrut.toml").write_text(
        "[limits]\n"
        "max_parameters = 1\n"
        "max_nesting = 1\n"
        "max_function_lines = 1\n"
        "max_class_lines = 10\n"
        "max_file_lines = 5\n"
    )
    monkeypatch.setattr(
        "scrut.cli.subprocess.run",
        lambda *a, **k: Mock(returncode=0, stdout="good.py\nbad.py\nbroken.py\n"),
    )

    main()

    out = capsys.readouterr().out

    assert "good.py" in out
    assert "bad.py" in out
    assert "broken.py" in out
    assert "Python syntax error" in out
    assert "Too many parameters (2/1)" in out
    assert "Files Reviewed     : 3" in out


def test_analyze_file_list_with_syntax_error(tmp_path):

    good = tmp_path / "good.py"
    clean = tmp_path / "clean.py"
    broken = tmp_path / "broken.py"

    good.write_text("def ok():\n    pass\n")
    clean.write_text("x = 1\n")
    broken.write_text("def broken(\n")

    results = [
        analyze_file(str(path), DEFAULT_LIMITS) for path in [good, clean, broken]
    ]

    assert len(results) == 3

    assert results[0][1][0]["issues"] == []
    assert results[1][1][0]["issues"] == []
    assert results[2][1][0]["issues"] == [
        {"severity": "ERROR", "message": "Python syntax error"}
    ]

    assert results[0][0][0]["name"] == "ok"
    assert results[2][0] == []


def test_main_integration_multiple_changed_files(tmp_path, monkeypatch, capsys):

    def git(*args):
        subprocess.run(["git", *args], cwd=tmp_path, check=True, capture_output=True)

    git("init", "-q")
    git("config", "user.email", "test@example.com")
    git("config", "user.name", "Test")

    (tmp_path / "a.py").write_text("def a():\n    pass\n")
    (tmp_path / "b.py").write_text("def b():\n    pass\n")
    (tmp_path / "c.py").write_text("def c():\n    pass\n")
    (tmp_path / "notes.txt").write_text("notes\n")

    git("add", "-A")
    git("-c", "commit.gpgsign=false", "commit", "-q", "-m", "initial")

    (tmp_path / "a.py").write_text("def a():\n    return 1\n")
    (tmp_path / "c.py").write_text("def c():\n    return 2\n")
    (tmp_path / "d.py").write_text("def d():\n    pass\n")
    (tmp_path / "notes.txt").write_text("updated\n")

    git("add", "-A")

    monkeypatch.chdir(tmp_path)

    main()

    out = capsys.readouterr().out

    assert "a.py" in out
    assert "c.py" in out
    assert "d.py" in out
    assert "Files Reviewed     : 3" in out
