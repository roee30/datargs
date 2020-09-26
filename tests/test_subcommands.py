# noinspection PyUnresolvedReferences,PyProtectedMember
from argparse import _SubParsersAction
from dataclasses import dataclass
from typing import Union

from pytest import raises

from datargs import make_parser, argsclass, arg, parse
from tests.test_parser import ParserTest


def test_subcommands():
    install_help = "installing command"
    package_help = "package help"

    @argsclass(description=install_help)
    class Install:
        package: str = arg(positional=True, help=package_help)

    help_help = "helping command"

    @argsclass(description=help_help)
    class Help:
        command: str = arg(positional=True)
        verbose: bool

    pip_help = "Pip install packages!"

    @argsclass(description=pip_help)
    class Pip:
        action: Union[Install, Help]
        verbose: bool

    # passing your own parser ignores `description`
    assert pip_help in make_parser(Pip).format_help()

    parser = make_parser(Pip, ParserTest())
    subparsers = next(
        action for action in parser._actions if isinstance(action, _SubParsersAction)
    )
    args = [("install", "package", install_help), ("help", "command", help_help)]
    for sub_command, arg_name, help_str in args:
        assert sub_command in parser.format_help()
        # noinspection PyUnresolvedReferences
        sub_help = subparsers.choices[sub_command].format_help()
        assert arg_name in sub_help
        assert help_str in sub_help

    result = parse(Pip, ["--verbose", "install", "foo"])
    assert isinstance(result, Pip)
    assert isinstance(result.action, Install)
    assert result.action.package == "foo"
    assert result.verbose

    result = parse(Pip, ["help", "foo", "--verbose"])
    assert isinstance(result, Pip)
    assert isinstance(result.action, Help)
    assert result.action.command == "foo"
    assert result.action.verbose
    assert not result.verbose


def test_union_no_dataclass():
    @dataclass
    class Args:
        action: Union[int, str]

    with raises(Exception) as exc_info:
        parse(Args, [])
    assert "Union" in exc_info.value.args[0]
