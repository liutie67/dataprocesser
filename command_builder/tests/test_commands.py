import pytest

from command_builder.commands import build_command
from command_builder.models import CommandArgument, ProfilePayload


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
