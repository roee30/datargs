# noinspection PyUnresolvedReferences
"""
Declerative, type safe `argparse` parsers.

>>> @dataclass
... class Args:
...     just_a_string: str
...     num: int
...     store_true: bool = False
...     store_false: bool = True
>>> args = parse_to_class(Args, ["--just-a-string", "STRING", "--num", "0", "--store-true", "--store-false"])
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
>>> parse_to_class(Args, [])
Args(no_default=False)

Enums are supported. They should be specified by name on the command line:
>>> class FoodEnum(Enum):
...     gnocchi = 0
...     kimchi = 1
>>> @dataclass
... class Args:
...     food: FoodEnum
>>> parse_to_class(Args, ["--food", "kimchi"])
Args(food=<FoodEnum.kimchi: 1>)
>>> parse_to_class(Args, ["--food", "poutine"]) # doctest: +SKIP
usage: make.py [-h] --food {gnocchi,kimchi}
make.py: error: argument --food: 'poutine' is not a member of FoodEnum
...
SystemExit: 2

Specifying enums by name is not currently supported.
"""
import dataclasses
# noinspection PyUnresolvedReferences,PyProtectedMember
from argparse import (
    ArgumentParser,
    Action,
    _StoreAction,
    _StoreTrueAction,
    _StoreFalseAction,
    ArgumentTypeError,
)
from dataclasses import dataclass, make_dataclass, MISSING
from enum import Enum
from functools import wraps, partial
from inspect import signature
from typing import Callable, Dict, TypeVar, Type, Sequence, Optional

from .compat import RecordField, RecordClass

DispatchCallback = Callable[[str, RecordField], Action]
AddArgFunc = Callable[[RecordField], Action]


def field_name_to_arg_name(name: str) -> str:
    return f"--{name.replace('_','-')}"


class TypeDispatch:

    dispatch: Dict[type, AddArgFunc] = {}

    @classmethod
    def add_arg(cls, field: RecordField):
        for typ, func in cls.dispatch.items():
            if issubclass(field.type, typ):
                return func(field)
        return add_any(field)

    @classmethod
    def register(cls, typ):
        def decorator(func: DispatchCallback) -> AddArgFunc:
            cls.dispatch[typ] = new_func = add_name_formatting(func)
            return new_func

        return decorator


def add_name_formatting(func: DispatchCallback) -> AddArgFunc:
    @wraps(func)
    def new_func(field):
        return func(field_name_to_arg_name(field.name), field)

    return new_func


@add_name_formatting
def add_any(name: str, field: RecordField) -> Action:
    return add_default(name, field)


def get_option_strings(name: str, field: RecordField):
    return [name, *field.metadata.get("aliases", [])]


def common_kwargs(field: RecordField):
    return {
        "type": field.type,
        "dest": field.name,
        **field.metadata,
    }


def add_default(name, field: RecordField, cls=_StoreAction, **kwargs):
    kwargs = {
        "required": field.is_required(),
        "default": field.default,
        **common_kwargs(field),
        **kwargs,
    }
    return call_func_with_matching_kwargs(
        cls, get_option_strings(name, field), **kwargs
    )


T = TypeVar("T")


def call_func_with_matching_kwargs(func: Callable[..., T], *args, **kwargs) -> T:
    sig = signature(func)
    new_kwargs = {key: value for key, value in kwargs.items() if key in sig.parameters}
    return func(*args, **new_kwargs)


@TypeDispatch.register(bool)
def bool_arg(name: str, field: RecordField):
    cls = (
        _StoreFalseAction if field.default and field.has_default() else _StoreTrueAction
    )
    return call_func_with_matching_kwargs(
        cls, get_option_strings(name, field), **common_kwargs(field)
    )


@TypeDispatch.register(Enum)
def enum_arg(name: str, field: RecordField):
    def type_func(value: str):
        result = field.type.__members__.get(value)
        if not result:
            raise ArgumentTypeError(
                f"{value!r} is not a member of {field.type.__name__}"
            )
        return result

    return add_default(
        name,
        field,
        type=type_func,
        choices=field.type,
        metavar=f"{{{','.join(field.type.__members__)}}}",
    )


ParserType = TypeVar("ParserType", bound=ArgumentParser)


def make_parser(cls: type, parser: ParserType = None) -> ParserType:
    # noinspection PyShadowingNames
    """
    Create parser that parses command-line arguments according to the fields of `cls`.
    Use this if you want to do anything with the parser other than immediately parsing the command-line arguments.
    If you do want to parse immediately, use `parse_to_class`.
    :param cls: class according to which argument parser is created
    :param parser: parser to add arguments to, by default creates a new parser
    :return: instance of `parser_cls` which parses command line according to `cls`

    >>> @dataclass
    ... class Args:
    ...     first_arg: int
    >>> parse_to_class(Args, ["--first-arg", "0"])
    Args(first_arg=0)
    >>> parser = make_parser(Args)
    >>> parser.add_argument("--second-arg", type=float) # doctest: +ELLIPSIS
    [...]
    >>> parser.parse_args(["--first-arg", "0", "--second-arg", "1.5"])
    Namespace(first_arg=0, second_arg=1.5)
    """
    record_class = RecordClass.wrap_class(cls)
    try:
        # noinspection PyUnresolvedReferences
        parser_params: dict = cls.__parser_params__
    except AttributeError:
        parser_params = {}
    parser = parser or ArgumentParser(**parser_params)
    for name, field in record_class.fields_dict().items():
        # noinspection PyProtectedMember
        parser._add_action(TypeDispatch.add_arg(field))
    return parser


