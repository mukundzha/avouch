import ast
import json
import subprocess
from unittest.mock import Mock, patch

import pytest

from avouch.analyzer import analyze_file, get_depth, read_file
from avouch.git import get_changed_files, get_staged_files, get_reviewable_files, is_gitrepo
from avouch.report import generate_report
from avouch.cli import main, SUCCESS, VIOLATIONS_FOUND, ERROR
from avouch.config.default import DEFAULT_LIMITS
from avouch.config.loader import load_config, merge_limits, DEFAULT_RULES, merge_ignore_paths
from avouch.rules.complexity import calculate_complexity
from avouch.rules.boolean_complexity import analyze, count_boolean_conditions
from avouch.utility.is_ignored import is_ignored

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

    result = main([])

    assert "All clean." in capsys.readouterr().out
    assert result == SUCCESS


def test_main_ignores_path_in_real_git_repo(tmp_path, monkeypatch, capsys):

    def git(*args):
        subprocess.run(["git", *args], cwd=tmp_path, check=True, capture_output=True)

    git("init", "-q")
    git("config", "user.email", "test@example.com")
    git("config", "user.name", "Test")

    (tmp_path / "tests").mkdir()
    (tmp_path / "app.py").write_text("def a():\n    pass\n")
    (tmp_path / "tests" / "bad.py").write_text("def t():\n    pass\n")
    git("add", "-A")
    git("-c", "commit.gpgsign=false", "commit", "-q", "-m", "initial")

    body = "".join(f"    if x{i}:\n        pass\n" for i in range(10))
    _avouch_toml(tmp_path)
    (tmp_path / "app.py").write_text("def f(x):\n" + body)
    (tmp_path / "tests" / "bad.py").write_text("def t(x):\n" + body)
    git("add", "-A")

    monkeypatch.chdir(tmp_path)

    result = main(["--ignore-path", "tests"])

    out = capsys.readouterr().out

    assert result == VIOLATIONS_FOUND
    assert "app.py" in out
    assert "tests/bad.py" not in out


def test_main_returns_1_on_violations(tmp_path, monkeypatch, capsys):

    body = "".join(f"    if x{i}:\n        pass\n" for i in range(10))
    _avouch_toml(tmp_path)
    bad = tmp_path / "bad.py"
    bad.write_text("def f(x):\n" + body)

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "avouch.git.subprocess.run",
        lambda *a, **k: Mock(returncode=0, stdout="bad.py\n"),
    )

    assert main([]) == VIOLATIONS_FOUND
    assert "Function too complex" in capsys.readouterr().out


@patch("avouch.cli.is_gitrepo", return_value=False)
def test_main_returns_2_on_error(mock_is_gitrepo, capsys):

    assert main([]) == ERROR
    assert "no Git repository found" in capsys.readouterr().err


@patch("avouch.cli.is_gitrepo")
def test_main_docs_prints_without_review(mock_is_gitrepo, capsys):

    assert main(["--docs"]) == SUCCESS

    out = capsys.readouterr().out

    assert "AVOUCH" in out
    assert "REVIEW RULES" in out
    assert "SCR014" in out
    assert not mock_is_gitrepo.called


@patch("avouch.cli.is_gitrepo", return_value=False)
def test_main_docs_works_outside_git_repo(mock_is_gitrepo, capsys):

    assert main(["--docs"]) == SUCCESS

    out = capsys.readouterr().out

    assert "AVOUCH" in out
    assert not mock_is_gitrepo.called


def _main_git(tmp_path, monkeypatch, stdout):

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "avouch.git.subprocess.run",
        Mock(
            side_effect=[
                Mock(returncode=0, stdout=""),
                Mock(returncode=0, stdout=""),
                Mock(returncode=0, stdout=stdout),
            ]
        ),
    )


def _avouch_toml(tmp_path, extra=""):

    (tmp_path / "avouch.toml").write_text(extra + "[limits]\nmax_complexity = 10\n")


def test_main_verbose_reports_diagnostics(tmp_path, monkeypatch, capsys):

    (tmp_path / "a.py").write_text("def ok():\n    pass\n")

    _main_git(tmp_path, monkeypatch, "a.py\n")

    assert main(["--verbose"]) == SUCCESS

    captured = capsys.readouterr()

    assert "reviewing 1 of 1" in captured.err
    assert "analyzed a.py" in captured.err
    assert "findings: 0" in captured.err
    assert "All clean." in captured.out


def test_main_verbose_quiet_when_nothing_to_review(tmp_path, monkeypatch, capsys):

    _main_git(tmp_path, monkeypatch, "")

    assert main(["--verbose"]) == ERROR

    captured = capsys.readouterr()

    assert captured.out == ""
    assert captured.err == (
        "avouch: candidate files: 0, reviewable: 0\n"
        "error: nothing to review\n"
        "hint: nothing changed vs HEAD (CI checkouts are clean); use --all-files for a full review\n"
    )


def test_main_verbose_keeps_normal_mode_quiet(tmp_path, monkeypatch, capsys):

    (tmp_path / "a.py").write_text("def ok():\n    pass\n")

    _main_git(tmp_path, monkeypatch, "a.py\n")

    assert main([]) == SUCCESS

    captured = capsys.readouterr()

    assert "All clean." in captured.out
    assert captured.err == ""


