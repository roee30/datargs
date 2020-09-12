from datargs.make import argsclass, arg, parse_to_class, make_parser


def test_help():
    parser_help = "Program documentation"
    program = "My prog"

    @argsclass(description=parser_help, parser_params=dict(prog=program))
    class Args:
        flag: bool = arg(help="helpful message")

    args = parse_to_class(Args, [])
    assert not args.flag
    parser = make_parser(Args)
    help_string = parser.format_help()
    assert "helpful message" in help_string
    assert parser_help in help_string
    assert program in help_string


def test_decorator_no_args():
    @argsclass
    class Args:
        flag: bool = arg(help="helpful message")

    assert not parse_to_class(Args, []).flag


def test_decorator_with_args():
    @argsclass(repr=True)
    class Args:
        flag: bool = arg(help="helpful message")

    assert not parse_to_class(Args, []).flag


def test_default():
    @argsclass
    class Args:
        x: int = arg(default=0)

    assert Args().x == 0


def test_alias():
    @argsclass
    class Args:
        num: int = arg(aliases=["-n"])

    args = parse_to_class(Args, ["-n", "0"])
    assert args.num == 0
