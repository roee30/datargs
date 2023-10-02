from dataclasses import dataclass, field

from datargs.make import arg, parse, make_parser
from tests.test_arg_type import ParserTest


def test_help():
    parser_help = "Program documentation"
    program = "My prog"
    parser = ParserTest(description=parser_help, prog=program)
    help_string = parser.format_help()
    assert parser_help in help_string
    assert program in help_string

    @dataclass
    class Args:
        flag: bool = arg(help="helpful message")

    args = parse(Args, [])
    assert not args.flag
    parser = make_parser(Args, parser)
    help_string = parser.format_help()
    assert "helpful message" in help_string
    assert parser_help in help_string
    assert program in help_string


def test_decorator_no_args():
    @dataclass
    class Args:
        flag: bool = arg(help="helpful message")

    assert not parse(Args, []).flag


def test_decorator_with_args():
    @dataclass(repr=True)
    class Args:
        flag: bool = arg(help="helpful message")

    assert not parse(Args, []).flag


def test_dataclass_with_args():
    @dataclass
    class Args:
        x: int = arg(default=0)

    assert Args().x == 0


def test_default():
    @dataclass
    class Args:
        x: int = arg(default=0)

    assert Args().x == 0


def test_alias():
    @dataclass
    class Args:
        num: int = arg("-n")

    args = parse(Args, ["-n", "0"])
    assert args.num == 0


def test_count():
    @dataclass
    class Args:
        verbosity: int = field(
            default=0,
            metadata=dict(
                aliases=["-v"],
                help="Increase logging verbosity",
                action="count",
            ),
        )
    args = parse(Args, ["-vv"])
    assert args.verbosity == 2