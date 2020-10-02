import typing as T
import uuid
from dataclasses import dataclass

from django.conf import settings
from django.db import models
from django.db.models.fields.related_descriptors import ReverseManyToOneDescriptor
from django.utils import timezone
from google.protobuf.json_format import MessageToDict, ParseDict
from google.protobuf.struct_pb2 import Value

from djpb.util import get_django_field_repr, create_proto_field_obj
from .gen_proto import (
    DJANGO_TO_PROTO_FIELD_TYPE,
    PROTO_VALUE_TYPE,
    PROTO_TIMESTAMP_TYPE,
)
from .stubs import DjModel, ProtoMsg, DjFieldType


def register_serializer(cls: T.Type["FieldSerializer"]) -> T.Type["FieldSerializer"]:
    assert issubclass(cls, FieldSerializer)

    proto_type_name = getattr(cls, "proto_type_name", None)

    for field_type in cls.field_types:
        SERIALIZERS[field_type] = cls()
        if proto_type_name:
            DJANGO_TO_PROTO_FIELD_TYPE[field_type] = proto_type_name

    return cls


class FieldSerializer:
    """
    The default serializer that does no serialization, and directly calls setattr.

    All serializers must subclass FieldSerializer,
    and register themselves using the @register_serializer decorator.
    """

    field_types: T.Iterable[DjFieldType]
    proto_type_name: str

    def update_proto(self, proto_obj: ProtoMsg, field_name: str, value):
        setattr(proto_obj, field_name, value)

    def update_django(self, node: "SaveNode", field_name: str, value):
        setattr(node.django_obj, field_name, value)


DEFAULT_SERIALIZER = FieldSerializer()
SERIALIZERS: T.Dict[DjFieldType, FieldSerializer] = {}


@register_serializer
class DateTimeFieldSerializer(FieldSerializer):
    field_types = (models.DateTimeField,)
    proto_type_name = PROTO_TIMESTAMP_TYPE

    def update_proto(self, proto_obj, field_name, value):
        field = getattr(proto_obj, field_name)
        field.FromDatetime(value)

    def update_django(self, node, field_name, value):
        value = value.ToDatetime()
        value = value.replace(tzinfo=timezone.utc)
        super().update_django(node, field_name, value)


@register_serializer
class UUIDFieldSerializer(FieldSerializer):
    field_types = (models.UUIDField,)
    proto_type_name = "string"

    def update_proto(self, proto_obj, field_name, value):
        value = str(value)
        super().update_proto(proto_obj, field_name, value)

    def update_django(self, node, field_name, value):
        value = uuid.UUID(value)
        super().update_django(node, field_name, value)


@register_serializer
class FileFieldSerializer(FieldSerializer):
    field_types = (models.FileField,)
    proto_type_name = "string"

    @property
    def use_url(self):
        try:
            return settings.DJPB_FILE_FIELD_USE_URL
        except AttributeError:
            return False

    def update_proto(self, proto_obj, field_name, value):
        if self.use_url:
            try:
                value = value.url
            except ValueError:
                value = ""
        else:
            value = str(value)

        super().update_proto(proto_obj, field_name, value)

    def update_django(self, node, field_name, value):
        if "://" in value:
            django_field_repr = get_django_field_repr(
                models.FileField, node.django_obj.__class__, field_name
            )
            raise ValueError(
                f"Please provide the file path, not the URL for {django_field_repr} = {value!r}."
            )

        super().update_django(node, field_name, value)


@register_serializer
class JSONFieldSerializer(FieldSerializer):
    field_types = (models.JSONField,)
    proto_type_name = PROTO_VALUE_TYPE

    def update_proto(self, proto_obj, field_name, value):
        value = ParseDict(value, Value())
        field = getattr(proto_obj, field_name)
        field.CopyFrom(value)

    def update_django(self, node, field_name, value):
        value = MessageToDict(value)
        super().update_django(node, field_name, value)


class DeferredSerializer(FieldSerializer):
    def update_django(self, node, field_name, value):
        from djpb.proto_to_django import _proto_to_django

        try:
            rel_pb_objs = list(value)
        except TypeError:
            rel_pb_objs = [value]

        field = getattr(node.django_obj, field_name)
        field.all().delete()

        for pb_obj in rel_pb_objs:
            child_node = _proto_to_django(pb_obj)
            node.add_child(SaveNodeChild(self, field_name, child_node))

    def save(
        self,
        django_obj: DjModel,
        field_name: str,
        child_node: "SaveNode",
        do_full_clean: bool,
    ):
        ...


@register_serializer
class OneToXSerializer(DeferredSerializer):
    field_types = (models.OneToOneField, models.ForeignKey)

    def update_proto(self, proto_obj, field_name, value):
        from djpb import django_to_proto

        field = getattr(proto_obj, field_name)
        value = django_to_proto(value, create_proto_field_obj(proto_obj, field_name))
        field.CopyFrom(value)

    def save(self, django_obj, field_name, child_node, do_full_clean):
        # save child object
        child_node.save(do_full_clean)
        rel_obj = child_node.django_obj

        # set parent object's field to child object
        setattr(django_obj, field_name, rel_obj)

        # save parent object
        if do_full_clean:
            django_obj.full_clean()
        django_obj.save()


class ManyToXSerializer(DeferredSerializer):
    def update_proto(self, proto_obj, field_name, value):
        from djpb import django_to_proto

        field = getattr(proto_obj, field_name)
        msgs = [
            django_to_proto(obj, create_proto_field_obj(proto_obj, field_name))
            for obj in value.all()
        ]
        del field[:]
        field.extend(msgs)


@register_serializer
class ManyToOneSerializer(ManyToXSerializer):
    field_types = (ReverseManyToOneDescriptor,)

    def save(self, django_obj, field_name, child_node, do_full_clean):
        # save parent object
        if do_full_clean:
            django_obj.full_clean()
        django_obj.save()

        # get child object
        rel_obj = child_node.django_obj

        # set child object's field to parent object
        rel_manager = getattr(django_obj, field_name)
        rel_name = rel_manager.field.name
        setattr(rel_obj, rel_name, django_obj)

        # save related object
        child_node.save(do_full_clean)


@register_serializer
class ManyToManySerializer(ManyToXSerializer):
    field_types = (models.ManyToManyField,)

    def save(self, django_obj, field_name, child_node, do_full_clean):
        # save child object
        child_node.save(do_full_clean)

        # save parent object
        if do_full_clean:
            django_obj.full_clean()
        django_obj.save()

        # add child to parent's m2m manager
        rel_manager = getattr(django_obj, field_name)
        rel_obj = child_node.django_obj
        rel_manager.add(rel_obj)


class SaveNodeChild(T.NamedTuple):
    serializer: DeferredSerializer
    field_name: str
    node: "SaveNode"

    def __hash__(self) -> int:
        return hash(self.node)


@dataclass
class SaveNode:
    django_obj: DjModel

    def __post_init__(self):
        self._children: T.Set[SaveNodeChild] = set()

    def __hash__(self) -> int:
        return id(self.django_obj)

    def add_child(self, child: SaveNodeChild):
        self._children.add(child)

    def save(self, do_full_clean: bool):
        if self._children:
            for serializer, field_name, child_node in self._children:
                serializer.save(self.django_obj, field_name, child_node, do_full_clean)
        else:
            if do_full_clean:
                self.django_obj.full_clean()
            self.django_obj.save()
