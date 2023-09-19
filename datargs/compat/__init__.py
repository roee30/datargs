"""
Module for uniform treatment of dataclasses and attrs classes.
"""
import dataclasses
from abc import abstractmethod
from dataclasses import dataclass
from typing import TypeVar, Generic, Mapping, Type, Union

from datargs.meta import AbstractClassProperty

try:
    from types import UnionType
except ImportError:
    # In this case, create a type such that ``isinstance(value, typ)`` will always return False
    UnionType = type("UniqueMarkerType", (), {})


FieldType = TypeVar("FieldType")


@dataclass
class DatargsParams:
    parser: dict = dataclasses.field(default_factory=dict)
    sub_commands: dict = dataclasses.field(default_factory=dict)
    name: str = None

    def __post_init__(self, *args, **kwargs):
        for key, value in (
            ("required", True),
            ("dest", "__datargs_dest__"),
        ):
            self.sub_commands.setdefault(key, value)


class RecordField(Generic[FieldType]):
    """
    Abstract base class for fields of dataclasses or attrs classes.
    """

    _field: FieldType
    NONE = object()

    def __init__(self, field):
        self._field = field

    @abstractmethod
    def is_required(self) -> bool:
        """
        Return whether field is required.
        """
        pass

    def has_default(self) -> bool:
        """
        Helper method to indicate whether a field has a default value.
        Used to make intention clearer in call sites.
        """
        return not self.is_required()

    @property
    def default(self):
        return self._field.default

    @property
    def name(self):
        return self._field.name

    @property
    def type(self):
        return self._field.type

    @property
    def metadata(self):
        return self._field.metadata

    @property
    def is_positional(self) -> bool:
        return self.metadata.get("positional", False)

    @property
    def aliases_overrides(self) -> bool:
        return self.metadata.get("aliases_overrides", False)


class DataField(RecordField[dataclasses.Field]):
    """
    Represents a dataclass field.
    """

    def is_required(self) -> bool:
        return self.default is dataclasses.MISSING


class NotARecordClass(Exception):
    pass


class RecordClass(Generic[FieldType]):
    """
    Abstract base class for dataclasses or attrs classes.
    """

    # The name of the attribute that holds field definitions
    fields_attribute: str = AbstractClassProperty()

    # The type to wrap fields with
    field_wrapper_type: Type[RecordField] = AbstractClassProperty()
    _implementors = []

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__()
        if not getattr(cls, "__abstractmethods__", None):
            cls._implementors.append(cls)

    def __init__(self, cls):
        self.cls: type = cls

    @property
    def datargs_params(self) -> DatargsParams:
        return getattr(self.cls, "__datargs_params__", DatargsParams())

    @property
    def parser_params(self):
        return self.datargs_params.parser

    @property
    def sub_commands_params(self):
        return self.datargs_params.sub_commands

    @property
    def name(self):
        return self.cls.__name__

    @abstractmethod
    def fields_dict(self) -> Mapping[str, FieldType]:
        """
        Returns a mapping of field names to field wrapper classes.
        """
        pass

    @classmethod
    def can_wrap_class(cls, potential_record_class) -> bool:
        """
        Returns whether this class is the appropriate implementation for wrapping `potential_record_class`.
        """
        return getattr(potential_record_class, cls.fields_attribute, None) is not None

    @classmethod
    def wrap_class(cls, record_class) -> "RecordClass":
        """
        Wrap `record_class` with the appropriate wrapper.
        """
        for candidate in cls._implementors:
            if candidate.can_wrap_class(record_class):
                return candidate(record_class)
        if getattr(record_class, "__attrs_attrs__", None) is not None:
            raise NotARecordClass(
                f"can't accept '{record_class.__name__}' because it is an attrs class and attrs is not installed"
            )
        raise NotARecordClass(
            f"class '{record_class.__name__}' is not a dataclass nor an attrs class"
        )

    @classmethod
    def get_field(cls, field: FieldType):
        """
        Wrap field with field classes with a uniform interface.
        """
        return cls.field_wrapper_type(field)


class DataClass(RecordClass[dataclasses.Field]):
    """
    Represents a dataclass.
    """

    fields_attribute = "__dataclass_fields__"
    field_wrapper_type = DataField

    def fields_dict(self) -> Mapping[str, FieldType]:
        fields = dataclasses.fields(self.cls)
        return {field.name: self.get_field(field) for field in fields}


def is_optional(typ):
    assert typ
    return (
        (isinstance(typ, UnionType) or getattr(typ, "__origin__", None) is Union)
        and len(typ.__args__) == 2
        and type(None) in typ.__args__
    ) or ()


try:
    import attr
except ImportError:
    pass
else:
    # import class to register it in RecordClass._implementors
    import datargs.compat.attrs
