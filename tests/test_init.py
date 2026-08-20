import tomllib
from pathlib import Path

from avouch.cli import main, SUCCESS, VIOLATIONS_FOUND, ERROR
from avouch.config.default import DEFAULT_LIMITS


def _write(tmp_path, name, content):
    path = tmp_path / name
    path.write_text(content)
    return path


def test_init_writes_measured_plus_one(tmp_path, monkeypatch, capsys):

    _write(
        tmp_path,
        "app.py",
        "def lots_of_args(a, b, c, d, e, f):\n"
        "    return a + b + c + d + e + f\n",
    )

    monkeypatch.chdir(tmp_path)

    result = main(["init"])

    assert result == SUCCESS
    assert "measured 12 maxima" in capsys.readouterr().out

    with open("avouch.toml", "rb") as file:
        config = tomllib.load(file)

    assert config["limits"]["max_parameters"] == 7
    assert config["limits"]["max_file_lines"] == 3


def test_init_dry_run_creates_nothing(tmp_path, monkeypatch, capsys):

    _write(tmp_path, "app.py", "def a():\n    pass\n")

    monkeypatch.chdir(tmp_path)

    result = main(["init", "--dry-run"])

    assert result == SUCCESS
    assert not Path("avouch.toml").exists()
    assert "[limits]" in capsys.readouterr().out


def test_init_zero_evidence_keeps_defaults(tmp_path, monkeypatch):

    _write(tmp_path, "app.py", "")

    monkeypatch.chdir(tmp_path)

    assert main(["init"]) == SUCCESS

    with open("avouch.toml", "rb") as file:
        config = tomllib.load(file)

    assert config["limits"] == DEFAULT_LIMITS


def test_init_then_all_clean(tmp_path, monkeypatch, capsys):

    _write(
        tmp_path,
        "app.py",
        "def busy(a, b, c):\n"
        "    if a:\n"
        "        return 1\n"
        "    elif b:\n"
        "        return 2\n"
        "    elif c:\n"
        "        return 3\n"
        "    return 0\n",
    )

    monkeypatch.chdir(tmp_path)

    assert main(["init"]) == SUCCESS

    result = main(["--not-git"])

    assert "All clean." in capsys.readouterr().out
    assert result == SUCCESS


def test_init_new_violation_still_reported(tmp_path, monkeypatch, capsys):

    _write(tmp_path, "app.py", "def ok(a, b):\n    return a\n")

    monkeypatch.chdir(tmp_path)

    assert main(["init"]) == SUCCESS

    _write(
        tmp_path,
        "app.py",
        "def too_many(a, b, c, d, e, f, g, h, i):\n    return a\n",
    )

    result = main(["--not-git"])

    assert result == VIOLATIONS_FOUND
    assert "Too many parameters" in capsys.readouterr().out


def test_init_preserves_rules_and_ignore_paths(tmp_path, monkeypatch):

    _write(
        tmp_path,
        "avouch.toml",
        "ignore_paths = [\"legacy/\"]\n\n[rules]\nmax_parameters = false\n",
    )
    _write(tmp_path, "app.py", "def ok(a, b):\n    return a\n")

    monkeypatch.chdir(tmp_path)

    assert main(["init"]) == SUCCESS

    with open("avouch.toml", "rb") as file:
        config = tomllib.load(file)

    assert config["rules"]["max_parameters"] is False
    assert config["ignore_paths"] == ["legacy/"]
    assert config["limits"]["max_parameters"] == DEFAULT_LIMITS["max_parameters"]


def test_init_conflicts_with_review_flags(tmp_path, monkeypatch, capsys):

    _write(tmp_path, "app.py", "def ok():\n    pass\n")

    monkeypatch.chdir(tmp_path)

    result = main(["init", "--all-files"])

    assert result == ERROR
    assert "cannot be combined" in capsys.readouterr().err
    assert not Path("avouch.toml").exists()