def parse_to_class(cls: Type[T], args: Optional[Sequence[str]] = None) -> T:
    """
    Parse command line arguments according to the fields of `cls` and populate it.
    Accepts classes decorated with `dataclass`, `attr.s` or `argsclass`.
    :param cls: class to parse command-line arguments by
    :param args: arguments to parse (default: `sys.arg`)
    :return: an instance of cls

    >>> @dataclass
    ... class Args:
    ...     is_flag: bool
    ...     num: int = 0
    >>> parse_to_class(Args, ["--num", "1"])
    Args(is_flag=False, num=1)
    """
    return cls(**vars(make_parser(cls).parse_args(args)))


# noinspection PyShadowingBuiltins
def arg(
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
    >>> @argsclass
    ... class Args:
    ...     num: int = arg(aliases=["-n"])
    >>> parse_to_class(Args, ["--num", "0"])
    Args(num=0)
    >>> parse_to_class(Args, ["-n", "0"])
    Args(num=0)

    Accepts all arguments to both `ArgumentParser.add_argument` and `dataclass.field`:
    >>> @argsclass
    ... class Args:
    ...     invisible_arg: int = arg(default=0, repr=False, metavar="MY_ARG", help="argument description")
    >>> print(Args())
    Args()
    >>> make_parser(Args).print_help() # doctest: +ELLIPSIS, +NORMALIZE_WHITESPACE
    usage: ...
      --invisible-arg MY_ARG    argument description
    """
    return dataclasses.field(
        metadata=dict(
            nargs=nargs,
            choices=choices,
            const=const,
            help=help,
            metavar=metavar,
            aliases=aliases,
        ),
        default=default,
        **kwargs,
    )


def argsclass(
    maybe_cls: type = None,
    description: str = None,
    parser_params: dict = None,
    **kwargs,
):
    """
    Decorator for passing `description` and other `ArgumentParser` parameters
    and for enabling the use of `arg()`.
    When not using `arg()`, using `dataclass` is prefereable.
    A paper-thin wrapper around `dataclass` which helps with passing additional arguments to parsers.

    >>> from dataclasses import dataclass, field, fields
    >>> @argsclass
    ... class Args:
    ...     str_arg: str = arg(metavar="ARGUMENT_NAME", help="Flag documentation")
    >>> make_parser(Args).print_help() # doctest: +ELLIPSIS, +NORMALIZE_WHITESPACE
    usage: ...
      --str-arg ARGUMENT_NAME      Flag documentation

    The above is equivalent to:
    >>> @dataclass
    ... class Args:
    ...     str_arg: str = arg(metavar="ARGUMENT_NAME", help="Flag documentation")
    >>> make_parser(Args).print_help() # doctest: +ELLIPSIS, +NORMALIZE_WHITESPACE
    usage: ...
      --str-arg ARGUMENT_NAME      Flag documentation

    `argclass` accepts all arguments to `dataclass`:
    >>> @argsclass(repr=False)
    ... class Args:
    ...     flag: bool
    >>> print(Args(True)) # doctest: +ELLIPSIS, +NORMALIZE_WHITESPACE
    <...Args object at 0x...>

    `argclass` accepts a `description` parameter for `ArgumentParser`.
    Other `ArgumentParser` parameters can be passed in `parser_params`:
    >>> @argsclass(description="My program help", parser_params=dict(prog="my-program-string", epilog="My epilog"))
    ... class Args:
    ...     flag: bool
    >>> make_parser(Args).print_help() # doctest: +ELLIPSIS, +NORMALIZE_WHITESPACE
    usage: my-program-string ...
    My program help
    ...
    My epilog
    """
    if maybe_cls is None:
        return partial(
            make_class, description=description, parser_params=parser_params, **kwargs
        )
    return make_class(maybe_cls)


def make_class(
    cls: type,
    description: str = None,
    parser_params: dict = None,
    **kwargs,
):
    annotations = cls.__annotations__
    optional_fields = {
        name: (name, annotations.get(name), member)
        for name, member in vars(cls).items()
        if isinstance(member, dataclasses.Field)
    }
    required_fields = {
        name: (name, annotation, dataclasses.field())
        for name, annotation in annotations.items()
        if name not in optional_fields
    }
    all_fields = {**required_fields, **optional_fields}
    new_cls = make_dataclass(
        cls.__name__,
        list(all_fields.values()),
        bases=tuple(cls.mro())[1:],
        namespace={
            key: value for key, value in vars(cls).items() if key not in all_fields
        },
        **kwargs,
    )
    new_cls.__parser_params__ = {"description": description, **(parser_params or {})}
    return new_cls


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
