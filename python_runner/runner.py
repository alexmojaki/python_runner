import ast
import builtins
import linecache
import logging
import os
import sys
import time
import traceback
from code import InteractiveConsole
from collections.abc import Awaitable
from contextlib import contextmanager
from types import CodeType, ModuleType, TracebackType
from typing import Callable, Any, Dict, Optional, Union

from .output import OutputBuffer

log = logging.getLogger(__name__)


Callback = Callable[[str, Dict[str, Any]], Any]


class Runner:
    OutputBufferClass = OutputBuffer

    def __init__(
        self,
        *,
        callback: Callback = None,
        source_code: str = "",
        filename: str = "my_program.py",
    ):
        self.set_callback(callback)  # type: ignore
        self.set_filename(filename)
        self.set_source_code(source_code)
        self.console = InteractiveConsole()
        self.output_buffer = self.OutputBufferClass(
            lambda parts: self.callback("output", parts=parts)
        )
        self.reset()

    def set_callback(self, callback: Callback):
        self._callback = callback

    def set_filename(self, filename: str):
        self.filename = os.path.normcase(os.path.abspath(filename))

    def set_source_code(self, source_code: str):
        self.source_code = source_code
        # Write to file if permitted by system
        try:
            with open(self.filename, "w") as f:
                f.write(self.source_code)
        except:  # pragma: no cover
            pass 
        linecache.cache[self.filename] = (
            len(self.source_code),
            0,
            [line + "\n" for line in self.source_code.splitlines()],
            self.filename,
        )

    def callback(self, event_type: str, **data):
        """
        Calls the callback function passed to __init__ or set_callback.
        May flush pending output which means the callback function
        may be called with an output event before this one.
        """
        if event_type != "output":
            self.output_buffer.flush()

        return self._callback(event_type, data)

    def output(self, output_type: str, text: str, **extra):
        """
        Saves the given output data to eventually (perhaps immediately)
        send it in a callback with event_type 'output'.
        """
        return self.output_buffer.put(output_type, text, **extra)

    def execute(self, code_obj: CodeType, mode: str = None, snoop_config: dict = None):
        """
        Executes a raw code object. This is an internal method, use `run` or `run_async` instead.
        """
        if mode == "snoop":
            from .snoop import exec_snoop, SnoopStream
            default_config = dict(columns=(), out=SnoopStream(self.output_buffer), color=False)
            exec_snoop(self, code_obj, snoop_config={**default_config, **(snoop_config or {})})
        else:
            return eval(code_obj, self.console.locals)  # type: ignore

    @contextmanager
    def _execute_context(self):
        with self.output_buffer.redirect_std_streams():
            try:
                yield
            except BaseException as e:
                self.output("traceback", **self.serialize_traceback(e))
        self.post_run()

    def run(self, source_code: str, mode: str = "exec", snoop_config: dict = None):
        """
        Run the given Python source_code.
        See also run_async.

        `mode` is typically 'exec', 'eval', or 'single',
        which have the same meanings as for the `compile` builtin.

        `mode` can also be 'snoop' which will run the code with the
        [snoop](https://github.com/alexmojaki/snoop) debugger (installed separately).
        An optional `snoop_config` dict can be passed
        which will be used as keyword arguments for a snoop.Config object.

        If `mode` is 'eval', the return value will be the evaluated expression if successful.
        """
        code_obj = self.pre_run(source_code, mode=mode)
        with self._execute_context():
            if code_obj:
                return self.execute(code_obj, mode=mode, snoop_config=snoop_config)

    async def run_async(
        self,
        source_code: str,
        mode: str = "exec",
        top_level_await: bool = True,
        snoop_config: dict = None,
    ):
        """
        Similar to the `run` method, but async.
        `top_level_await` determines whether the `await` keyword is allowed outside a function.
        """
        code_obj = self.pre_run(source_code, mode, top_level_await=top_level_await)
        with self._execute_context():
            if code_obj:
                result = self.execute(code_obj, mode=mode, snoop_config=snoop_config)
                while isinstance(result, Awaitable):
                    result = await result
                return result

    def skip_traceback_internals(self, tb: TracebackType) -> TracebackType:
        """
        Returns the traceback starting from the first frame in the code that was run,
        skipping frames from python_runner.
        """
        original = tb
        while tb and tb.tb_frame.f_code.co_filename != self.filename:
            tb = tb.tb_next
        if tb:
            return tb
        else:
            return original

    def serialize_traceback(self, exc: BaseException) -> dict:
        """
        Override this method to return a dict containing information about a captured user exception.
        This will ultimately be sent in the callback as output.
        It should at least have a key 'text' with a string value.
        """
        tb = self.skip_traceback_internals(exc.__traceback__)
        lines = traceback.format_exception(type(exc), exc, tb)
        return dict(text="".join(lines))

    def serialize_syntax_error(self, exc: BaseException) -> dict:
        """
        Similar to serialize_traceback but called when there's a SyntaxError while compiling user code.
        """
        return self.serialize_traceback(exc)

    def pre_run(
        self, source_code, mode="exec", top_level_await=False
    ) -> Optional[CodeType]:
        """
        Compiles source_code into a code object.
        """
        compile_mode = mode
        if mode == "single":
            source_code += "\n"  # Allow compiling single-line compound statements
        elif mode != "eval":
            compile_mode = "exec"
            self.reset()
        self.output_buffer.reset()

        self.set_source_code(source_code)

        try:
            return compile(
                self.source_code,
                self.filename,
                compile_mode,
                flags=top_level_await * ast.PyCF_ALLOW_TOP_LEVEL_AWAIT,
            )
        except SyntaxError as e:
            try:
                if not ast.parse(self.source_code).body:
                    # Code is only comments, which cannot be compiled in 'single' mode
                    return None
            except SyntaxError:
                pass

            e.__traceback__ = None
            self.output("syntax_error", **self.serialize_syntax_error(e))
            return None

    def post_run(self):
        self.output_buffer.flush()

    def reset(self):
        """
        Called before running code 'from scratch' (i.e. when `mode` is not 'single' or 'eval')
        to reset state such as global variables.
        """
        mod = ModuleType("__main__")
        mod.__file__ = self.filename
        sys.modules["__main__"] = mod
        self.console.locals = mod.__dict__
        self.output_buffer.reset()