def test_main_verbose_findings_unchanged(tmp_path, monkeypatch, capsys):

    body = "".join(f"    if x{i}:\n        pass\n" for i in range(10))
    _avouch_toml(tmp_path)
    (tmp_path / "bad.py").write_text("def f(x):\n" + body)

    monkeypatch.chdir(tmp_path)

    def run(mode):

        order = {"call": 0}

        def fake_run(*args, **kwargs):
            order["call"] += 1
            return Mock(returncode=0, stdout="bad.py\n" if order["call"] == 3 else "")

        monkeypatch.setattr("avouch.git.subprocess.run", fake_run)

        return main(mode)

    assert run([]) == VIOLATIONS_FOUND
    normal_out = capsys.readouterr().out

    assert run(["--verbose"]) == VIOLATIONS_FOUND
    verbose = capsys.readouterr()

    assert verbose.out == normal_out
    assert "Function too complex" in verbose.out
    assert "findings: 1" in verbose.err


def test_main_changed_reviews_same_files_as_default(tmp_path, monkeypatch, capsys):

    body = "".join(f"    if x{i}:\n        pass\n" for i in range(10))
    _avouch_toml(tmp_path)
    (tmp_path / "bad.py").write_text("def f(x):\n" + body)

    monkeypatch.chdir(tmp_path)

    def run(mode):

        order = {"call": 0}

        def fake_run(*args, **kwargs):
            order["call"] += 1
            return Mock(returncode=0, stdout="bad.py\n" if order["call"] == 3 else "")

        monkeypatch.setattr("avouch.git.subprocess.run", fake_run)

        return main(mode)

    assert run([]) == VIOLATIONS_FOUND
    normal_out = capsys.readouterr().out

    assert run(["--changed"]) == VIOLATIONS_FOUND
    changed_out = capsys.readouterr().out

    assert "bad.py" in normal_out
    assert "bad.py" in changed_out


@pytest.mark.parametrize(
    "flags",
    [
        ["--changed", "--staged"],
        ["--changed", "--all-files"],
        ["--staged", "--all-files"],
    ],
)
def test_main_selection_flags_are_mutually_exclusive(flags, capsys):

    with pytest.raises(SystemExit) as exc:
        main(flags)

    assert exc.value.code == 2
    assert "not allowed with argument" in capsys.readouterr().err


def test_main_changed_no_changed_files(tmp_path, monkeypatch, capsys):

    _main_git(tmp_path, monkeypatch, "")

    assert main(["--changed"]) == ERROR
    assert "nothing to review" in capsys.readouterr().err


@patch("avouch.cli.is_gitrepo", return_value=False)
def test_main_changed_outside_git_repo(mock_is_gitrepo, capsys):

    assert main(["--changed"]) == ERROR
    assert "no Git repository found" in capsys.readouterr().err


def _main_staged(tmp_path, monkeypatch, stdout):

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "avouch.git.subprocess.run",
        Mock(
            side_effect=[
                Mock(returncode=0, stdout=""),
                Mock(returncode=0, stdout=stdout),
            ]
        ),
    )

    return main(["--staged"])


def test_main_staged_selects_multiple_files(tmp_path, monkeypatch, capsys):

    (tmp_path / "a.py").write_text("def ok():\n    pass\n")
    (tmp_path / "b.py").write_text("def f(a, b, c, d, e, f):\n    return a\n")
    (tmp_path / "notes.txt").write_text("x\n")

    assert _main_staged(tmp_path, monkeypatch, "a.py\nb.py\nnotes.txt\n") == VIOLATIONS_FOUND

    out = capsys.readouterr().out

    assert "✓ a.py" in out
    assert "Too many parameters" in out
    assert "notes.txt" not in out


def test_main_staged_uses_findings_report(tmp_path, monkeypatch, capsys):

    (tmp_path / "a.py").write_text("def ok():\n    pass\n")

    assert _main_staged(tmp_path, monkeypatch, "a.py\n") == SUCCESS

    out = capsys.readouterr().out

    assert "All clean." in out
    assert "[Changed Files]" not in out


def test_main_staged_no_staged_files(tmp_path, monkeypatch, capsys):

    assert _main_staged(tmp_path, monkeypatch, "") == ERROR
    assert "nothing to review" in capsys.readouterr().err


@patch("avouch.cli.is_gitrepo", return_value=False)
def test_main_staged_outside_git_repo(mock_is_gitrepo, capsys):

    assert main(["--staged"]) == ERROR
    assert "no Git repository found" in capsys.readouterr().err


def test_main_staged_ignores_unstaged_changes(tmp_path, monkeypatch, capsys):

    def git(*args):
        subprocess.run(["git", *args], cwd=tmp_path, check=True, capture_output=True)

    git("init", "-q")
    git("config", "user.email", "test@example.com")
    git("config", "user.name", "Test")

    (tmp_path / "a.py").write_text("def a():\n    pass\n")
    (tmp_path / "b.py").write_text("def b():\n    pass\n")
    git("add", "-A")
    git("-c", "commit.gpgsign=false", "commit", "-q", "-m", "initial")

    (tmp_path / "a.py").write_text("def a():\n    return 1\n")
    body = "".join(f"    if x{i}:\n        pass\n" for i in range(10))
    (tmp_path / "b.py").write_text("def b(x):\n" + body)
    git("add", "a.py")

    monkeypatch.chdir(tmp_path)

    result = main(["--staged"])

    out = capsys.readouterr().out

    assert result == SUCCESS
    assert "All clean." in out
    assert "b.py" not in out


