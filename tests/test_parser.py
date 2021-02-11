from abc import ABC
from argparse import ArgumentParser
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Type, Sequence, Text, NoReturn, TypeVar, Optional

import attr
import pytest
from pytest import raises

from datargs.compat import DataClass, RecordClass
from datargs.make import argsclass, parse, arg, make_parser


@pytest.fixture(
    scope="module",
    params=[attr.dataclass, dataclass, argsclass],
    ids=["attrs", None, None],
)
def factory(request):
    return request.param


def test_attrs_imported():
    try:
        import attr
    except ImportError:
        pass
    else:
        import datargs.compat.attrs


def test_attrs_error():
    class NoInitSubclass:
        def __init_subclass__(cls, **kwargs):
            pass

    class MockResolver(NoInitSubclass, RecordClass, ABC):
        _implementors = [DataClass]

    @attr.s
    class Args:
        pass

    with raises(Exception) as exc_info:
        MockResolver.wrap_class(Args)
    assert "not installed" in exc_info.value.args[0]


def test_invalid_class():
    class NoDataclass:
        pass

    with pytest.raises(Exception) as exc_info:
        parse_test(NoDataclass, [])
    assert "not a dataclass" in exc_info.value.args[0]


def test_bool(factory):
    @factory
    class TestStoreTrue:
        store_true: bool = False

    args = parse_test(TestStoreTrue, [])
    assert not args.store_true
    args = parse_test(TestStoreTrue, ["--store-true"])
    assert args.store_true

    @factory
    class TestStoreTrueNoDefault:
        store_true: bool

    args = parse_test(TestStoreTrueNoDefault, [])
    assert not args.store_true
    args = parse_test(TestStoreTrueNoDefault, ["--store-true"])
    assert args.store_true

    @factory
    class TestStoreFalse:
        store_false: bool = True

    args = parse_test(TestStoreFalse, [])
    assert args.store_false
    args = parse_test(TestStoreFalse, ["--store-false"])
    assert not args.store_false


def test_str(factory):
    @factory
    class TestStringRequired:
        arg: str

    _test_required(TestStringRequired)

    args = parse_test(TestStringRequired, ["--arg", "test"])
    assert args.arg == "test"

    @factory
    class TestStringOptional:
        arg: str = "default"

    args = parse_test(TestStringOptional, [])
    assert args.arg == "default"
    args = parse_test(TestStringOptional, ["--arg", "test"])
    assert args.arg == "test"


def test_int(factory):
    @factory
    class TestIntRequired:
        arg: int

    _test_required(TestIntRequired)

    args = parse_test(TestIntRequired, ["--arg", "1"])
    assert args.arg == 1

    @factory
    class TestIntOptional:
        arg: int = 0

    args = parse_test(TestIntOptional, [])
    assert args.arg == 0
    args = parse_test(TestIntOptional, ["--arg", "1"])
    assert args.arg == 1


def test_float(factory):
    @factory
    class TestIntRequired:
        arg: int

    _test_required(TestIntRequired)

    args = parse_test(TestIntRequired, ["--arg", "1"])
    assert args.arg == 1

    @factory
    class TestIntOptional:
        arg: int = 0

    args = parse_test(TestIntOptional, [])
    assert args.arg == 0
    args = parse_test(TestIntOptional, ["--arg", "1"])
    assert args.arg == 1


def test_enum(factory):
    class TestEnum(Enum):
        a = 0
        b = 1

    @factory
    class TestEnumRequired:
        arg: TestEnum

    _test_required(TestEnumRequired)
    args = parse_test(TestEnumRequired, ["--arg", "a"])
    assert args.arg == TestEnum.a

    @factory
    class TestEnumOptional:
        arg: TestEnum = TestEnum.b

    args = parse_test(TestEnumOptional, ["--arg", "a"])
    assert args.arg == TestEnum.a
    args = parse_test(TestEnumOptional, [])
    assert args.arg == TestEnum.b


def test_sequence(factory):
    @factory
    class TestSequenceRequired:
        arg: Sequence[int]

    _test_required(TestSequenceRequired)

    args = parse_test(TestSequenceRequired, ["--arg", "1", "2"])
    assert args.arg == [1, 2]

    @factory
    class TestSequenceOptional:
        arg: Sequence[int] = ()

    args = parse_test(TestSequenceOptional, [])
    assert args.arg == ()
    args = parse_test(TestSequenceOptional, ["--arg", "1", "2"])
    assert args.arg == [1, 2]

    @argsclass
    class TestSequencePositional:
        arg: Sequence[int] = arg(default=(), positional=True)

    args = parse_test(TestSequencePositional, [])
    assert args.arg == ()
    args = parse_test(TestSequencePositional, ["1", "2"])
    assert args.arg == [1, 2]

    @argsclass
    class TestSequencePositionalPath:
        arg: Sequence[Path] = arg(default=(), positional=True)

    args = parse_test(TestSequencePositionalPath, [])
    assert args.arg == ()
    args = parse_test(TestSequencePositionalPath, ["1", "2"])
    assert args.arg == [Path("1"), Path("2")]


def test_optional(factory):
    @factory
    class TestOptional:
        arg: Optional[int] = None

    args = parse_test(TestOptional, [])
    assert args.arg is None
    args = parse_test(TestOptional, ["--arg", "1"])
    assert args.arg == 1


def test_kwargs(factory):
    @factory(order=True)
    class Order:
        arg: int

    assert Order(0) < Order(1)

    @factory(order=False)
    class NoOrder:
        arg: int

    with raises(TypeError):
        assert NoOrder(0) < NoOrder(1)


def test_positional():
    @argsclass
    class TestPositional:
        arg: str = arg(positional=True)

    _test_required(TestPositional)

    args = parse_test(TestPositional, ["test"])
    assert args.arg == "test"


def test_order_bool():
    @argsclass
    class TestOrderBool:
        not_required: str = arg(default="")
        also_not_required: bool = arg()

    args = parse_test(TestOrderBool, [])
    assert not args.also_not_required


def test_argsclass_on_decorator():
    """
    Does not work with attrs.
    """

    @argsclass
    @dataclass
    class TestDoubleDecorators:
        arg: str = arg(positional=True)

    args = parse(TestDoubleDecorators, ["arg"])
    assert args.arg == "arg"

    description = "desc"

    @argsclass(description=description)
    @dataclass
    class TestDoubleDecorators:
        arg: str = arg(positional=True)

    help_str = make_parser(TestDoubleDecorators).format_help()
    assert description in help_str


def test_nargs_dataclass():
    @dataclass()
    class Nargs:
        nums: int = arg(nargs="+")

    args = parse_test(Nargs, ["--nums", "1", "2"])
    assert args.nums == [1, 2]


def test_nargs_attrs():
    @attr.s
    class Nargs:
        nums: int = attr.ib(metadata=dict(nargs="+"))

    args = parse_test(Nargs, ["--nums", "1", "2"])
    assert args.nums == [1, 2]


def _test_required(cls):
    with raises(ParserError) as exc_info:
        parse_test(cls, [])
    assert "required" in exc_info.value.message


@attr.s(auto_attribs=True, auto_exc=True)
class ParserError(Exception):
    message: str = None


T = TypeVar("T")


def parse_test(cls: Type[T], args: Sequence[str]) -> T:
    return parse(cls, args, parser=ParserTest())


class ParserTest(ArgumentParser):
    def error(self, message: Text) -> NoReturn:
        raise ParserError(message)

    exit = error


if __name__ == "__main__":
    pytest.main()