class FakeStdin:
    def __init__(self, readline):
        self.readline = readline

    def __getattr__(self, item):
        return getattr(sys.__stdin__, item)

    def __next__(self):
        return self.readline()

    def __iter__(self):
        return self


class PatchedStdinRunner(Runner):  # noqa
    def pre_run(self, *args, **kwargs):
        sys.stdin = FakeStdin(self.readline)
        builtins.input = self.input
        return super().pre_run(*args, **kwargs)

    def reset(self):
        super().reset()
        self.line = ""

    def non_str_input(self, value: Any):
        raise TypeError(f"Callback for input should return str, not {type(value).__name__}")

    def readline(self, n=-1, prompt="") -> str:
        if not self.line and n:
            value = self.callback("input", prompt=prompt)
            if not isinstance(value, str):
                value = self.non_str_input(value) or ""
            if not value.endswith("\n"):
                value += "\n"
            self.output("input", value)
            self.line = value

        if n < 0 or n > len(self.line):
            n = len(self.line)
        to_return = self.line[:n]
        self.line = self.line[n:]
        return to_return

    def input(self, prompt="") -> str:
        self.output("input_prompt", prompt)
        return self.readline(prompt=prompt)[:-1]  # Remove trailing newline


class PatchedSleepRunner(Runner):  # noqa
    def pre_run(self, *args, **kwargs):
        time.sleep = self.sleep
        return super().pre_run(*args, **kwargs)

    def sleep(self, seconds: Union[int, float]):
        if not isinstance(seconds, (int, float)):
            raise TypeError(f"an integer is required (got type {type(seconds).__name__})")
        if not seconds >= 0:
            raise ValueError("sleep length must be non-negative")
        return self.callback("sleep", seconds=seconds)


class PyodideRunner(PatchedStdinRunner, PatchedSleepRunner):  # noqa # pragma: no cover
    """
    For use with https://github.com/alexmojaki/pyodide-worker-runner, especially `makeRunnerCallback`.
    """

    ServiceWorkerError = RuntimeError(
        "The service worker for reading input isn't working. "
        "Try closing all this site's tabs, then reopening. "
        "If that doesn't work, try using a different browser."
    )

    NoChannelError = RuntimeError(
        "This browser doesn't support reading input. "
        "Try upgrading to the most recent version or switching to a different browser, "
        "e.g. Chrome or Firefox."
    )
    InterruptError = KeyboardInterrupt

    def pyodide_error(self, e: Exception):
        import pyodide  # type: ignore  # noqa

        js_error = e.js_error  # type: ignore
        typ = getattr(js_error, "type", "")
        err = getattr(self, typ, None)
        if err:
            raise err from None
        else:
            raise

    def readline(self, *args, **kwargs):
        try:
            return super().readline(*args, **kwargs)
        except Exception as e:
            self.pyodide_error(e)

    def sleep(self, *args, **kwargs):
        try:
            return super().sleep(*args, **kwargs)
        except Exception as e:
            try:
                self.pyodide_error(e)
            except RuntimeError as re:
                if re not in (self.ServiceWorkerError, self.NoChannelError):
                    raise
