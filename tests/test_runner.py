import traceback

from python_runner import Runner


class MyRunner(Runner):
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

    runner.set_callback(callback)
    runner.run(source_code)
    assert events == expected_events


def test_print():
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