def test_main_staged_respects_ignore_paths(tmp_path, monkeypatch, capsys):

    (tmp_path / "tests").mkdir()
    (tmp_path / "app.py").write_text("def f(a, b, c, d, e, f):\n    return a\n")
    (tmp_path / "tests" / "bad.py").write_text("def f(a, b, c, d, e, f):\n    return a\n")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "avouch.git.subprocess.run",
        Mock(
            side_effect=[
                Mock(returncode=0, stdout=""),
                Mock(returncode=0, stdout="app.py\ntests/bad.py\n"),
            ]
        ),
    )

    assert main(["--staged", "--ignore-path", "tests"]) == VIOLATIONS_FOUND

    captured = capsys.readouterr()

    assert "app.py" in captured.out
    assert "tests/bad.py" not in captured.out
 

def test_main_invalid_config_reports_error(tmp_path, monkeypatch, capsys):

    (tmp_path / "avouch.toml").write_text("[limits\n")

    monkeypatch.chdir(tmp_path)

    assert main([]) == ERROR

    captured = capsys.readouterr()

    assert "invalid avouch.toml configuration" in captured.err
    assert "hint: check the [limits], [rules], and ignore_paths sections" in captured.err


def test_main_quiet_clean_suppresses_output(tmp_path, monkeypatch, capsys):

    (tmp_path / "a.py").write_text("def ok():\n    pass\n")

    _main_git(tmp_path, monkeypatch, "a.py\n")

    assert main(["--quiet"]) == SUCCESS

    assert capsys.readouterr().out == ""


def test_main_quiet_same_exit_code_as_normal(tmp_path, monkeypatch, capsys):

    body = "".join(f"    if x{i}:\n        pass\n" for i in range(10))
    _avouch_toml(tmp_path)
    (tmp_path / "bad.py").write_text("def f(x):\n" + body)

    monkeypatch.chdir(tmp_path)

    def run(mode):

        order = {"call": 0}

        def fake_run(*args, **kwargs):
            order["call"] += 1
            return Mock(returncode=0, stdout="bad.py\n" if order["call"] == 3 else "")

        monkeypatch.setattr("avouch.git.subprocess.run", fake_run)

        return main(mode)

    assert run([]) == VIOLATIONS_FOUND
    assert "Function too complex" in capsys.readouterr().out

    assert run(["--quiet"]) == VIOLATIONS_FOUND
    assert capsys.readouterr().out == ""


def test_main_quiet_errors_remain_visible(tmp_path, monkeypatch, capsys):

    _main_git(tmp_path, monkeypatch, "")

    assert main(["--quiet"]) == ERROR

    captured = capsys.readouterr()

    assert captured.out == ""
    assert "nothing to review" in captured.err


@patch("avouch.cli.is_gitrepo", return_value=False)
def test_main_quiet_error_outside_git_repo(mock_is_gitrepo, capsys):

    assert main(["--quiet"]) == ERROR
    assert "no Git repository found" in capsys.readouterr().err


def test_main_quiet_json_still_valid(tmp_path, monkeypatch, capsys):

    body = "".join(f"    if x{i}:\n        pass\n" for i in range(10))
    _avouch_toml(tmp_path)
    (tmp_path / "bad.py").write_text("def f(x):\n" + body)

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "avouch.git.subprocess.run",
        Mock(
            side_effect=[
                Mock(returncode=0, stdout=""),
                Mock(returncode=0, stdout="bad.py\n"),
                Mock(returncode=0, stdout=""),
            ]
        ),
    )

    assert main(["--quiet", "--json"]) == VIOLATIONS_FOUND

    data = json.loads(capsys.readouterr().out)

    assert data["summary"]["total"] == 1


def test_main_quiet_changed_suppresses_diff_view(tmp_path, monkeypatch, capsys):

    (tmp_path / "bad.py").write_text("def f(x):\n    return x\n")

    _main_git(tmp_path, monkeypatch, "bad.py\n")

    assert main(["--quiet", "--changed"]) == SUCCESS

    assert capsys.readouterr().out == ""


def test_main_quiet_verbose_keeps_diagnostics(tmp_path, monkeypatch, capsys):

    (tmp_path / "a.py").write_text("def ok():\n    pass\n")

    _main_git(tmp_path, monkeypatch, "a.py\n")

    assert main(["--quiet", "--verbose"]) == SUCCESS

    captured = capsys.readouterr()

    assert captured.out == ""
    assert "findings: 0" in captured.err


def test_main_quiet_all_files(tmp_path, monkeypatch, capsys):

    (tmp_path / "a.py").write_text("def f(a, b, c, d, e, f):\n    return a\n")

    _main_all_files(tmp_path, monkeypatch, "a.py\n")

    assert main(["--quiet", "--all-files"]) == VIOLATIONS_FOUND

    assert capsys.readouterr().out == ""


def test_main_quiet_staged(tmp_path, monkeypatch, capsys):

    (tmp_path / "a.py").write_text("def f(a, b, c, d, e, f):\n    return a\n")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "avouch.git.subprocess.run",
        Mock(
            side_effect=[
                Mock(returncode=0, stdout=""),
                Mock(returncode=0, stdout="a.py\n"),
            ]
        ),
    )

    assert main(["--quiet", "--staged"]) == VIOLATIONS_FOUND

    assert capsys.readouterr().out == ""


