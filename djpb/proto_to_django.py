from djpb.django_to_proto import SERIALIZERS, DEFAULT_SERIALIZER
from djpb.registry import PROTO_CLS_TO_MODEL
from djpb.util import create_django_field_map, get_django_field_type


def proto_to_django(proto_obj, django_obj=None):
    if django_obj is None:
        proto_cls = type(proto_obj)
        django_cls = PROTO_CLS_TO_MODEL[proto_cls]
        django_obj = django_cls()

    django_model = django_obj.__class__
    field_map = create_django_field_map(django_obj)

    for proto_field in proto_obj.DESCRIPTOR.fields:
        field_name = proto_field.name

        try:
            if not proto_obj.HasField(field_name):
                # leave "unset" fields as-is
                continue
        except ValueError:
            pass

        django_field_type = get_django_field_type(django_model, field_map, field_name)
        value = getattr(proto_obj, field_name)

        # print(field_name, django_field_type)

        serializer = SERIALIZERS.get(django_field_type, DEFAULT_SERIALIZER)
        serializer.update_django(django_obj, field_name, value)

    return django_obj


def proto_bytes_to_django(proto_bytes: bytes, proto_obj, django_obj=None):
    proto_obj = proto_obj.MergeFromString(proto_bytes)
    django_obj = proto_to_django(proto_obj, django_obj)
    return django_obj
