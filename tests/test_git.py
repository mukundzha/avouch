import ast
import subprocess
from unittest.mock import Mock, patch

from scrut.analyzer import analyze_file, get_depth, read_file
from scrut.git import get_changed_files, get_reviewable_files, is_gitrepo
from scrut.report import generate_report
from scrut.cli import main
from scrut.config.default import DEFAULT_LIMITS
from scrut.config.loader import load_config, merge_limits


@patch("scrut.git.subprocess.run")
def test_is_gitrepo_true(mock_run):

    mock_run.return_value = Mock(returncode=0)

    assert is_gitrepo() is True


@patch("scrut.git.subprocess.run")
def test_is_gitrepo_false(mock_run):

    mock_run.return_value = Mock(returncode=1)

    assert is_gitrepo() is False


@patch("scrut.git.subprocess.run")
def test_get_changed_files(mock_run):

    mock_run.return_value = Mock(stdout="a.py\nb.py\nREADME.md\n", returncode=0)

    assert get_changed_files() == ["a.py", "b.py", "README.md"]


def test_get_reviewable_files(tmp_path):

    py1 = tmp_path / "a.py"
    py2 = tmp_path / "b.py"
    txt = tmp_path / "c.txt"
    missing = tmp_path / "d.py"

    py1.write_text("")
    py2.write_text("")
    txt.write_text("")

    assert get_reviewable_files([str(py1), str(txt), str(py2), str(missing)]) == [
        str(py1),
        str(py2),
    ]


def test_read_file(tmp_path):

    file = tmp_path / "a.py"
    file.write_text("print('hi')")

    assert read_file(str(file)) == "print('hi')"


def test_read_file_missing(tmp_path):

    assert read_file(str(tmp_path / "nope.py")) is None


def test_get_depth_zero():

    tree = ast.parse("def f():\n    pass\n")

    assert get_depth(tree.body[0]) == 0


def test_get_depth_counts_block_nodes():

    cases = [
        ("def f():\n    if True:\n        pass\n", 1),
        ("def f():\n    for i in range(3):\n        pass\n", 1),
        ("def f():\n    while True:\n        pass\n", 1),
        ("async def f():\n    async for i in aiter():\n        pass\n", 1),
        ("def f():\n    with open('f') as f:\n        pass\n", 1),
        ("async def f():\n    async with c:\n        pass\n", 1),
        (
            "def f():\n"
            "    try:\n"
            "        pass\n"
            "    except Exception:\n"
            "        pass\n",
            1,
        ),
        ("def f():\n    match x:\n        case 1:\n            pass\n", 1),
    ]

    for code, expected in cases:
        assert get_depth(ast.parse(code).body[0]) == expected


def test_get_depth_chain():

    tree = ast.parse(
        "def f():\n"
        "    if True:\n"
        "        for i in range(3):\n"
        "            with open('f') as f:\n"
        "                pass\n"
    )

    assert get_depth(tree.body[0]) == 3


def test_get_depth_siblings_do_not_stack():

    tree = ast.parse(
        "def f():\n"
        "    if True:\n"
        "        pass\n"
        "    for i in range(3):\n"
        "        pass\n"
    )

    assert get_depth(tree.body[0]) == 1


def test_analyze_file_clean(tmp_path):

    file = tmp_path / "clean.py"
    file.write_text("def ok():\n    pass\n")

    funcs, files, classes = analyze_file(str(file), DEFAULT_LIMITS)

    assert funcs[0]["name"] == "ok"
    assert funcs[0]["file"] == str(file)
    assert files[0]["issues"] == []
    assert classes == []


def test_analyze_file_syntax_error(tmp_path):

    file = tmp_path / "broken.py"
    file.write_text("def broken(\n")

    funcs, files, classes = analyze_file(str(file), DEFAULT_LIMITS)

    assert funcs == []
    assert files[0]["issues"] == [
        {"severity": "ERROR", "message": "Python syntax error"}
    ]


def test_analyze_file_unreadable(tmp_path):

    funcs, files, classes = analyze_file(str(tmp_path / "missing.py"), DEFAULT_LIMITS)

    assert funcs == []
    assert files[0]["issues"] == [
        {"severity": "ERROR", "message": "Could not read file"}
    ]


def test_analyze_file_warnings(tmp_path):

    file = tmp_path / "warn.py"
    file.write_text("def f(a, b):\n    if True:\n        pass\n")

    limits = {
        **DEFAULT_LIMITS,
        "max_parameters": 1,
        "max_nesting": 0,
        "max_function_lines": 1,
    }

    funcs, files, classes = analyze_file(str(file), limits)

    assert [issue["message"] for issue in funcs[0]["issues"]] == [
        "Function too long (3/1)",
        "Too many parameters (2/1)",
        "Nesting too deep (1/0)",
    ]


def test_analyze_file_class_and_file_warnings(tmp_path):

    file = tmp_path / "big.py"
    file.write_text("class Big:\n" + "    def m():\n        pass\n" * 20)

    limits = {**DEFAULT_LIMITS, "max_class_lines": 10, "max_file_lines": 10}

    funcs, files, classes = analyze_file(str(file), limits)

    assert classes[0]["issues"][0]["message"] == "Class too large (41/10)"
    assert files[0]["issues"][0]["message"] == "File too large (41/10)"


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


def test_generate_report_all_clean(capsys):

    funcs = [
        {
            "name": "ok",
            "file": "a.py",
            "lines": 3,
            "parameters": 0,
            "nesting_depth": 0,
            "issues": [],
        }
    ]
    files = [{"name": "a.py", "lines": 3, "issues": []}]
    classes = []

    generate_report(funcs, files, classes)

    assert "All clean." in capsys.readouterr().out


def test_generate_report_with_issues(capsys):

    funcs = [
        {
            "name": "f",
            "file": "a.py",
            "lines": 3,
            "parameters": 2,
            "nesting_depth": 1,
            "issues": [
                {"severity": "WARNING", "message": "Too many parameters (2/1)"}
            ],
        }
    ]
    files = [{"name": "a.py", "lines": 3, "issues": []}]
    classes = []

    generate_report(funcs, files, classes)

    out = capsys.readouterr().out

    assert "need attention" in out
    assert "Too many parameters (2/1)" in out


def test_main_with_mocked_git(tmp_path, monkeypatch, capsys):

    good = tmp_path / "good.py"
    broken = tmp_path / "broken.py"

    good.write_text("def ok():\n    pass\n")
    broken.write_text("def broken(\n")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "scrut.git.subprocess.run",
        lambda *a, **k: Mock(returncode=0, stdout="good.py\nbroken.py\n"),
    )

    main()

    out = capsys.readouterr().out

    assert "Python syntax error" in out
    assert "need attention" in out
    assert "passed" in out


def test_main_with_real_git_repo(tmp_path, monkeypatch, capsys):

    def git(*args):
        subprocess.run(["git", *args], cwd=tmp_path, check=True, capture_output=True)

    git("init", "-q")
    git("config", "user.email", "test@example.com")
    git("config", "user.name", "Test")

    (tmp_path / "a.py").write_text("def a():\n    pass\n")
    git("add", "-A")
    git("-c", "commit.gpgsign=false", "commit", "-q", "-m", "initial")

    (tmp_path / "a.py").write_text("def a():\n    return 1\n")
    (tmp_path / "b.py").write_text("def b():\n    pass\n")
    (tmp_path / "notes.txt").write_text("x\n")
    git("add", "-A")

    monkeypatch.chdir(tmp_path)

    main()

    assert "All clean." in capsys.readouterr().out
