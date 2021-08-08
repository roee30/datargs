# noinspection PyUnresolvedReferences
"""
Declarative, type safe `argparse` parsers.

>>> @dataclass
... class Args:
...     just_a_string: str
...     num: int
...     store_true: bool = False
...     store_false: bool = True
>>> args = parse(Args, ["--just-a-string", "STRING", "--num", "0", "--store-true", "--store-false"])
>>> args
Args(just_a_string='STRING', num=0, store_true=True, store_false=False)

Pycharm correctly infers that `args` is of type `Args`.
Trying to access a non-existent member is a type error:
>>> args.nope  # doctest: +SKIP
Pycharm says: Unresolved attribute reference 'nope' for class 'Args'

A flag with no defaults is assumed to be False by default:
>>> @dataclass
... class Args:
...     no_default: bool
>>> parse(Args, [])
Args(no_default=False)

Enums are supported. They should be specified by name on the command line:
>>> class FoodEnum(Enum):
...     gnocchi = 0
...     kimchi = 1
>>> @dataclass
... class Args:
...     food: FoodEnum
>>> parse(Args, ["--food", "kimchi"])
Args(food=<FoodEnum.kimchi: 1>)
>>> parse(Args, ["--food", "poutine"]) # doctest: +SKIP
usage: make.py [-h] --food {gnocchi,kimchi}
make.py: error: argument --food: 'poutine': invalid value
...
SystemExit: 2

Specifying enums by name is not currently supported.
"""
import dataclasses

# noinspection PyUnresolvedReferences,PyProtectedMember
from argparse import (
    ArgumentParser,
    ArgumentTypeError,
    _SubParsersAction,
    Namespace,
    _CountAction,
)
from dataclasses import dataclass, MISSING
from enum import Enum
from functools import wraps, partial
from inspect import signature
from typing import (
    Callable,
    Dict,
    TypeVar,
    Type,
    Sequence,
    Optional,
    overload,
    Any,
    Union,
    cast,
    get_type_hints,
    List,
    get_origin,
)

from boltons.strutils import camel2under

from .compat import (
    RecordField,
    RecordClass,
    NotARecordClass,
    DatargsParams,
    is_optional,
)


@dataclass
class Action:
    args: Sequence[Any] = dataclasses.field(default_factory=list)
    kwargs: Dict[str, Any] = dataclasses.field(default_factory=dict)


DispatchCallback = Callable[[str, RecordField, dict], Action]
AddArgFunc = Callable[[RecordField, dict], Action]


def field_name_to_arg_name(name: str, positional=False) -> str:
    if positional:
        return name
    return f"--{name.replace('_','-')}"


SpecialRule = Callable[[Type["TypeDispatch"], RecordField], Optional[Action]]


class TypeDispatch:

    dispatch: Dict[type, AddArgFunc] = {}
    special_rules: List[SpecialRule] = []

    @classmethod
    def add_arg(cls, field: RecordField, override: dict):
        dispatch_type = get_origin(field.type) or field.type
        for typ, func in cls.dispatch.items():
            if issubclass(dispatch_type, typ):
                return func(field, override)
        return add_any(field, override)

    @classmethod
    def add_simple_for_type(cls, field: RecordField, typ: type, override: dict):
        override = {**override, "type": typ}
        for rule_typ, func in cls.dispatch.items():
            if issubclass(typ, rule_typ):
                return func(field, override)
        return add_any(field, override)

    @classmethod
    def register(cls, typ):
        def decorator(func: DispatchCallback) -> AddArgFunc:
            cls.dispatch[typ] = new_func = wraps(func)(add_name_formatting(func))
            return new_func

        return decorator


def add_name_formatting(func: DispatchCallback) -> AddArgFunc:
    @wraps(func)
    def new_func(field: RecordField, override: dict):
        return func(
            field_name_to_arg_name(field.name, positional=field.is_positional),
            field,
            override,
        )

    return new_func


@add_name_formatting
def add_any(name: str, field: RecordField, extra: dict) -> Action:
    return add_default(name, field, extra)


def get_option_strings(name: str, field: RecordField):
    return [name, *field.metadata.get("aliases", [])]


def common_kwargs(field: RecordField):
    return {"type": field.type, **subdict(field.metadata, ["aliases", "positional"])}


def subdict(dct, remove_keys):
    return {key: value for key, value in dct.items() if key not in remove_keys}


def add_default(name, field: RecordField, override: dict) -> Action:
    override = {
        "default": field.default,
        **common_kwargs(field),
        **override,
    }
    if not field.is_positional:
        override["required"] = field.is_required()
    return Action(kwargs=override, args=get_option_strings(name, field))


T = TypeVar("T")


def call_func_with_matching_kwargs(func: Callable[..., T], *args, **kwargs) -> T:
    sig = signature(func)
    new_kwargs = {key: value for key, value in kwargs.items() if key in sig.parameters}
    return func(*args, **new_kwargs)


@TypeDispatch.register(str)
def add_str(name, field, override: dict):
    return add_default(name, field, override)


