# Contributing to AURIX

Thank you for your interest in contributing to AURIX! This document provides guidelines for contributing to the project.

## Code of Conduct

By participating in this project, you agree to abide by our [Code of Conduct](CODE_OF_CONDUCT.md).

## How to Contribute

### Reporting Bugs

1. Check if the bug has already been reported in [Issues](https://github.com/cstpalash/aurix/issues)
2. If not, create a new issue with:
   - Clear, descriptive title
   - Steps to reproduce
   - Expected vs actual behavior
   - Environment details (Python version, OS)

### Suggesting Features

1. Check existing issues and discussions for similar ideas
2. Open a new issue with the `enhancement` label
3. Describe the use case and proposed solution

### Pull Requests

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Make your changes
4. Add tests for new functionality
5. Run the test suite: `pytest`
6. Commit with clear messages: `git commit -m "Add feature X"`
7. Push to your fork: `git push origin feature/your-feature`
8. Open a Pull Request

## Development Setup

```bash
# Clone your fork
git clone https://github.com/YOUR_USERNAME/aurix.git
cd aurix

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"

# Run tests
pytest
```

## Code Style

- Follow PEP 8 guidelines
- Use type hints where appropriate
- Add docstrings to public functions and classes
- Keep functions focused and small

## Commit Messages

- Use present tense: "Add feature" not "Added feature"
- Be descriptive but concise
- Reference issues when applicable: "Fix #123: Handle edge case"

## Testing

- Write tests for new features
- Ensure all tests pass before submitting PR
- Aim for meaningful coverage, not just line coverage

## Documentation

- Update README.md for user-facing changes
- Add docstrings for new public APIs
- Include examples for complex features

## Review Process

1. A maintainer will review your PR
2. Address any requested changes
3. Once approved, a maintainer will merge

## Questions?

Open an issue with the `question` label or start a discussion.

Thank you for contributing!
