import ast
import builtins
import linecache
import logging
import sys
from code import InteractiveConsole
from types import ModuleType

from .output import OutputBuffer

log = logging.getLogger(__name__)


class Runner:
    OutputBufferClass = OutputBuffer

    def __init__(
        self,
        *,
        callback=None,
        filename="my_program.py",
    ):
        self.set_callback(callback)
        self.filename = filename

        self.console = InteractiveConsole()
        self.output_buffer = self.OutputBufferClass(
            lambda parts: self.callback("output", parts=parts)
        )
        self.reset()

    def set_callback(self, callback):
        self._callback = callback

    def callback(self, event_type, **data):
        if event_type != "output":
            self.output_buffer.flush()

        return self._callback(event_type, data)

    def output(self, output_type, text, **extra):
        return self.output_buffer.put(output_type, text, **extra)

    def execute(self, code_obj, source_code, mode=None):  # noqa
        with self.output_buffer.redirect_std_streams():
            try:
                return eval(code_obj, self.console.locals)  # noqa
            except Exception as e:
                self.output("traceback", **self.serialize_traceback(e, source_code))

    def serialize_traceback(self, exc, source_code):  # noqa
        raise NotImplementedError  # pragma: no cover

    def serialize_syntax_error(self, exc, source_code):
        return self.serialize_traceback(exc, source_code)

    def run(self, source_code, mode="exec"):
        compile_mode = mode
        if mode == "single":
            source_code += "\n"  # Allow compiling single-line compound statements
        elif mode != "eval":
            compile_mode = "exec"
            self.reset()

        filename = self.filename
        linecache.cache[filename] = (
            len(source_code),
            0,
            [line + "\n" for line in source_code.splitlines()],
            filename,
        )

        result = None

        try:
            code_obj = compile(source_code, filename, compile_mode)
        except SyntaxError as e:
            try:
                if not ast.parse(source_code).body:
                    # Code is only comments, which cannot be compiled in 'single' mode
                    return
            except SyntaxError:
                pass

            self.output("syntax_error", **self.serialize_syntax_error(e, source_code))
        else:
            result = self.execute(code_obj, source_code, mode)

        self.output_buffer.flush()
        return result

    def reset(self):
        mod = ModuleType("__main__")
        mod.__file__ = self.filename
        sys.modules["__main__"] = mod
        self.console.locals = mod.__dict__
        self.output_buffer.reset()


class PatchedStdinRunner(Runner):  # noqa
    def execute(self, code_obj, source_code, mode=None):  # noqa
        sys.stdin.readline = self.readline
        builtins.input = self.input
        return super().execute(code_obj, source_code, mode)

    def reset(self):
        super().reset()
        self.line = ""

    def non_str_input(self):
        raise TypeError(f"Callback for input should return str, not {type(self.line).__name__}")

    def readline(self, n=-1, prompt=""):
        if not self.line and n:
            self.line = self.callback("input", prompt=prompt)
            if not isinstance(self.line, str):
                self.non_str_input()
            if not self.line.endswith("\n"):
                self.line += "\n"
            self.output("input", self.line)

        if n < 0 or n > len(self.line):
            n = len(self.line)
        to_return = self.line[:n]
        self.line = self.line[n:]
        return to_return

    def input(self, prompt=""):
        self.output("input_prompt", prompt)
        return self.readline(prompt=prompt)[:-1]  # Remove trailing newline
