# python_runner

[![Tests](https://github.com/alexmojaki/python_runner/actions/workflows/pytest.yml/badge.svg)](https://github.com/alexmojaki/python_runner/actions/workflows/pytest.yml) [![Coverage Status](https://coveralls.io/repos/github/alexmojaki/python_runner/badge.svg?branch=master)](https://coveralls.io/github/alexmojaki/python_runner?branch=master) [![Supports Python versions 3.8+](https://img.shields.io/pypi/pyversions/python_runner.svg)](https://pypi.python.org/pypi/python_runner)

Run Python code within Python with best practices. Designed for educational use such as [futurecoder](https://futurecoder.io/) and [Papyros](https://github.com/dodona-edu/papyros).

## Advantages over `exec` or `eval`

- Saves source code in a file (if possible) and `linecache` so it can be accessed by tracebacks, `inspect`, `pdb`, `doctest`, etc
- Runs code in a fresh module where `__name__ == "__main__"`
- Allows easy and correct overriding of `sys.stdin/stdout/stderr` and `time.sleep`
- Show full tracebacks with internals hidden
- Support for running async code
- Single callback to handle different kinds of events and output
- Output buffering
- Integration with [`snoop`](https://github.com/alexmojaki/snoop) for debugging
- Integration with [`pyodide-worker-runner`](https://github.com/alexmojaki/pyodide-worker-runner)

## Usage example

```python
from python_runner import PatchedStdinRunner

def get_input(prompt):
    return "some input"

def send_output(part_type, text):
    if part_type == "stdout":
        color = "white"
    elif part_type in ("stderr", "traceback", "syntax_error"):
        color = "red"
    else:
        color = "blue"
    show_output(color, text)

def callback(event_type, data):
    if event_type == "input":
        return get_input(data["prompt"])
    else:
        assert event_type == "output"
        for part in data["parts"]:
            send_output(part["type"], part["text"])

runner = PatchedStdinRunner(callback=callback)
code = """
name = input("Who are you?")
print(f"Hello {name}!")
"""

runner.run(code)

# Calls:
# get_input("Who are you?")
# send_output("input_prompt", "Who are you?")
# send_output("input", "some input")
# send_output("stdout", "Hello some input!")
# send_output("stdout", "\n")
```

## Runners

- `Runner` is the simplest runner. It patches `sys.stdout` and `sys.stderr`.
- `PatchedStdinRunner` also patches `sys.stdin`
- `PatchedSleepRunner` also patches `time.sleep`
- `PyodideRunner` inherits `PatchedStdinRunner` and `PatchedSleepRunner` and is meant to be used in combination with [`pyodide-worker-runner`](https://github.com/alexmojaki/pyodide-worker-runner), especially `makeRunnerCallback`.

## Callback events

Before calling `.run()` or `.run_async()`, you must pass a `callback` to the constructor or `.set_callback()`:

```python
def callback(event_type, data):
    ...

runner = Runner(callback=callback)
# or
runner = Runner()
runner.set_callback(callback)
```

`data` is a dict with string keys and arbitrary values. Custom calls to `runner.callback()` can pass any values, but standard values of `event_type` are:

- `input`:
  - When using `PatchedStdinRunner`
  - `data` will have one key `prompt` which will contain the prompt passed to the `input` function, defaulting to the empty string.
  - The callback should return a string representing one line of user input.
- `output`:
  - `data` will have one key `parts` which will contain a list of output parts. Each part is a dict. The dict may contain anything, but it must contain at least these two keys:
    - `text`: a string containing the output
    - `type`: a code describing the type of output. Custom calls to `runner.output()` can pass any values, but standard values of `type` are:
      - `stdout`: for strings written to `sys.stdout`.
      - `stderr`: for strings written to `sys.stderr`.
      - `traceback`: when code passed to `.run()` or `.run_async()` raises an error at runtime, this part will contain the return value of `.serialize_traceback()`.
      - `syntax_error`: when code passed to `.run()` or `.run_async()` has a syntax error and fails to compile, this part will contain the return value of `.serialize_syntax_error()`.
      - `input_prompt`: the prompt passed to the `input()` function. Only created when `PatchedStdinRunner` is used.
      - `input`: the user's input passed to stdin. Not actually output, but included here because it's typically shown in regular Python consoles. Only created when `PatchedStdinRunner` is used.
      - `snoop`: debugging output from `snoop` when `.run()` is called with `mode='snoop'`.
- `sleep`:
  - When using `PatchedSleepRunner`
  - `data` will have one key `seconds` which will contain the number of seconds to sleep for.

## Running

Call `runner.run()` or `await runner.run_async()` with a string containing Python source code. You can also pass the following optional keyword arguments:

- `mode`:
  - `'exec'`: (default) for running multiple statements normally, like the `exec()` builtin function.
  - `'eval'`: for evaluating the value of a single expression, like the `eval()` builtin function. In this case, `.run()` or `.run_async()` will return the evaluated expression if successful.
  - `'single'`: for running a single statement, printing the value if it's an expression, like the standard Python REPL.
  - `'snoop'`: like `'exec'` but runs the code with the [snoop](https://github.com/alexmojaki/snoop) debugger (installed separately).
- `snoop_config`: only used when `mode='snoop'`. A dict which will be used as keyword arguments for a `snoop.Config` object. For example, `snoop_config=dict(color='monokai')` will enable ANSI color codes in the debugging output.
- `top_level_await`: only for `.run_async()`. If true (the default), the given source code can use the `await` keyword at the top level outside of a function.
