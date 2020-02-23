import typing as T
import uuid

from django.contrib.postgres.fields import JSONField
from django.db import models
from google.protobuf.struct_pb2 import Struct


class FieldSerializer:
    field_types: T.Iterable[models.Field]

    def update_proto(self, obj, attr, value):
        setattr(obj, attr, value)

    def update_django(self, obj, attr, value):
        setattr(obj, attr, value)


DEFAULT_SERIALIZER = FieldSerializer()
SERIALIZERS: T.Dict[models.Field, FieldSerializer] = {}


def register_serializer(cls: T.Type[FieldSerializer]) -> T.Type[FieldSerializer]:
    for field_type in cls.field_types:
        SERIALIZERS[field_type] = cls()
    return cls


@register_serializer
class DateTimeFieldSerializer(FieldSerializer):
    field_types = (models.DateTimeField,)

    def update_proto(self, obj, attr, value):
        field = getattr(obj, attr)
        field.FromDatetime(value)

    def update_django(self, obj, attr, value):
        value = value.ToDatetime()
        super().update_django(obj, attr, value)


@register_serializer
class UUIDFieldSerializer(FieldSerializer):
    field_types = (models.UUIDField,)

    def update_proto(self, obj, attr, value):
        value = str(value)
        super().update_proto(obj, attr, value)

    def update_django(self, obj, attr, value):
        value = uuid.UUID(value)
        super().update_django(obj, attr, value)


@register_serializer
class FileFieldSerializer(FieldSerializer):
    field_types = (models.FileField,)

    def update_proto(self, obj, attr, value):
        value = str(value)
        super().update_proto(obj, attr, value)


@register_serializer
class JSONFieldSerializer(FieldSerializer):
    field_types = (JSONField,)

    def update_proto(self, obj, attr, value):
        struct = Struct()
        struct.update(value)

        field = getattr(obj, attr)
        field.CopyFrom(struct)

    def update_django(self, obj, attr, value):
        value = dict(value)
        super().update_django(obj, attr, value)


@register_serializer
class RelatedFieldSerializer(FieldSerializer):
    field_types = (models.ForeignKey, models.OneToOneField)

    def update_proto(self, obj, attr, value):
        struct = Struct()
        struct.update(value)

        field = getattr(obj, attr)
        field.CopyFrom(struct)

    def update_django(self, obj, attr, value):
        value = dict(value)
        super().update_django(obj, attr, value)
