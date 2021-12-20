import traceback
from textwrap import dedent

from python_runner import PatchedStdinRunner


class MyRunner(PatchedStdinRunner):
    def serialize_traceback(self, exc, source_code):
        return {
            "text": "".join(traceback.format_exception_only(type(exc), exc)),
            "source_code": source_code,
        }


def check_simple(source_code, expected_events):
    runner = MyRunner()
    events = []

    def callback(event_type, data):
        events.append((event_type, data))
        if event_type == "input":
            return f"input: {len(events)}"

    runner.set_callback(callback)
    runner.run(source_code)
    assert events == expected_events


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
