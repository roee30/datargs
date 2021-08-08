from . import RecordField, RecordClass

try:
    import attr
except ImportError:
    pass
else:

    class AttrField(RecordField[attr.Attribute]):
        def is_required(self) -> bool:
            return self.default is attr.NOTHING

    class AttrClass(RecordClass[attr.Attribute]):
        fields_attribute = "__attrs_attrs__"
        field_wrapper_type = AttrField

        def fields_dict(self):
            return {
                name: self.get_field(field)
                for name, field in attr.fields_dict(self.cls).items()
            }
