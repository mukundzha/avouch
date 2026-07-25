# Scrut

> Review your code before your teammates do.

Scrut is a fast, terminal-first code review tool that analyzes your local code changes before you commit. It helps catch maintainability issues early, reducing repetitive pull request feedback and making reviews more focused on architecture and business logic.

## Why Scrut?

Most code review comments are predictable:

* "This function is too long."
* "The complexity increased."
* "Too many parameters."
* "This should be extracted into a helper."
* "The nesting is difficult to follow."

Scrut finds these issues before your code reaches a pull request.

## Features

* Review uncommitted code changes
* Analyze only the files you've modified
* Detect maintainability issues
* Fast terminal experience
* Designed for everyday development

## Example

```text
$ scrut

Reviewing changes...

Files analyzed: 3

HIGH
auth.py

• Function complexity increased
• Nesting depth exceeded
• 6 function parameters

Suggestion:
Extract validation into a helper function.

────────────────────────────

Score: 9.1/10

✓ Ready to commit
```

## Roadmap

### v0.1

* Read changed files from Git
* Parse Python code using the AST
* Detect common maintainability issues
* Beautiful CLI output

### Planned

* Additional programming languages
* Custom review rules
* GitHub Pull Request integration
* AI-powered explanations
* Team rule configuration

## Philosophy

Scrut does **not** replace human code reviews.

Instead, it removes repetitive review comments so human reviewers can focus on design, correctness, performance, and architecture.

## Installation

Coming soon.

## Development

```bash
git clone https://github.com/mukundzha/scrut.git
cd scrut

python -m venv .venv
source .venv/bin/activate

pip install -e .
```

## License

MIT License.
