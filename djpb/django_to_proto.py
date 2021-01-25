import inspect

from django.core.exceptions import ObjectDoesNotExist

from djpb.registry import MODEL_TO_PROTO_CLS, PROTO_META, ProtoMeta
from djpb.serializers import SERIALIZERS, DEFAULT_SERIALIZER
from djpb.signals import pre_django_to_proto, post_django_to_proto
from djpb.stubs import DjModel, ProtoMsg
from djpb.util import (
    build_django_field_map,
    resolve_django_field_type,
    get_django_field_repr,
)


def django_to_proto_bytes(django_obj: DjModel, proto_obj: ProtoMsg = None) -> bytes:
    proto_obj = django_to_proto(django_obj, proto_obj)
    proto_bytes = proto_obj.SerializeToString()
    return proto_bytes


def django_to_proto(
    django_obj: DjModel, proto_obj: ProtoMsg = None, *, proto_meta: ProtoMeta = None
) -> ProtoMsg:
    django_model = type(django_obj)

    if proto_obj is None:
        try:
            proto_cls = MODEL_TO_PROTO_CLS[django_model][0]
        except IndexError:
            raise ValueError(
                f"Please specify at least one protobuf class for the model {django_model.__qualname__!r}."
            )
        proto_obj = proto_cls()

    field_map = build_django_field_map(django_obj)

    proto_meta = proto_meta or PROTO_META[django_model]
    custom = proto_meta.custom

    pre_django_to_proto.send(django_model, proto_obj=proto_obj, django_obj=django_obj)

    for proto_field in proto_obj.DESCRIPTOR.fields:
        field_name = proto_field.name

        # handle custom fields
        try:
            field = custom[field_name]
        except KeyError:
            pass
        else:
            field.update_proto(django_obj, proto_obj, field_name)
            continue

        # handle set_null
        if field_name.endswith("__set_null"):
            continue

        django_field_type = resolve_django_field_type(
            django_model, field_map, field_name
        )

        # check if proto field can be in an "unset" state
        try:
            proto_obj.HasField(field_name)
        except ValueError:
            can_unset = False
        else:
            can_unset = True

        try:
            value = getattr(django_obj, field_name)
        except ObjectDoesNotExist:
            if can_unset:
                # leave this field "unset"
                continue
            raise

        if value is None:
            if can_unset:
                # leave this field "unset"
                continue

            django_field_repr = get_django_field_repr(
                django_field_type, django_model, field_name
            )
            raise ValueError(
                f"Can't serialize None-type value for {django_field_repr}, "
                f"because protobuf doesn't support null types.\n"
                f"You can wrap the field with a `oneof` as a workaround."
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

    post_django_to_proto.send(django_model, proto_obj=proto_obj, django_obj=django_obj)

    return proto_obj
