import typing
from dataclasses import dataclass

from .django_to_proto import django_to_proto
from .serializers import SaveNode
from .stubs import DjModel, ProtoMsg
from .util import create_proto_field_obj


@dataclass
class CustomField:
    proto_type: str
    null: bool = False

    def update_proto(self, django_obj: DjModel, proto_obj: ProtoMsg, field_name: str):
        pass

    def update_django(self, node: "SaveNode", proto_obj: ProtoMsg, field_name: str):
        pass


@dataclass
class ReadOnlyQueryStrField(CustomField):
    query: str = None

    def update_proto(self, django_obj, proto_obj, field_name):
        model = type(django_obj)
        value = (
            model.objects.filter(pk=django_obj.pk)
            .values_list(self.query or field_name, flat=True)
            .first()
        )
        if value is None:
            return
        setattr(proto_obj, field_name, value)


@dataclass
class ReadOnlyQuerySetField(CustomField):
    get_queryset: typing.Callable = None

    def update_proto(self, django_obj, proto_obj, field_name):
        field = getattr(proto_obj, field_name)
        msgs = [
            django_to_proto(obj, create_proto_field_obj(proto_obj, field_name))
            for obj in self.get_queryset(django_obj)
        ]
        field.extend(msgs)


@dataclass
class ReadOnlyValueField(CustomField):
    get_value: typing.Callable = None

    def update_proto(self, django_obj, proto_obj, field_name):
        value = self.get_value(django_obj)
        setattr(proto_obj, field_name, value)
