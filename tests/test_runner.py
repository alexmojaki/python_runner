import asyncio
import builtins
import os
import sys
import time
import traceback
from textwrap import dedent

import pytest

from python_runner import PatchedStdinRunner, PatchedSleepRunner
from python_runner.output import OutputBuffer


class MyRunner(PatchedStdinRunner):
    def serialize_traceback(self, exc):
        return {
            "text": "".join(traceback.format_exception_only(type(exc), exc)),
            "source_code": self.source_code,
        }


events = []

def default_filename():
    return os.path.normcase(os.path.abspath("my_program.py"))

def default_callback(event_type, data):
    events.append((event_type, data))
    if event_type == "input":
        return f"input: {len(events)}"


def check_simple(
    source_code,
    expected_events,
    mode="exec",
    runner=None,
    flush_time=OutputBuffer.flush_time,
):
    OutputBuffer.flush_time = flush_time

    global events
    events = []

    runner = runner or MyRunner(callback=default_callback)
    result = runner.run(source_code, mode=mode)
    assert events == expected_events
    if mode != "eval":
        assert result is None
    return result


def test_simple_print():
    check_simple(
        "print(1); print(2)",
        [
            (
                "output",
                {
                    "parts": [
                        {
                            "type": "stdout",
                            "text": "1\n2\n",
                        },
                    ],
                },
            ),
        ],
    )


def test_stdout_bytes():
    check_simple(
        "import sys; sys.stdout.write(b'abc' + '☃'.encode())",
        [
            (
                "output",
                {
                    "parts": [
                        {
                            "type": "stdout",
                            "text": "abc☃",
                        },
                    ],
                },
            ),
        ],
    )


def test_stdout_write_non_str():
    check_simple(
        "import sys; sys.stdout.write(123)",
        [
            (
                "output",
                {
                    "parts": [
                        {
                            "type": "traceback",
                            "text": "TypeError: Can only write str, not int\n",
                            "source_code": "import sys; sys.stdout.write(123)",
                        }
                    ],
                },
            ),
        ],
    )


def test_stdout_attrs():
    check_simple(
        "import sys; print(sys.stdout.encoding, callable(sys.stdout.isatty))",
        [
            (
                "output",
                {
                    "parts": [
                        {
                            "type": "stdout",
                            "text": "utf-8 True\n",
                        },
                    ],
                },
            ),
        ],
    )


def test_mixed_output():
    source = dedent(
        """
        import sys
        
        print(1)
        print(2)
        
        print(3, file=sys.stderr)
        print(4, file=sys.stderr)
        
        print(5)
        print(6)
        
        print(7, file=sys.stderr)
        print(8, file=sys.stderr)
        
        1/0
        """
    )
    check_simple(
        source,
        [
            (
                "output",
                {
                    "parts": [
                        {"type": "stdout", "text": "1\n2\n"},
                        {"type": "stderr", "text": "3"},
                    ]
                },
            ),
            (
                "output",
                {
                    "parts": [
                        {"type": "stderr", "text": "\n4\n"},
                        {"type": "stdout", "text": "5"},
                    ]
                },
            ),
            (
                "output",
                {
                    "parts": [
                        {"type": "stdout", "text": "\n6\n"},
                        {"type": "stderr", "text": "7"},
                    ]
                },
            ),
            (
                "output",
                {
                    "parts": [
                        {
                            "type": "stderr",
                            "text": "\n8\n",
                        },
                        {
                            "type": "traceback",
                            "text": "ZeroDivisionError: division by zero\n",
                            "source_code": source,
                        },
                    ]
                },
            ),
        ],
    )


def test_syntax_error():
    filename = default_filename()
    text = (
        f'  File "{filename}", line 1\n'
        "    a b\n"
        "      ^\n"
        "SyntaxError: invalid syntax\n"
    )

    check_simple(
        "a b",
        [
            (
                "output",
                {
                    "parts": [
                        {
                            "type": "syntax_error",
                            "text": text,
                            "source_code": "a b",
                        }
                    ]
                },
            )
        ],
    )


