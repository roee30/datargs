"""
Module for uniform treatment of dataclasses and attrs classes.
"""
from abc import abstractmethod
from typing import TypeVar, Generic, Mapping, Type

import dataclasses

from datargs.meta import AbstractClassProperty

FieldType = TypeVar("FieldType")


class RecordField(Generic[FieldType]):
    """
    Abstract base class for fields of dataclasses or attrs classes.
    """

    field: FieldType

    def __init__(self, field):
        self.field = field

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
        return self.field.default

    @property
    def name(self):
        return self.field.name

    @property
    def type(self):
        return self.field.type

    @property
    def metadata(self):
        return self.field.metadata


class DataField(RecordField[dataclasses.Field]):
    """
    Represents a dataclass field.
    """

    def is_required(self) -> bool:
        return self.field.default is dataclasses.MISSING


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
        self.cls = cls

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
    def wrap_class(cls, record_class):
        """
        Wrap `record_class` with the appropriate wrapper.
        """
        for candidate in cls._implementors:
            if candidate.can_wrap_class(record_class):
                return candidate(record_class)
        if getattr(record_class, "__attrs_attrs__", None) is not None:
            raise Exception(
                f"can't accept '{record_class.__name__}' because it is an attrs class and attrs is not installed"
            )
        raise Exception(
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


try:
    import attr
except ImportError:
    pass
else:
    # import class to register it in RecordClass._implementors
    import datargs.compat.attrs
