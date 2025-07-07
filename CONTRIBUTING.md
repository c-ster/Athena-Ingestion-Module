# Contributing to Athena Ingestion Module

We're excited that you're interested in contributing to Athena! Here's how you can help:

## 🛠 Development Setup

1. Fork the repository and clone it locally
2. Set up a Python virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
3. Install development dependencies:
   ```bash
   pip install -r requirements-dev.txt
   ```
4. Install pre-commit hooks:
   ```bash
   pre-commit install
   ```

## 🧪 Testing

Run the test suite with:
```bash
pytest
```

## 📝 Pull Request Process

1. Create a new branch for your feature/fix:
   ```bash
   git checkout -b feature/amazing-feature
   ```
2. Make your changes and write tests
3. Run tests and ensure they pass
4. Update the documentation if needed
5. Submit a pull request with a clear description of changes

## 🐛 Reporting Issues

When reporting issues, please include:
- Steps to reproduce
- Expected behavior
- Actual behavior
- Environment details (OS, Python version, etc.)

## 📜 Code Style

- Follow [PEP 8](https://www.python.org/dev/peps/pep-0008/) for Python code
- Use type hints for better code clarity
- Write docstrings for all public functions and classes
- Keep commits small and focused on a single change
