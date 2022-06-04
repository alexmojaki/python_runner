import sys
import time
from contextlib import contextmanager, redirect_stdout, redirect_stderr
from typing import List, Union, Any, Dict


class OutputBuffer:
    """
    Buffers output to reduce the number of callback events.
    """

    # See should_flush
    flush_length = 1000
    flush_time = 1  # seconds

    def __init__(self, flush):
        self._flush = flush
        self.reset()

    def reset(self):
        self.parts: List[Dict[str, Any]] = []
        self.last_time = time.time()

    def put(self, output_type: str, text: Union[str, bytes], **extra):
        if isinstance(text, bytes):
            text = text.decode("utf8", "replace")
        if not isinstance(text, str):
            raise TypeError(f"Can only write str, not {type(text).__name__}")
        assert isinstance(output_type, str)

        if not self.parts or self.parts[-1]["type"] != output_type:
            self.parts.append(dict(type=output_type, text=text, **extra))
        else:
            self.parts[-1]["text"] += text

        if self.should_flush():
            self.flush()

    def should_flush(self) -> bool:
        return (
            len(self.parts) > 1
            or self.last_time and time.time() - self.last_time > self.flush_time
            or sum(len(p["text"]) for p in self.parts) >= self.flush_length
        )

    def flush(self):
        if not self.parts:
            return
        self._flush(self.parts)
        self.reset()

    @contextmanager
    def redirect_std_streams(self):
        with redirect_stdout(SysStream("stdout", self)):  # noqa
            with redirect_stderr(SysStream("stderr", self)):  # noqa
                yield


class SysStream:
    def __init__(self, output_type: str, output_buffer: OutputBuffer):
        self.type = output_type
        self.output_buffer = output_buffer

    def __getattr__(self, item: str):
        return getattr(sys.__stdout__, item)

    def write(self, s: Union[str, bytes]):
        self.output_buffer.put(self.type, s)

    def flush(self):
        self.output_buffer.flush()
