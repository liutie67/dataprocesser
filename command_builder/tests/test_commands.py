import pytest

from command_builder.commands import build_command, parse_command
from command_builder.models import CommandArgument, ParseCommandRequest, ProfilePayload


def argument(**overrides):
    values = {
        "id": "arg-1",
        "position": 0,
        "mode": "named",
        "token": "--budget",
        "value_type": "int",
        "value": "120",
        "choices": [],
        "enabled": True,
    }
    values.update(overrides)
    return CommandArgument(**values)


def profile(**overrides):
    values = {
        "name": "测试配置",
        "script_path": r".\testbench.py",
        "prefix": "python",
        "shell": "powershell",
        "arguments": [
            argument(),
            argument(id="arg-2", position=1, token="--od-limit", value="0"),
        ],
    }
    values.update(overrides)
    return ProfilePayload(**values)


def test_generates_requested_example():
    assert (
        build_command(profile())
        == r"python .\testbench.py --budget 120 --od-limit 0"
    )


def test_powershell_quotes_paths_and_strings():
    built = build_command(
        profile(
            script_path=r"C:\My Project\testbench.py",
            arguments=[
                argument(token="--name", value_type="str", value="O'Brien")
            ],
        )
    )
    assert built == r"python 'C:\My Project\testbench.py' --name 'O''Brien'"


def test_uv_prefix_positionals_choices_and_boolean():
    built = build_command(
        profile(
            prefix="uv_run_python",
            arguments=[
                argument(
                    id="positional",
                    mode="positional",
                    token="",
                    value_type="choice",
                    choices=["quick", "full"],
                    value="full",
                ),
                argument(
                    id="verbose",
                    position=1,
                    token="--verbose",
                    value_type="bool",
                    value=True,
                ),
                argument(
                    id="hidden",
                    position=2,
                    token="--hidden",
                    value_type="bool",
                    value=False,
                ),
                argument(
                    id="disabled",
                    position=3,
                    token="--skip",
                    value_type="str",
                    value="unused",
                    enabled=False,
                ),
            ],
        )
    )
    assert built == r"uv run python .\testbench.py full --verbose"


def test_bash_uses_shell_quoting():
    built = build_command(
        profile(
            shell="bash",
            script_path="scripts/my test.py",
            arguments=[argument(token="--label", value_type="str", value="hello world")],
        )
    )
    assert built == "python 'scripts/my test.py' --label 'hello world'"


def test_module_and_py_launcher():
    built = build_command(
        profile(
            prefix="py",
            invocation_mode="module",
            script_path="package.worker",
            arguments=[argument(token="--limit", value="-3")],
        )
    )
    assert built == "py -m package.worker --limit -3"


def test_parse_uv_script_with_named_positionals_and_separator():
    parsed = parse_command(
        ParseCommandRequest(
            command=r"uv run python .\testbench.py --budget 20 input.jpg --verbose -- --literal",
            dialect="powershell",
        )
    )
    assert parsed.draft.prefix == "uv_run_python"
    assert parsed.draft.invocation_mode == "script"
    assert parsed.draft.script_path == r".\testbench.py"
    assert [item.mode for item in parsed.draft.arguments] == [
        "named",
        "positional",
        "named",
        "positional",
        "positional",
    ]
    assert parsed.draft.arguments[0].value == 20
    assert parsed.draft.arguments[2].value is True
    assert parsed.draft.arguments[-1].value == "--literal"


def test_parse_module_equals_repeated_flags_and_negative_number():
    parsed = parse_command(
        ParseCommandRequest(
            command="python -m package.worker --tag=first --tag second --threshold -0.5",
            dialect="bash",
        )
    )
    assert parsed.draft.invocation_mode == "module"
    assert parsed.draft.script_path == "package.worker"
    assert [item.token for item in parsed.draft.arguments] == ["--tag", "--tag", "--threshold"]
    assert parsed.draft.arguments[-1].value == -0.5


@pytest.mark.parametrize(
    ("command", "dialect", "message"),
    [
        ("python -c 'print(1)'", "bash", "-c"),
        ("python -u tool.py", "powershell", "解释器选项"),
        ("python tool.py | more", "cmd", "暂不支持"),
        ("python 'tool.py", "bash", "引号"),
        ("git status", "bash", "仅支持"),
    ],
)
def test_parse_rejects_unsupported_commands(command, dialect, message):
    with pytest.raises(ValueError, match=message):
        parse_command(ParseCommandRequest(command=command, dialect=dialect))


def test_auto_detects_bash_and_preserves_quoted_values():
    parsed = parse_command(
        ParseCommandRequest(
            command="python tool.py --label 'hello world' --path $HOME/file",
            dialect="auto",
            fallback_shell="powershell",
        )
    )
    assert parsed.detected_shell == "bash"
    assert parsed.draft.arguments[0].value == "hello world"
    assert parsed.draft.arguments[1].value == "$HOME/file"
    assert not parsed.warnings


@pytest.mark.parametrize(
    ("dialect", "command", "script_path", "value"),
    [
        (
            "powershell",
            r"python 'C:\My Project\tool.py' --name 'O''Brien'",
            r"C:\My Project\tool.py",
            "O'Brien",
        ),
        (
            "cmd",
            r'python "C:\My Project\tool.py" --name "hello world"',
            r"C:\My Project\tool.py",
            "hello world",
        ),
    ],
)
def test_parse_windows_quoted_values(dialect, command, script_path, value):
    parsed = parse_command(ParseCommandRequest(command=command, dialect=dialect))
    assert parsed.draft.script_path == script_path
    assert parsed.draft.arguments[0].value == value


def test_cmd_quotes_spaces():
    built = build_command(
        profile(
            shell="cmd",
            script_path=r"C:\My Project\test.py",
            arguments=[argument(token="--label", value_type="str", value="hello world")],
        )
    )
    assert built == 'python "C:\\My Project\\test.py" --label "hello world"'


@pytest.mark.parametrize(
    ("value_type", "value"),
    [("int", "12.3"), ("float", "not-a-number"), ("choice", "missing")],
)
def test_invalid_values_are_rejected(value_type, value):
    choices = ["allowed"] if value_type == "choice" else []
    with pytest.raises(ValueError):
        build_command(
            profile(
                arguments=[
                    argument(value_type=value_type, value=value, choices=choices)
                ]
            )
        )


def test_positional_boolean_is_rejected_by_schema():
    with pytest.raises(ValueError):
        argument(mode="positional", token="", value_type="bool", value=True)