def test_main_help_lists_quiet(capsys):

    with pytest.raises(SystemExit):
        main(["--help"])

    assert "--quiet" in capsys.readouterr().out


def test_main_version_prints_version(capsys):

    with pytest.raises(SystemExit) as exc:
        main(["--version"])

    assert exc.value.code == 0
    assert "avouch 0.3.3" in capsys.readouterr().out


def _main_all_files(tmp_path, monkeypatch, stdout):

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "avouch.git.subprocess.run",
        Mock(
            side_effect=[
                Mock(returncode=0, stdout=""),
                Mock(returncode=0, stdout=stdout),
            ]
        ),
    )


def test_main_all_files_selects_every_python_file(tmp_path, monkeypatch, capsys):

    (tmp_path / "a.py").write_text("def ok():\n    pass\n")
    (tmp_path / "b.py").write_text("def ok():\n    pass\n")
    (tmp_path / "c.py").write_text("def f(a, b, c, d, e, f):\n    return a\n")

    _main_all_files(tmp_path, monkeypatch, "a.py\nb.py\nc.py\nnotes.txt\n")

    assert main(["--all-files"]) == VIOLATIONS_FOUND

    captured = capsys.readouterr()

    assert "✓ a.py" in captured.out
    assert "✓ b.py" in captured.out
    assert "c.py" in captured.out
    assert "Too many parameters" in captured.out


def test_main_all_files_respects_ignore_paths(tmp_path, monkeypatch, capsys):

    (tmp_path / "tests").mkdir()
    (tmp_path / "app.py").write_text("def f(a, b, c, d, e, f):\n    return a\n")
    (tmp_path / "tests" / "bad.py").write_text("def f(a, b, c, d, e, f):\n    return a\n")

    _main_all_files(tmp_path, monkeypatch, "app.py\ntests/bad.py\n")

    assert main(["--all-files", "--ignore-path", "tests"]) == VIOLATIONS_FOUND

    captured = capsys.readouterr()

    assert "app.py" in captured.out
    assert "tests/bad.py" not in captured.out


def test_main_all_files_skips_generated(tmp_path, monkeypatch, capsys):

    (tmp_path / "app.py").write_text("def f(a, b, c, d, e, f):\n    return a\n")
    (tmp_path / "generated.py").write_text("def f(a, b, c, d, e, f):\n    return a\n")

    _main_all_files(tmp_path, monkeypatch, "app.py\ngenerated.py\n")

    assert main(["--all-files"]) == VIOLATIONS_FOUND

    captured = capsys.readouterr()

    assert "app.py" in captured.out
    assert "generated.py" not in captured.out


def _main_json(tmp_path, monkeypatch, stdout):

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "avouch.git.subprocess.run",
        Mock(
            side_effect=[
                Mock(returncode=0, stdout=""),
                Mock(returncode=0, stdout=stdout),
                Mock(returncode=0, stdout=""),
            ]
        ),
    )

    return main(["--json"])


def test_main_json_clean(tmp_path, monkeypatch, capsys):

    (tmp_path / "good.py").write_text("def ok():\n    pass\n")

    assert _main_json(tmp_path, monkeypatch, "good.py\n") == SUCCESS

    data = json.loads(capsys.readouterr().out)

    assert data["version"] == 1
    assert data["violations"] == []
    assert data["summary"] == {
        "total": 0,
        "errors": 0,
        "warnings": 0,
        "files_with_violations": 0,
    }


def test_main_json_single_violation(tmp_path, monkeypatch, capsys):

    body = "".join(f"    if x{i}:\n        pass\n" for i in range(10))
    _avouch_toml(tmp_path)
    (tmp_path / "bad.py").write_text("def f(x):\n" + body)

    assert _main_json(tmp_path, monkeypatch, "bad.py\n") == VIOLATIONS_FOUND

    data = json.loads(capsys.readouterr().out)
    violation = data["violations"][0]

    assert data["summary"]["total"] == 1
    assert violation["severity"] == "WARNING"
    assert "Function too complex" in violation["message"]
    assert violation["file"] == "bad.py"
    assert violation["name"] == "f"
    assert violation["kind"] == "func"


def test_main_json_multiple_violations_one_file(tmp_path, monkeypatch, capsys):

    (tmp_path / "avouch.toml").write_text(
        "[limits]\nmax_parameters = 1\nmax_function_lines = 1\n"
    )
    (tmp_path / "a.py").write_text("def f(a, b):\n    pass\n")

    assert _main_json(tmp_path, monkeypatch, "a.py\n") == VIOLATIONS_FOUND

    data = json.loads(capsys.readouterr().out)
    messages = [v["message"] for v in data["violations"]]

    assert data["summary"]["total"] == 2
    assert any("Function too long" in m for m in messages)
    assert any("Too many parameters" in m for m in messages)


def test_main_json_multiple_files(tmp_path, monkeypatch, capsys):

    (tmp_path / "avouch.toml").write_text("[limits]\nmax_parameters = 1\n")
    (tmp_path / "a.py").write_text("def f(a, b):\n    pass\n")
    (tmp_path / "b.py").write_text("def g(c, d):\n    pass\n")

    assert _main_json(tmp_path, monkeypatch, "a.py\nb.py\n") == VIOLATIONS_FOUND

    data = json.loads(capsys.readouterr().out)

    assert {v["file"] for v in data["violations"]} == {"a.py", "b.py"}
    assert all(v["rule"] == "SCR014" for v in data["violations"])
    assert data["summary"] == {
        "total": 2,
        "errors": 0,
        "warnings": 2,
        "files_with_violations": 2,
    }


