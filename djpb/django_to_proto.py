import inspect

from django.core.exceptions import ObjectDoesNotExist
from django.db import models

from djpb.registry import MODEL_TO_PROTO_CLS
from djpb.serializers import SERIALIZERS, DEFAULT_SERIALIZER
from djpb.util import (
    build_django_field_map,
    resolve_django_field_type,
    get_django_field_repr,
)


def django_to_proto(django_obj: models.Model, proto_obj=None):
    django_model = type(django_obj)

    if proto_obj is None:
        proto_cls = MODEL_TO_PROTO_CLS[django_model]
        if proto_cls is None:
            raise ValueError(
                f"Please specify the protobuf class for the model {django_model.__qualname__!r}."
            )
        proto_obj = proto_cls()

    field_map = build_django_field_map(django_obj)

    proto_meta = getattr(django_model, "ProtoMeta", None)
    custom = getattr(proto_meta, "custom", {})
    null_str_fields = getattr(proto_meta, "null_str_fields", ())

    for proto_field in proto_obj.DESCRIPTOR.fields:
        field_name = proto_field.name

        if field_name in custom:
            continue

        django_field_type = resolve_django_field_type(
            django_model, field_map, field_name
        )
        is_wrapper_type = proto_field.message_type is not None

        try:
            value = getattr(django_obj, field_name)
        except ObjectDoesNotExist:
            if is_wrapper_type:
                # leave this field "unset"
                continue
            raise

        if value is None:
            if field_name in null_str_fields:
                # use empty string and None interchangeably
                value = ""

            elif is_wrapper_type:
                # leave this field "unset"
                continue

            else:
                django_field_repr = get_django_field_repr(
                    django_field_type, django_model, field_name
                )
                raise ValueError(
                    f"Can't serialize None-type value for {django_field_repr}, "
                    f"because protobuf doesn't support null types."
                )

        # walk down the MRO to resolve the serializer for this field type
        serializer = DEFAULT_SERIALIZER
        for base_type in inspect.getmro(django_field_type):
            try:
                serializer = SERIALIZERS[base_type]
            except KeyError:
                continue
            else:
                break

        try:
            serializer.update_proto(proto_obj, field_name, value)
        except Exception as e:
            django_field_repr = get_django_field_repr(
                django_field_type, django_model, field_name
            )
            serializer_repr = repr(serializer.__class__.__qualname__)
            raise ValueError(
                f"Failed to serialize {django_field_repr} using {serializer_repr}."
            ) from e

    return proto_obj


def django_to_proto_bytes(django_obj, proto_obj=None) -> bytes:
    proto_obj = django_to_proto(django_obj, proto_obj)
    proto_bytes = proto_obj.SerializeToString()
    return proto_bytes
