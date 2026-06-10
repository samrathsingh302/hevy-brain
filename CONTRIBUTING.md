# Contribution guidelines

Contributing to this project should be as easy and transparent as possible,
whether it's:

- Reporting a bug
- Discussing the current state of the code
- Submitting a fix
- Proposing new features

## GitHub is used for everything

GitHub is used to host code, to track issues and feature requests, as well as
accept pull requests.

1. Fork the repo and create your branch from `main`.
2. If you've changed something, update the documentation.
3. Make sure your code lints (`ruff check` + `ruff format --check`).
4. Make sure the tests pass (`pytest tests`).
5. Issue that pull request!

## Development setup

```sh
pip install -e ".[dev]"
python -m pytest tests -q
python -m ruff check hevy_brain tests
python -m ruff format hevy_brain tests
```

Tests must never hit the real Hevy or Anthropic APIs — use the fake clients
in `tests/` as a pattern.

## Any contributions you make will be under the MIT Software License

In short, when you submit code changes, your submissions are understood to be
under the same [MIT License](LICENSE) that covers the project.

## Report bugs using GitHub's issues

Report a bug by opening a new issue — it's that easy!

**Great bug reports** tend to have:

- A quick summary and/or background
- Steps to reproduce (be specific, give sample code if you can)
- What you expected would happen
- What actually happens
- Notes (possibly including why you think this might be happening)