@TypeDispatch.register(Sequence)
def sequence_arg(name: str, field: RecordField, override: dict) -> Action:
    nargs = field.metadata.get("nargs")
    if nargs:
        assert nargs in ("+", "?") or isinstance(nargs, int)
    else:
        nargs = "+" if field.is_required() else "*"
    return TypeDispatch.add_simple_for_type(
        field, field.type.__args__[0], dict(**override, nargs=nargs)
    )


@TypeDispatch.register(bool)
def bool_arg(name: str, field: RecordField, override: dict) -> Action:
    kwargs = {
        **subdict(common_kwargs(field), ["type"]),
        **override,
        "action": "store_false"
        if field.default and field.has_default()
        else "store_true",
    }
    return Action(
        args=get_option_strings(name, field),
        kwargs=kwargs,
    )


@TypeDispatch.register(Enum)
def enum_arg(name: str, field: RecordField, override: dict) -> Action:
    field_type = override.get("type") or field.type

    def enum_type_func(value: str):
        result = field_type.__members__.get(value)
        if not result:
            raise ArgumentTypeError(
                f"invalid choice: {value!r} (choose from {[e.name for e in field.type]})"
            )
        return result

    return add_default(
        name,
        field,
        {
            **override,
            "type": enum_type_func,
            "choices": field_type,
            "metavar": f"{{{','.join(field_type.__members__)}}}",
        },
    )


ParserType = TypeVar("ParserType", bound=ArgumentParser)


@overload
def make_parser(cls: type) -> ArgumentParser:
    pass


@overload
def make_parser(cls: type, parser: None = None) -> ArgumentParser:
    pass


@overload
def make_parser(cls: type, parser: ParserType) -> ParserType:
    pass


def make_parser(cls, parser=None):
    # noinspection PyShadowingNames
    """
    Create parser that parses command-line arguments according to the fields of `cls`.
    Use this if you want to do anything with the parser other than immediately parsing the command-line arguments.
    If you do want to parse immediately, use `parse()`.
    :param cls: class according to which argument parser is created
    :param parser: parser to add arguments to, by default creates a new parser
    :return: instance of `parser_cls` which parses command line according to `cls`

    >>> @dataclass
    ... class Args:
    ...     first_arg: int
    >>> parse(Args, ["--first-arg", "0"])
    Args(first_arg=0)
    >>> parser = make_parser(Args)
    >>> parser.add_argument("--second-arg", type=float) # doctest: +ELLIPSIS
    [...]
    >>> parser.parse_args(["--first-arg", "0", "--second-arg", "1.5"])
    Namespace(first_arg=0, second_arg=1.5)
    """
    record_class = RecordClass.wrap_class(cls)
    return _make_parser(record_class, parser=parser)


class DatargsSubparsers(_SubParsersAction):
    """
    A subparsers action that creates the correct sub-command class upon parsing.
    """

    def __init__(self, name, *args, **kwargs):
        self.__name = name
        super().__init__(*args, **kwargs)
        self._command_type_map = {}

    def add_parser(self, typ: type, name: str, aliases=(), *args, **kwargs):
        result = super().add_parser(name, aliases=aliases, *args, **kwargs)
        for alias in [name, *aliases]:
            self._command_type_map[alias] = typ
        return result

    def __call__(self, parser, namespace, values, *args, **kwargs):
        new_ns = Namespace()
        name, *_ = values
        super().__call__(parser, new_ns, values)
        setattr(namespace, self.__name, self._command_type_map[name](**vars(new_ns)))


def _make_parser(record_class: RecordClass, parser: ParserType = None) -> ParserType:
    if not parser:
        parser = ArgumentParser(**record_class.parser_params)
    assert parser is not None
    for name, field in record_class.fields_dict().items():
        sub_commands = None
        try:
            if field.type.__origin__ is Union and not is_optional(field.type):
                sub_commands = field.type.__args__
        except AttributeError:
            pass
        if sub_commands is not None:
            add_subparsers(parser, record_class, field, sub_commands)
        else:
            action = TypeDispatch.add_arg(field, {})
            fix_count_action_kwargs(action)
            parser.add_argument(*action.args, **action.kwargs)
    return parser


def fix_count_action_kwargs(action):
    """
    If argument action is "count", remove "type" kwarg
    """
    if action.kwargs.get("action") == "count":
        action.kwargs.pop("type")


def add_subparsers(
    parser: ArgumentParser,
    top_class: RecordClass,
    sub_parsers_field: RecordField,
    sub_parser_classes: Sequence[type],
):
    # noinspection PyArgumentList
    subparsers = cast(
        DatargsSubparsers,
        parser.add_subparsers(
            **top_class.sub_commands_params,
            action=DatargsSubparsers,
            name=sub_parsers_field.name,
        ),
    )
    for command in sub_parser_classes:
        try:
            sub_parsers_args = top_class.wrap_class(command)
        except NotARecordClass:
            raise Exception(
                f"{top_class.name}.{sub_parsers_field.name}: "
                f"Union must be used with dataclass/attrs class and creates a subparser (got: {sub_parsers_field.type})"
            )
        sub_parser = subparsers.add_parser(
            command,
            sub_parsers_args.datargs_params.name
            or camel2under(sub_parsers_args.name).replace("_", "-"),
            **sub_parsers_args.parser_params,
        )
        _make_parser(sub_parsers_args, sub_parser)