def test_runtime_error():
    check_simple(
        "nonexistent",
        [
            (
                "output",
                {
                    "parts": [
                        {
                            "type": "traceback",
                            "text": "NameError: name 'nonexistent' is not defined\n",
                            "source_code": "nonexistent",
                        }
                    ]
                },
            )
        ],
    )


def test_simple_input():
    check_simple(
        "input('some_prompt'); print('after')",
        [
            (
                "output",
                {
                    "parts": [
                        {"type": "input_prompt", "text": "some_prompt"},
                    ]
                },
            ),
            (
                "input",
                {"prompt": "some_prompt"},
            ),
            (
                "output",
                {
                    "parts": [
                        {"type": "input", "text": "input: 2\n"},
                        {"type": "stdout", "text": "after"},
                    ]
                },
            ),
            (
                "output",
                {
                    "parts": [
                        {"type": "stdout", "text": "\n"},
                    ]
                },
            ),
        ],
    )


def test_iter_stdin():
    check_simple(
        "import sys; print(next(iter(sys.stdin))); print(sys.stdin.close.__name__)",
        [
            (
                "input",
                {"prompt": ""},
            ),
            (
                "output",
                {
                    "parts": [
                        {"text": "input: 1\n", "type": "input"},
                        {"text": "input: 1\n", "type": "stdout"},
                    ]
                },
            ),
            (
                "output",
                {
                    "parts": [
                        {"text": "\nclose\n", "type": "stdout"},
                    ]
                },
            ),
        ],
    )


def test_non_str_input():
    def callback(event_type, data):
        if event_type == "input":
            return
        return default_callback(event_type, data)

    check_simple(
        "input()",
        runner=MyRunner(callback=callback),
        expected_events=[
            (
                "output",
                {
                    "parts": [
                        {
                            "type": "input_prompt",
                            "text": "",
                        },
                    ],
                },
            ),
            (
                "output",
                {
                    "parts": [
                        {
                            "type": "traceback",
                            "text": "TypeError: Callback for input should return str, not NoneType\n",
                            "source_code": "input()",
                        }
                    ]
                },
            ),
        ],
    )


def test_custom_non_str_input():
    class Runner(MyRunner):
        def non_str_input(self, value):
            print(repr(value))

    def callback(event_type, data):
        if event_type == "input":
            return 123
        return default_callback(event_type, data)

    runner = Runner(callback=callback)
    assert runner.line == ""

    check_simple(
        "input()",
        runner=runner,
        expected_events=[
            (
                "output",
                {
                    "parts": [
                        {"text": "", "type": "input_prompt"},
                    ],
                },
            ),
            (
                "output",
                {
                    "parts": [
                        {"text": "123\n", "type": "stdout"},
                        {"text": "\n", "type": "input"},
                    ]
                },
            ),
        ],
    )

    assert runner.line == ""


def test_single():
    check_simple(
        "1 + 2",
        [
            (
                "output",
                {
                    "parts": [
                        {"type": "stdout", "text": "3\n"},
                    ],
                },
            ),
        ],
        mode="single",
    )

    check_simple(
        "for i in range(2): print(i)",
        [
            (
                "output",
                {
                    "parts": [
                        {"type": "stdout", "text": "0\n1\n"},
                    ],
                },
            ),
        ],
        mode="single",
    )


def test_eval():
    assert 3 == check_simple(
        "1 + 2",
        [],
        mode="eval",
    )


def test_empty():
    for mode in ["single", "eval", "exec"]:
        for source in ["", "#", "#foo", "#foo\n#bar\n", "\n", " "]:
            check_simple(source, [], mode=mode)


def test_flush_direct():
    check_simple(
        dedent(
            """
            import sys
            
            print(1)
            print(2)
            
            sys.stdout.flush()
            sys.stdout.flush()
            
            print(3)
            print(4)
            """
        ),
        [
            ("output", {"parts": [{"type": "stdout", "text": "1\n2\n"}]}),
            ("output", {"parts": [{"type": "stdout", "text": "3\n4\n"}]}),
        ],
    )


