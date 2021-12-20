import traceback

from python_runner import Runner


class MyRunner(Runner):
    def serialize_traceback(self, exc, source_code):
        return {"text": "".join(traceback.format_exception_only(type(exc), exc)), "source": source_code}


def test_basic():
    runner = MyRunner()
    events = []
    def callback(event_type, data):
        events.append((event_type, data))
    runner.set_callback(callback)

    runner.run("print(1); print(2)")
    assert events == [('output', {'parts': [{'text': '1\n2\n', 'type': 'stdout'}]})]

    events = []
    runner.run("a b")
    assert events == [('output', {'parts': [{'type': 'syntax_error', 'text': '  File "my_program.py", line 1\n    a b\n      ^\nSyntaxError: invalid syntax\n', 'source': 'a b'}]})]

    events = []
    runner.run("nonexistent")
    assert events == [('output', {'parts': [{'type': 'traceback', 'text': "NameError: name 'nonexistent' is not defined\n", 'source': 'nonexistent'}]})]
