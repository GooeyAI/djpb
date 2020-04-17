import typing as T

from django.db import models, transaction
from google.protobuf.message import Message

from djpb.django_to_proto import SERIALIZERS, DEFAULT_SERIALIZER
from djpb.registry import PROTO_CLS_TO_MODEL, MODEL_TO_PROTO_CLS
from djpb.serializers import FieldSerializer, SaveNode
from djpb.util import (
    build_django_field_map,
    resolve_django_field_type,
    get_django_field_repr,
)


def proto_to_django(proto_obj: Message, django_obj=None, *, do_full_clean=False):
    node = _proto_to_django(proto_obj, django_obj)
    with transaction.atomic():
        node.save(do_full_clean)
    django_obj = node.django_obj
    return django_obj


def _proto_to_django(proto_obj: Message, django_obj=None) -> SaveNode:
    if django_obj is None:
        proto_cls = type(proto_obj)
        django_cls = PROTO_CLS_TO_MODEL[proto_cls]
        django_obj = django_cls()

    django_model = django_obj.__class__
    field_map = build_django_field_map(django_obj)
    node = SaveNode(django_obj)

    for proto_field in proto_obj.DESCRIPTOR.fields:
        field_name = proto_field.name

        try:
            if not proto_obj.HasField(field_name):
                # leave "unset" fields as-is
                continue
        except ValueError:
            pass

        django_field_type = resolve_django_field_type(
            django_model, field_map, field_name
        )
        value = getattr(proto_obj, field_name)

        serializer: FieldSerializer = SERIALIZERS.get(
            django_field_type, DEFAULT_SERIALIZER
        )
        try:
            serializer.update_django(node, field_name, value)
        except Exception as e:
            django_field_repr = get_django_field_repr(
                django_field_type, django_model, field_name
            )
            serializer_repr = repr(serializer.__class__.__qualname__)
            raise ValueError(
                f"Failed to de-serialize {django_field_repr} using {serializer_repr}."
            ) from e

    return node


def proto_bytes_to_django(
    proto_bytes: bytes,
    django_model: T.Type[models.Model],
    django_obj: models.Model = None,
) -> models.Model:
    proto_obj = proto_bytes_to_proto(proto_bytes, django_model)
    django_obj = proto_to_django(proto_obj, django_obj)
    return django_obj


def proto_bytes_to_proto(proto_bytes: bytes, django_model: T.Type[models.Model]):
    proto_cls = MODEL_TO_PROTO_CLS[django_model]
    proto_obj = proto_cls()
    proto_obj.MergeFromString(proto_bytes)
    return proto_obj