@patch("avouch.cli.is_gitrepo", return_value=False)
def test_main_json_error_exit_code(mock_is_gitrepo, capsys):

    assert main(["--json"]) == ERROR

    captured = capsys.readouterr()

    assert captured.out == ""
    assert "no Git repository found" in captured.err


def test_main_changed_json_is_machine_readable(tmp_path, monkeypatch, capsys):

    body = "".join(f"    if x{i}:\n        pass\n" for i in range(10))
    _avouch_toml(tmp_path)
    (tmp_path / "bad.py").write_text("def f(x):\n" + body)

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "avouch.git.subprocess.run",
        Mock(
            side_effect=[
                Mock(returncode=0, stdout=""),
                Mock(returncode=0, stdout="bad.py\n"),
                Mock(returncode=0, stdout=""),
            ]
        ),
    )

    assert main(["--changed", "--json"]) == VIOLATIONS_FOUND

    out = capsys.readouterr().out

    assert "[Changed Files]" not in out
    assert "\x1b" not in out
    assert json.loads(out)["summary"]["total"] == 1


def test_main_staged_json_is_machine_readable(tmp_path, monkeypatch, capsys):

    body = "".join(f"    if x{i}:\n        pass\n" for i in range(10))
    _avouch_toml(tmp_path)
    (tmp_path / "bad.py").write_text("def f(x):\n" + body)

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "avouch.git.subprocess.run",
        Mock(
            side_effect=[
                Mock(returncode=0, stdout=""),
                Mock(returncode=0, stdout="bad.py\n"),
            ]
        ),
    )

    assert main(["--staged", "--json"]) == VIOLATIONS_FOUND

    out = capsys.readouterr().out

    assert "\x1b" not in out
    assert json.loads(out)["summary"]["total"] == 1


def test_main_all_files_json_is_machine_readable(tmp_path, monkeypatch, capsys):

    body = "".join(f"    if x{i}:\n        pass\n" for i in range(10))
    _avouch_toml(tmp_path)
    (tmp_path / "bad.py").write_text("def f(x):\n" + body)

    _main_all_files(tmp_path, monkeypatch, "bad.py\n")

    assert main(["--all-files", "--json"]) == VIOLATIONS_FOUND

    out = capsys.readouterr().out

    assert "\x1b" not in out
    assert json.loads(out)["summary"]["total"] == 1


def test_main_json_contract_fields(tmp_path, monkeypatch, capsys):

    body = "".join(f"    if x{i}:\n        pass\n" for i in range(10))
    _avouch_toml(tmp_path)
    (tmp_path / "bad.py").write_text("def f(x):\n" + body)

    assert _main_json(tmp_path, monkeypatch, "bad.py\n") == VIOLATIONS_FOUND

    data = json.loads(capsys.readouterr().out)

    assert data["version"] == 1
    assert data["tool"] == "avouch"
    assert data["violations"][0]["line"] == 1


def test_main_json_syntax_error_reports_line(tmp_path, monkeypatch, capsys):

    (tmp_path / "broken.py").write_text("def broken(\n")

    assert _main_json(tmp_path, monkeypatch, "broken.py\n") == VIOLATIONS_FOUND

    data = json.loads(capsys.readouterr().out)

    assert data["violations"][0]["kind"] == "file"
    assert data["violations"][0]["line"] == 1


def test_main_json_file_finding_line_is_null(tmp_path, monkeypatch, capsys):

    (tmp_path / "avouch.toml").write_text("[limits]\nmax_file_lines = 1\n")
    (tmp_path / "a.py").write_text("def f(a, b):\n    pass\n")

    assert _main_json(tmp_path, monkeypatch, "a.py\n") == VIOLATIONS_FOUND

    data = json.loads(capsys.readouterr().out)
    violation = data["violations"][0]

    assert violation["kind"] == "file"
    assert violation["line"] is None


def test_main_json_deterministic(tmp_path, monkeypatch, capsys):

    body = "".join(f"    if x{i}:\n        pass\n" for i in range(10))
    _avouch_toml(tmp_path)
    (tmp_path / "bad.py").write_text("def f(x):\n" + body)

    assert _main_json(tmp_path, monkeypatch, "bad.py\n") == VIOLATIONS_FOUND
    first = capsys.readouterr().out

    assert _main_json(tmp_path, monkeypatch, "bad.py\n") == VIOLATIONS_FOUND
    second = capsys.readouterr().out

    assert first == second


def test_main_unreadable_file_reports_reason(tmp_path, monkeypatch, capsys):

    (tmp_path / "dir.py").mkdir()

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "avouch.git.subprocess.run",
        Mock(
            side_effect=[
                Mock(returncode=0, stdout=""),
                Mock(returncode=0, stdout=""),
                Mock(returncode=0, stdout="dir.py\n"),
            ]
        ),
    )

    assert main(["--json"]) == VIOLATIONS_FOUND

    violation = json.loads(capsys.readouterr().out)["violations"][0]

    assert violation["kind"] == "file"
    assert violation["message"] == "Could not read 'dir.py': Is a directory."


