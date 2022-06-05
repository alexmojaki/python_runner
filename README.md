# python_runner

[![Tests](https://github.com/alexmojaki/python_runner/actions/workflows/pytest.yml/badge.svg)](https://github.com/alexmojaki/python_runner/actions/workflows/pytest.yml) [![Coverage Status](https://coveralls.io/repos/github/alexmojaki/python_runner/badge.svg?branch=master)](https://coveralls.io/github/alexmojaki/python_runner?branch=master) [![Supports Python versions 3.8+](https://img.shields.io/pypi/pyversions/python_runner.svg)](https://pypi.python.org/pypi/python_runner)

Run Python code within Python with best practices. Designed for educational use such as [futurecoder](https://futurecoder.io/) and [Papyros](https://github.com/dodona-edu/papyros).

## Advantages over `exec` or `eval`

- Saves source code in a file (if possible) and `linecache` so it can be accessed by tracebacks, `inspect`, `pdb`, `doctest`, etc
- Runs code in a fresh module where `__name__ == "__main__"`
- Allows easy and correct overriding of `sys.stdin/stdout/stderr` and `time.sleep`
- Single callback to manage different kinds of events and output
- Output buffering
- Run with [`snoop`](https://github.com/alexmojaki/snoop) for debugging
- Integration with [`pyodide-worker-runner`](https://github.com/alexmojaki/pyodide-worker-runner)

## Usage

```python
from python_runner import Runner
import traceback

class MyRunner(Runner):
    def serialize_traceback(self, exc: BaseException) -> dict:
        return dict(text=traceback.format_exc())

```
