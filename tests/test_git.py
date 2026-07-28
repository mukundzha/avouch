import ast
from unittest.mock import Mock, patch

from scrut.cli import (
    get_reviewable_files,
    get_depth,
    read_file,
    get_changed_files,
    is_gitrepo,
)


def test_get_reviewable_files(tmp_path):

    main = tmp_path / "main.py"
    hello = tmp_path / "hello.py"
    readme = tmp_path / "README.md"
    notes = tmp_path / "notes.txt"
    image = tmp_path / "image.png"

    main.write_text("")
    hello.write_text("")
    readme.write_text("")
    notes.write_text("")
    image.write_text("")

    files = [
        str(main),
        str(readme),
        str(notes),
        str(hello),
        str(image),
    ]

    result = get_reviewable_files(files)

    assert result == [
        str(main),
        str(hello),
    ]


def test_get_depth_no_nesting():
  
    code = """
def foo():
    pass
"""

    tree = ast.parse(code)
    function = tree.body[0]

    assert get_depth(function) == 0


def test_get_depth_nested():

    code = """
def foo():
    if True:
        while True:
            for i in range(5):
                pass
"""

    tree = ast.parse(code)
    function = tree.body[0]

    assert get_depth(function) == 3


def test_read_file(tmp_path):

    file = tmp_path / "sample.py"

    file.write_text("print('Hello')")

    result = read_file(file)

    assert result == "print('Hello')"


@patch("subprocess.run")
def test_get_changed_files(mock_run):

    mock_run.return_value = Mock(
        stdout="main.py\nhello.py\nREADME.md\n",
        returncode=0,
    )

    result = get_changed_files()

    assert result == [
        "main.py",
        "hello.py",
        "README.md",
    ]


@patch("subprocess.run")
def test_is_gitrepo_true(mock_run):

    mock_run.return_value = Mock(returncode=0)

    assert is_gitrepo() is True


@patch("subprocess.run")
def test_is_gitrepo_false(mock_run):

    mock_run.return_value = Mock(returncode=1)

    assert is_gitrepo() is False