def test_main_syntax_error_reports_detail(tmp_path, monkeypatch, capsys):

    (tmp_path / "broken.py").write_text("def broken(\n")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "avouch.git.subprocess.run",
        Mock(
            side_effect=[
                Mock(returncode=0, stdout=""),
                Mock(returncode=0, stdout=""),
                Mock(returncode=0, stdout="broken.py\n"),
            ]
        ),
    )

    assert main(["--json"]) == VIOLATIONS_FOUND

    violation = json.loads(capsys.readouterr().out)["violations"][0]

    assert violation["kind"] == "file"
    assert "Could not parse 'broken.py'" in violation["message"]
    assert "line 1" in violation["message"]


def test_main_non_utf8_file_reports_reason(tmp_path, monkeypatch, capsys):

    (tmp_path / "binary.py").write_bytes(b"def f():\n    return '\xff'\n")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "avouch.git.subprocess.run",
        Mock(
            side_effect=[
                Mock(returncode=0, stdout=""),
                Mock(returncode=0, stdout=""),
                Mock(returncode=0, stdout="binary.py\n"),
            ]
        ),
    )

    assert main(["--json"]) == VIOLATIONS_FOUND

    violation = json.loads(capsys.readouterr().out)["violations"][0]

    assert violation["kind"] == "file"
    assert "Could not read 'binary.py':" in violation["message"]
    assert "invalid start byte" in violation["message"]


def test_main_internal_error_reports_concise_diagnostic(tmp_path, monkeypatch, capsys):

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "avouch.git.subprocess.run",
        Mock(side_effect=[Mock(returncode=0, stdout="")]),
    )
    monkeypatch.setattr("avouch.cli.get_changed_files", Mock(side_effect=RuntimeError("boom")))

    assert main([]) == ERROR

    captured = capsys.readouterr()

    assert captured.out == ""
    assert "error: internal error: RuntimeError: boom" in captured.err
    assert "Traceback" not in captured.err


def test_main_internal_error_traceback_under_verbose(tmp_path, monkeypatch, capsys):

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "avouch.git.subprocess.run",
        Mock(side_effect=[Mock(returncode=0, stdout="")]),
    )
    monkeypatch.setattr("avouch.cli.get_changed_files", Mock(side_effect=RuntimeError("boom")))

    assert main(["--verbose"]) == ERROR

    captured = capsys.readouterr()

    assert "error: internal error: RuntimeError: boom" in captured.err
    assert "Traceback (most recent call last):" in captured.err


def test_main_verbose_json_stdout_stays_clean(tmp_path, monkeypatch, capsys):

    body = "".join(f"    if x{i}:\n        pass\n" for i in range(10))
    _avouch_toml(tmp_path)
    (tmp_path / "bad.py").write_text("def f(x):\n" + body)

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "avouch.git.subprocess.run",
        Mock(
            side_effect=[
                Mock(returncode=0, stdout=""),
                Mock(returncode=0, stdout="bad.py\n"),
                Mock(returncode=0, stdout=""),
            ]
        ),
    )

    assert main(["--verbose", "--json"]) == VIOLATIONS_FOUND

    captured = capsys.readouterr()

    assert json.loads(captured.out)["summary"]["total"] == 1
    assert "review set: bad.py" in captured.err


def test_main_verbose_reports_ignore_paths_and_skips(tmp_path, monkeypatch, capsys):

    (tmp_path / "tests").mkdir()
    (tmp_path / "app.py").write_text("def ok():\n    pass\n")
    (tmp_path / "tests" / "bad.py").write_text("def ok():\n    pass\n")
    (tmp_path / "notes.txt").write_text("x\n")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "avouch.git.subprocess.run",
        Mock(
            side_effect=[
                Mock(returncode=0, stdout=""),
                Mock(returncode=0, stdout="app.py\ntests/bad.py\nnotes.txt\n"),
                Mock(returncode=0, stdout=""),
            ]
        ),
    )

    assert main(["--verbose", "--ignore-path", "tests"]) == SUCCESS

    captured = capsys.readouterr()

    assert "ignore paths: tests" in captured.err
    assert "skipped 2 non-reviewable file(s): tests/bad.py, notes.txt" in captured.err


def test_main_changed_non_utf8_file_does_not_crash(tmp_path, monkeypatch, capsys):

    def git(*args):
        subprocess.run(["git", *args], cwd=tmp_path, check=True, capture_output=True)

    git("init", "-q")
    git("config", "user.email", "test@example.com")
    git("config", "user.name", "Test")

    (tmp_path / "ok.py").write_text("def ok():\n    pass\n")
    (tmp_path / "weird.py").write_bytes(b"x = 1\n")
    git("add", "-A")
    git("-c", "commit.gpgsign=false", "commit", "-q", "-m", "initial")

    (tmp_path / "weird.py").write_bytes(b"\xff\xfe\xfa")
    (tmp_path / "ok.py").write_text("def ok():\n    return 1\n")

    monkeypatch.chdir(tmp_path)

    assert main(["--changed"]) == VIOLATIONS_FOUND

    assert "weird.py" in capsys.readouterr().out


def test_main_without_not_git_still_requires_git(tmp_path, monkeypatch, capsys):

    (tmp_path / "a.py").write_text("def ok():\n    pass\n")

    monkeypatch.chdir(tmp_path)

    assert main([]) == ERROR
    assert "no Git repository found" in capsys.readouterr().err


