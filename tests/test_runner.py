import traceback
from textwrap import dedent

from python_runner import PatchedStdinRunner


class MyRunner(PatchedStdinRunner):
    def serialize_traceback(self, exc, source_code):
        return {
            "text": "".join(traceback.format_exception_only(type(exc), exc)),
            "source_code": source_code,
        }


events = []


def default_callback(event_type, data):
    events.append((event_type, data))
    if event_type == "input":
        return f"input: {len(events)}"


def check_simple(source_code, expected_events, mode="exec", callback=default_callback):
    global events
    events = []

    runner = MyRunner(callback=callback)
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
    check_simple(
        "a b",
        [
            (
                "output",
                {
                    "parts": [
                        {
                            "type": "syntax_error",
                            "text": (
                                '  File "my_program.py", line 1\n'
                                "    a b\n"
                                "      ^\n"
                                "SyntaxError: invalid syntax\n"
                            ),
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


def test_non_str_input():
    def callback(event_type, data):
        if event_type == "input":
            return
        return default_callback(event_type, data)

    check_simple(
        "input()",
        callback=callback,
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
    check_simple("", [])


def test_comments_only():
    check_simple("#foo\n#bar\n", [])
