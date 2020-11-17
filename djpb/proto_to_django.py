from django.db import transaction

from djpb.django_to_proto import SERIALIZERS, DEFAULT_SERIALIZER
from djpb.registry import PROTO_CLS_TO_MODEL, MODEL_TO_PROTO_CLS
from djpb.serializers import FieldSerializer, SaveNode
from djpb.util import (
    build_django_field_map,
    resolve_django_field_type,
    get_django_field_repr,
)
from .signals import post_proto_to_django, pre_proto_to_django
from .stubs import ProtoMsg, DjModel, DjModelType


def proto_to_django(
    proto_obj: ProtoMsg, django_obj: DjModel = None, *, do_full_clean=False
) -> DjModel:
    node = _proto_to_django(proto_obj, django_obj)
    with transaction.atomic():
        node.save(do_full_clean)
    django_obj = node.django_obj
    return django_obj


def _proto_to_django(proto_obj: ProtoMsg, django_obj: DjModel = None) -> SaveNode:
    proto_fields = {x.name: x for x in proto_obj.DESCRIPTOR.fields}

    if django_obj is None:
        proto_cls = type(proto_obj)
        django_cls = PROTO_CLS_TO_MODEL[proto_cls]

        # try to get an existing object if it's pk is present in the proto fields
        pk_field_name = django_cls._meta.pk.name

        if pk_field_name in proto_fields:
            pk = getattr(proto_obj, pk_field_name)

            if pk:  # pk might be 0, let's ignore that
                try:
                    django_obj = django_cls.objects.get(**{pk_field_name: pk})
                except django_cls.DoesNotExist:
                    pass

        if django_obj is None:
            django_obj = django_cls()

    django_model = django_obj.__class__
    field_map = build_django_field_map(django_obj)
    node = SaveNode(django_obj)

    proto_meta = getattr(django_model, "ProtoMeta", None)
    custom = getattr(proto_meta, "custom", {})

    pre_proto_to_django.send(django_model, proto_obj=proto_obj, django_obj=django_obj)

    for field_name, proto_field in proto_fields.items():
        # determine if field is in "unset" state
        try:
            unset = not proto_obj.HasField(field_name)
        except ValueError:
            unset = False

        if unset:
            try:
                field = field_map[field_name]
            except KeyError:
                pass
            else:
                if field.null:
                    setattr(django_obj, field_name, None)
            # leave "unset" fields as-is
            continue

        # handle custom fields
        try:
            field = custom[field_name]
        except KeyError:
            pass
        else:
            field.update_django(node, proto_obj, field_name)
            continue

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

    post_proto_to_django.send(django_model, proto_obj=proto_obj, django_obj=django_obj)

    return node