def test_main_not_git_reviews_python_files_in_plain_directory(tmp_path, monkeypatch, capsys):

    (tmp_path / "good.py").write_text("def f(a, b, c, d, e, f):\n    return a\n")
    (tmp_path / "notes.txt").write_text("not python\n")

    monkeypatch.chdir(tmp_path)

    assert main(["--not-git"]) == VIOLATIONS_FOUND

    captured = capsys.readouterr()

    assert "good.py" in captured.out
    assert "notes.txt" not in captured.out


def test_main_not_git_reports_findings(tmp_path, monkeypatch, capsys):

    body = "".join(f"    if x{i}:\n        pass\n" for i in range(10))
    _avouch_toml(tmp_path)
    (tmp_path / "bad.py").write_text("def f(x):\n" + body)

    monkeypatch.chdir(tmp_path)

    assert main(["--not-git"]) == VIOLATIONS_FOUND
    assert "Function too complex" in capsys.readouterr().out


def test_main_not_git_discovers_nested_python_files(tmp_path, monkeypatch, capsys):

    (tmp_path / "nested").mkdir()
    (tmp_path / "nested" / "deep.py").write_text("def f(a, b, c, d, e, f):\n    return a\n")

    monkeypatch.chdir(tmp_path)

    assert main(["--not-git"]) == VIOLATIONS_FOUND

    out = capsys.readouterr().out

    assert "nested/deep.py" in out
    assert "Too many parameters" in out


def test_main_not_git_skips_env_and_cache_directories(tmp_path, monkeypatch, capsys):

    body = "".join(f"    if x{i}:\n        pass\n" for i in range(10))
    _avouch_toml(tmp_path)
    (tmp_path / ".venv").mkdir()
    (tmp_path / ".venv" / "lib.py").write_text("def f(x):\n" + body)
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "__pycache__" / "cached.py").write_text("def f(x):\n" + body)
    (tmp_path / "generated.py").write_text("def f(x):\n" + body)
    (tmp_path / "app.py").write_text("def f(x):\n" + body)

    monkeypatch.chdir(tmp_path)

    assert main(["--not-git"]) == VIOLATIONS_FOUND

    out = capsys.readouterr().out

    assert "app.py" in out
    assert ".venv" not in out
    assert "__pycache__" not in out
    assert "generated.py" not in out


def test_main_not_git_respects_ignore_path_flag(tmp_path, monkeypatch, capsys):

    body = "".join(f"    if x{i}:\n        pass\n" for i in range(10))
    _avouch_toml(tmp_path)
    (tmp_path / "tests").mkdir()
    (tmp_path / "app.py").write_text("def f(x):\n" + body)
    (tmp_path / "tests" / "bad.py").write_text("def f(x):\n" + body)

    monkeypatch.chdir(tmp_path)

    assert main(["--not-git", "--ignore-path", "tests"]) == VIOLATIONS_FOUND

    out = capsys.readouterr().out

    assert "app.py" in out
    assert "tests/bad.py" not in out


def test_main_not_git_respects_config_ignore_paths(tmp_path, monkeypatch, capsys):

    _avouch_toml(tmp_path, 'ignore_paths = ["tests"]\n')
    body = "".join(f"    if x{i}:\n        pass\n" for i in range(10))
    (tmp_path / "tests").mkdir()
    (tmp_path / "app.py").write_text("def f(x):\n" + body)
    (tmp_path / "tests" / "bad.py").write_text("def f(x):\n" + body)

    monkeypatch.chdir(tmp_path)

    assert main(["--not-git"]) == VIOLATIONS_FOUND

    out = capsys.readouterr().out

    assert "app.py" in out
    assert "tests/bad.py" not in out


def test_main_not_git_json_uses_existing_schema(tmp_path, monkeypatch, capsys):

    body = "".join(f"    if x{i}:\n        pass\n" for i in range(10))
    _avouch_toml(tmp_path)
    (tmp_path / "bad.py").write_text("def f(x):\n" + body)
    (tmp_path / "good.py").write_text("def ok():\n    pass\n")

    monkeypatch.chdir(tmp_path)

    assert main(["--not-git", "--json"]) == VIOLATIONS_FOUND

    data = json.loads(capsys.readouterr().out)

    assert data["version"] == 1
    assert data["tool"] == "avouch"
    assert data["violations"][0]["file"] == "bad.py"
    assert data["summary"] == {
        "total": 1,
        "errors": 0,
        "warnings": 1,
        "files_with_violations": 1,
    }


def test_main_not_git_json_is_deterministic_and_sorted(tmp_path, monkeypatch, capsys):

    (tmp_path / "z.py").write_text("def f(a, b, c, d, e, f):\n    return a\n")
    (tmp_path / "a.py").write_text("def f(a, b, c, d, e, f):\n    return a\n")

    monkeypatch.chdir(tmp_path)

    assert main(["--not-git", "--json"]) == VIOLATIONS_FOUND
    first = capsys.readouterr().out

    assert main(["--not-git", "--json"]) == VIOLATIONS_FOUND
    second = capsys.readouterr().out

    assert first == second
    assert [v["file"] for v in json.loads(first)["violations"]] == ["a.py", "z.py"]