def parse(cls: Type[T], args: Optional[Sequence[str]] = None, *, parser=None) -> T:
    """
    Parse command line arguments according to the fields of `cls` and populate it.
    Accepts classes decorated with `dataclass` or `attr.s`.
    :param cls: class to parse command-line arguments by
    :param parser: existing parser to add arguments to and parse from
    :param args: arguments to parse (default: `sys.arg`)
    :return: an instance of cls

    >>> @dataclass
    ... class Args:
    ...     is_flag: bool
    ...     num: int = 0
    >>> parse(Args, ["--num", "1"])
    Args(is_flag=False, num=1)
    """
    result = vars(make_parser(cls, parser=parser).parse_args(args))
    try:
        command_dest = cls.__datargs_params__.sub_commands.get("dest", None)
    except AttributeError:
        pass
    else:
        if command_dest is not None and command_dest in result:
            del result[command_dest]
    return cls(**result)


def argsclass(
    cls: type = None,
    *args,
    description: str = None,
    parser_params: dict = None,
    name: str = None,
    **kwargs,
):
    """
    A wrapper around `dataclass` for passing `description` and other params (in `parser_params`)
    to the `ArgumentParser` constructor.

    :param cls: class to wrap
    :param description: parser description
    :param parser_params: dict of arguments to parser class constructor
    :param name: Only used in subcommands, string to invoke subcommand. By default, the string used is the class'
        name converted to kebab-case, i.e., snake case with hyphens
    """
    # sub_commands_params has been disabled until a useful use case is found
    datargs_kwargs = {
        "description": description,
        "parser_params": parser_params,
        "name": name,
        "sub_commands_params": {},
    }

    if cls is None:
        # We're called with parens.
        return partial(
            make_class,
            *args,
            **datargs_kwargs,
            **kwargs,
        )

    return make_class(
        cls,
        *args,
        **datargs_kwargs,
        **kwargs,
    )


def make_class(
    cls,
    description: str = None,
    parser_params: dict = None,
    name: str = None,
    sub_commands_params: dict = None,
    *args,
    **kwargs,
):
    try:
        RecordClass.wrap_class(cls)
    except NotARecordClass:
        for key, value in cls.__dict__.items():
            if not isinstance(value, dataclasses.Field) or value.default is not MISSING:
                continue
            typ = value.type or get_type_hints(cls)[key]
            if typ is bool:
                value.default = False
        new_cls = dataclass(*args, **kwargs)(cls)
    else:
        new_cls = cls
    new_cls.__datargs_params__ = DatargsParams(
        parser={"description": description, **(parser_params or {})},
        sub_commands=sub_commands_params or {},
        name=name,
    )
    return new_cls


def arg(
    positional=False,
    nargs=None,
    const=None,
    default=MISSING,
    choices=None,
    help=None,
    metavar=None,
    aliases: Sequence[str] = (),
    **kwargs,
):
    """
    Helper method to more easily add parsing-related behavior.
    Supports aliases:
    >>> @dataclass
    ... class Args:
    ...     num: int = arg(aliases=["-n"])
    >>> parse(Args, ["--num", "0"])
    Args(num=0)
    >>> parse(Args, ["-n", "0"])
    Args(num=0)

    Accepts all arguments to both `ArgumentParser.add_argument` and `dataclass.field`:
    >>> @dataclass
    ... class Args:
    ...     invisible_arg: int = arg(default=0, repr=False, metavar="MY_ARG", help="argument description")
    >>> print(Args())
    Args()
    >>> make_parser(Args).print_help() # doctest: +ELLIPSIS, +NORMALIZE_WHITESPACE
    usage: ...
      --invisible-arg MY_ARG    argument description
    """
    return dataclasses.field(
        metadata=remove_dict_nones(
            dict(
                nargs=nargs,
                choices=choices,
                const=const,
                help=help,
                metavar=metavar,
                aliases=aliases,
                positional=positional,
            )
        ),
        default=default,
        **kwargs,
    )


def remove_dict_nones(dct: dict) -> dict:
    return {key: value for key, value in dct.items() if value is not None}


if __name__ == "__main__":
    import doctest

    OC = doctest.OutputChecker

    class AEOutputChecker(OC):
        def check_output(self, want, got, optionflags):
            if optionflags & doctest.ELLIPSIS:
                want = want.replace("[...]", doctest.ELLIPSIS_MARKER)
            return super().check_output(want, got, optionflags)

    doctest.OutputChecker = AEOutputChecker
    doctest.testmod(optionflags=doctest.REPORT_NDIFF)