def test_flush_time():
    check_simple(
        dedent(
            """
            import time

            print(1)
            print(2)

            time.sleep(0.11)

            print(3)
            print(4)
            """
        ),
        [
            ("output", {"parts": [{"type": "stdout", "text": "1\n2\n3"}]}),
            ("output", {"parts": [{"type": "stdout", "text": "\n4\n"}]}),
        ],
        flush_time=0.1,
    )


def test_flush_big_output():
    check_simple(
        dedent(
            """
            for i in range(3000):
                print(9)
            """
        ),
        [
            ("output", {"parts": [{"type": "stdout", "text": "9\n" * 500}]}),
        ] * 6,
    )


def test_console_locals():
    runner = MyRunner(callback=default_callback)
    base_locals = {
        "__name__": "__main__",
        "__doc__": None,
        "__package__": None,
        "__loader__": None,
        "__spec__": None,
        "__file__": default_filename(),
        "__builtins__": builtins.__dict__,
    }

    check_simple("x = 1", [], runner=runner)
    assert runner.console.locals == {**base_locals, "x": 1}

    check_simple("y = 2", [], runner=runner)
    assert runner.console.locals == {**base_locals, "y": 2}

    check_simple("z = 3", [], runner=runner, mode="single")
    assert runner.console.locals == {**base_locals, "y": 2, "z": 3}


def test_await_syntax_error():
    filename = default_filename()
    if sys.version_info[:2] >= (3, 10):
        text = (
            f'  File "{filename}", line 1\n'
            "    await b\n"
            "    ^^^^^^^\n"
            "SyntaxError: 'await' outside function\n"
        )
    else:
        text = (
            f'  File "{filename}", line 1\n'
            "    await b\n"
            "    ^\n"
            "SyntaxError: 'await' outside function\n"
        )
    check_simple(
        "await b",
        [
            (
                "output",
                {
                    "parts": [
                        {
                            "type": "syntax_error",
                            "text": text,
                            "source_code": "await b",
                        }
                    ]
                },
            )
        ],
    )


def test_sleep():
    class SleepRunner(MyRunner, PatchedSleepRunner):
        pass

    check_simple(
        "import time; time.sleep(123)",
        [
            (
                "sleep",
                {"seconds": 123},
            ),
        ],
        runner=SleepRunner(callback=default_callback),
    )


def test_await():
    global events
    events = []

    runner = MyRunner(callback=default_callback)
    result = runner.run_async(
        dedent(
            """
    async def foo():
        print('hi')
    
    await foo()
            """
        )
    )
    assert events == []
    asyncio.run(result, debug=True)
    assert events == [
        (
            "output",
            {
                "parts": [
                    {"type": "stdout", "text": "hi\n"},
                ],
            },
        ),
    ]


def test_async_without_await():
    global events
    events = []

    runner = MyRunner(callback=default_callback)
    result = runner.run_async(
        dedent(
            """
    def foo():
        print('hi')

    foo()
            """
        )
    )
    assert events == []
    asyncio.run(result, debug=True)
    assert events == [
        (
            "output",
            {
                "parts": [
                    {"type": "stdout", "text": "hi\n"},
                ],
            },
        ),
    ]


def test_invalid_sleep():
    runner = PatchedSleepRunner()
    for arg in [-1, float('nan'), "", 1+2j, None]:
        with pytest.raises(Exception):
            try:
                time.sleep(arg)
            except Exception as e:
                assert isinstance(e, (ValueError, TypeError))
                with pytest.raises(type(e)):
                    runner.sleep(arg)
                raise

def test_snoop():
    filename = default_filename()
    code = dedent(
        """
    def double(x):
        return 2*x

    double(5)
        """)
    check_simple(code, [
        ('output', {'parts': [{'type': 'snoop', 'text': (
            '    2 | def double(x):\n'
            '    5 | double(5)\n'  
           f'     >>> Call to double in File "{filename}", line 2\n'
            '     ...... x = 5\n'
            '        2 | def double(x):\n'
            '        3 |     return 2*x\n'
            '     <<< Return value from double: 10\n'
            '    5 | double(5)\n'
            )}]})
        ], mode="snoop")
