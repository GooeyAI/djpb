import typing as T
import uuid

from django.conf import settings
from django.contrib.postgres.fields import JSONField
from django.db import models
from django.db.models.fields.related_descriptors import ReverseManyToOneDescriptor
from google.protobuf.json_format import MessageToDict, ParseDict
from google.protobuf.struct_pb2 import Value

from djpb.util import get_django_field_repr


class FieldSerializer:
    field_types: T.Iterable[models.Field]

    def update_proto(self, proto_obj, field_name, value):
        setattr(proto_obj, field_name, value)

    def update_django(self, django_obj, field_name, value):
        setattr(django_obj, field_name, value)


DEFAULT_SERIALIZER = FieldSerializer()
SERIALIZERS: T.Dict[models.Field, FieldSerializer] = {}


def register_serializer(cls: T.Type[FieldSerializer]) -> T.Type[FieldSerializer]:
    for field_type in cls.field_types:
        SERIALIZERS[field_type] = cls()
    return cls


@register_serializer
class DateTimeFieldSerializer(FieldSerializer):
    field_types = (models.DateTimeField,)

    def update_proto(self, proto_obj, field_name, value):
        field = getattr(proto_obj, field_name)
        field.FromDatetime(value)

    def update_django(self, django_obj, field_name, value):
        value = value.ToDatetime()
        super().update_django(django_obj, field_name, value)


@register_serializer
class UUIDFieldSerializer(FieldSerializer):
    field_types = (models.UUIDField,)

    def update_proto(self, proto_obj, field_name, value):
        value = str(value)
        super().update_proto(proto_obj, field_name, value)

    def update_django(self, django_obj, field_name, value):
        value = uuid.UUID(value)
        super().update_django(django_obj, field_name, value)


@register_serializer
class FileFieldSerializer(FieldSerializer):
    field_types = (models.FileField,)

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

    def update_django(self, django_obj, field_name, value):
        if "://" in value:
            django_field_repr = get_django_field_repr(
                models.FileField, django_obj.__class__, field_name
            )
            raise ValueError(
                f"Please provide the file path, not the URL for {django_field_repr} = {value!r}."
            )

        super().update_django(django_obj, field_name, value)


@register_serializer
class JSONFieldSerializer(FieldSerializer):
    field_types = (JSONField,)

    def update_proto(self, proto_obj, field_name, value):
        value = ParseDict(value, Value())
        field = getattr(proto_obj, field_name)
        field.CopyFrom(value)

    def update_django(self, django_obj, field_name, value):
        value = MessageToDict(value)
        super().update_django(django_obj, field_name, value)


@register_serializer
class ForwardSingleSerializer(FieldSerializer):
    field_types = (models.OneToOneField, models.ForeignKey)

    def update_proto(self, proto_obj, field_name, value):
        from djpb import django_to_proto

        value = django_to_proto(value)
        field = getattr(proto_obj, field_name)
        field.CopyFrom(value)

    def update_django(self, django_obj, field_name, value):
        from djpb import proto_to_django

        value = proto_to_django(value)
        super().update_django(django_obj, field_name, value)


@register_serializer
class ReverseManySerializer(FieldSerializer):
    field_types = (ReverseManyToOneDescriptor, models.ManyToManyField)

    def update_proto(self, proto_obj, field_name, value):
        from djpb import django_to_proto

        msgs = [django_to_proto(obj) for obj in value.all()]
        field = getattr(proto_obj, field_name)
        del field[:]
        field.extend(msgs)

    def update_django(self, django_obj, field_name, value):
        from djpb import proto_to_django

        django_obj.save()

        rel_manager = getattr(django_obj, field_name)
        rel_name = rel_manager.field.name

        rel_objs = [proto_to_django(obj) for obj in value]
        for rel_obj in rel_objs:
            setattr(rel_obj, rel_name, django_obj)
            rel_obj.save()

        rel_manager.set(rel_objs, bulk=False)
