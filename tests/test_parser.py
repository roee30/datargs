from abc import ABC
from argparse import ArgumentParser
from enum import Enum
from typing import Type, Sequence, Text, NoReturn, TypeVar

import attr
import pytest
from dataclasses import dataclass
from pytest import raises

from datargs.compat import DataClass, RecordClass
from datargs.make import make_parser


@pytest.fixture(scope="module", params=[attr.dataclass, dataclass])
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
        parse_from_class(NoDataclass, [])
    assert "not a dataclass" in exc_info.value.args[0]


def test_bool(factory):
    @factory
    class TestStoreTrue:
        store_true: bool = False

    args = parse_from_class(TestStoreTrue, [])
    assert not args.store_true
    args = parse_from_class(TestStoreTrue, ["--store-true"])
    assert args.store_true

    @factory
    class TestStoreTrueNoDefault:
        store_true: bool

    args = parse_from_class(TestStoreTrueNoDefault, [])
    assert not args.store_true
    args = parse_from_class(TestStoreTrueNoDefault, ["--store-true"])
    assert args.store_true

    @factory
    class TestStoreFalse:
        store_false: bool = True

    args = parse_from_class(TestStoreFalse, [])
    assert args.store_false
    args = parse_from_class(TestStoreFalse, ["--store-false"])
    assert not args.store_false


def test_str(factory):
    @factory
    class TestStringRequired:
        arg: str

    _test_required(TestStringRequired)

    args = parse_from_class(TestStringRequired, ["--arg", "test"])
    assert args.arg == "test"

    @factory
    class TestStringOptional:
        arg: str = "default"

    args = parse_from_class(TestStringOptional, [])
    assert args.arg == "default"
    args = parse_from_class(TestStringOptional, ["--arg", "test"])
    assert args.arg == "test"


def test_int(factory):
    @factory
    class TestIntRequired:
        arg: int

    _test_required(TestIntRequired)

    args = parse_from_class(TestIntRequired, ["--arg", "1"])
    assert args.arg == 1

    @factory
    class TestIntOptional:
        arg: int = 0

    args = parse_from_class(TestIntOptional, [])
    assert args.arg == 0
    args = parse_from_class(TestIntOptional, ["--arg", "1"])
    assert args.arg == 1


def test_float(factory):
    @factory
    class TestIntRequired:
        arg: int

    _test_required(TestIntRequired)

    args = parse_from_class(TestIntRequired, ["--arg", "1"])
    assert args.arg == 1

    @factory
    class TestIntOptional:
        arg: int = 0

    args = parse_from_class(TestIntOptional, [])
    assert args.arg == 0
    args = parse_from_class(TestIntOptional, ["--arg", "1"])
    assert args.arg == 1


def test_enum(factory):
    class TestEnum(Enum):
        a = 0
        b = 1

    @factory
    class TestEnumRequired:
        arg: TestEnum

    _test_required(TestEnumRequired)
    args = parse_from_class(TestEnumRequired, ["--arg", "a"])
    assert args.arg == TestEnum.a

    @factory
    class TestEnumOptional:
        arg: TestEnum = TestEnum.b

    args = parse_from_class(TestEnumOptional, ["--arg", "a"])
    assert args.arg == TestEnum.a
    args = parse_from_class(TestEnumOptional, [])
    assert args.arg == TestEnum.b


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


def _test_required(cls):
    with raises(ParserError) as exc_info:
        parse_from_class(cls, [])
    assert "required" in exc_info.value.message


@attr.s(auto_attribs=True, auto_exc=True)
class ParserError(Exception):
    message: str = None


T = TypeVar("T")


def parse_from_class(cls: Type[T], args: Sequence[str]) -> T:
    result = make_parser(cls, ParserTest()).parse_args(args)
    return cls(**vars(result))


class ParserTest(ArgumentParser):
    def error(self, message: Text) -> NoReturn:
        raise ParserError(message)


if __name__ == "__main__":
    pytest.main()