def test_main_not_git_verbose(tmp_path, monkeypatch, capsys):

    (tmp_path / "a.py").write_text("def ok():\n    pass\n")

    monkeypatch.chdir(tmp_path)

    assert main(["--not-git", "--verbose"]) == SUCCESS

    captured = capsys.readouterr()

    assert "review mode: all Python files on disk (--not-git)" in captured.err
    assert "reviewing 1 of 1" in captured.err
    assert "analyzed a.py" in captured.err
    assert "All clean." in captured.out


def test_main_not_git_quiet(tmp_path, monkeypatch, capsys):

    (tmp_path / "bad.py").write_text("def f(a, b, c, d, e, f):\n    return a\n")

    monkeypatch.chdir(tmp_path)

    assert main(["--not-git", "--quiet"]) == VIOLATIONS_FOUND
    assert capsys.readouterr().out == ""


def test_main_not_git_with_all_files(tmp_path, monkeypatch, capsys):

    (tmp_path / "a.py").write_text("def f(a, b, c, d, e, f):\n    return a\n")

    monkeypatch.chdir(tmp_path)

    assert main(["--not-git", "--all-files"]) == VIOLATIONS_FOUND
    assert "Too many parameters" in capsys.readouterr().out


def test_main_not_git_nothing_to_review(tmp_path, monkeypatch, capsys):

    monkeypatch.chdir(tmp_path)

    assert main(["--not-git"]) == ERROR

    captured = capsys.readouterr()

    assert captured.out == ""
    assert "error: nothing to review" in captured.err
    assert "hint: no reviewable .py files found on disk" in captured.err


@pytest.mark.parametrize("flag", [["--changed"], ["--staged"]])
def test_main_not_git_rejects_git_dependent_flags(tmp_path, monkeypatch, capsys, flag):

    (tmp_path / "a.py").write_text("def ok():\n    pass\n")

    monkeypatch.chdir(tmp_path)

    assert main(["--not-git", *flag]) == ERROR

    captured = capsys.readouterr()

    assert captured.out == ""
    assert "--not-git cannot be combined with --changed or --staged" in captured.err


def test_main_not_git_works_inside_git_repo(tmp_path, monkeypatch, capsys):

    def git(*args):
        subprocess.run(["git", *args], cwd=tmp_path, check=True, capture_output=True)

    git("init", "-q")
    git("config", "user.email", "test@example.com")
    git("config", "user.name", "Test")

    (tmp_path / "a.py").write_text("def ok():\n    pass\n")
    git("add", "-A")
    git("-c", "commit.gpgsign=false", "commit", "-q", "-m", "initial")

    monkeypatch.chdir(tmp_path)

    assert main(["--not-git"]) == SUCCESS

    assert "All clean." in capsys.readouterr().out


def test_main_help_lists_not_git(capsys):

    with pytest.raises(SystemExit):
        main(["--help"])

    assert "--not-git" in capsys.readouterr().out


def test_main_mutable_default_args_reports_finding(tmp_path, monkeypatch, capsys):

    (tmp_path / "a.py").write_text("def f(items=[]):\n    return items\n")

    _main_git(tmp_path, monkeypatch, "a.py\n")

    assert main([]) == VIOLATIONS_FOUND

    out = capsys.readouterr().out

    assert "SCR017" in out
    assert "Mutable default argument detected" in out


def test_main_mutable_default_args_immutable_defaults_clean(tmp_path, monkeypatch, capsys):

    (tmp_path / "a.py").write_text(
        "def f(a=None, b='', c=0, d=(1, 2), *, e=frozenset()):\n"
        "    return a\n"
    )

    _main_git(tmp_path, monkeypatch, "a.py\n")

    assert main([]) == SUCCESS

    assert "All clean." in capsys.readouterr().out


def test_main_mutable_default_args_keyword_only_default(tmp_path, monkeypatch, capsys):

    (tmp_path / "a.py").write_text("def f(*, opts={}):\n    return opts\n")

    assert _main_json(tmp_path, monkeypatch, "a.py\n") == VIOLATIONS_FOUND

    violation = json.loads(capsys.readouterr().out)["violations"][0]

    assert violation["rule"] == "SCR017"
    assert violation["severity"] == "WARNING"
    assert violation["file"] == "a.py"
    assert violation["name"] == "f"
    assert violation["kind"] == "func"
    assert violation["line"] == 1


def test_main_mutable_default_args_nested_function_flagged_once(tmp_path, monkeypatch, capsys):

    (tmp_path / "a.py").write_text(
        "def outer():\n"
        "    def inner(x=[]):\n"
        "        return x\n"
    )

    assert _main_json(tmp_path, monkeypatch, "a.py\n") == VIOLATIONS_FOUND

    violations = json.loads(capsys.readouterr().out)["violations"]

    scr017 = [v for v in violations if v["rule"] == "SCR017"]

    assert len(scr017) == 1
    assert scr017[0]["name"] == "inner"


def test_reviewable_files_skip_env_dirs(tmp_path, monkeypatch):

    monkeypatch.chdir(tmp_path)

    from avouch.git import get_reviewable_files

    (tmp_path / "app.py").write_text("x = 1\n")

    for dirname in ("testenv", "venv", ".venv", "node_modules", "site-packages", "dist", "build"):
        (tmp_path / dirname).mkdir(exist_ok=True)
        (tmp_path / dirname / "bad.py").write_text("def t():\n    pass\n")

    paths = [str(p.relative_to(tmp_path)) for p in tmp_path.rglob("*.py")]

    reviewable = get_reviewable_files(paths)

    assert reviewable == ["app.py"]
