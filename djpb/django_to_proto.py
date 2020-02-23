from djpb.serializer import SERIALIZERS, DEFAULT_SERIALIZER
from djpb.util import create_django_field_map, get_django_field_type
from djpb.registry import MODEL_TO_PROTO_CLS


def django_to_proto(django_obj, proto_obj=None):
    if proto_obj is None:
        proto_cls = MODEL_TO_PROTO_CLS[django_obj]
        proto_obj = proto_cls()

    django_model_name = django_obj.__class__.__qualname__
    field_map = create_django_field_map(django_obj)

    for proto_field in proto_obj.DESCRIPTOR.fields:
        attr = proto_field.name
        is_wrapper_type = proto_field.message_type is not None
        django_field_type = get_django_field_type(field_map, attr, django_model_name)

        try:
            value = getattr(django_obj, attr)
        except django_obj.ObjectDoesNotExist:
            if is_wrapper_type:
                # leave this field "unset"
                continue
            raise

        if value is None:
            if is_wrapper_type:
                # leave this field "unset"
                continue
            raise ValueError(
                f"Can't serialize a None-type value for {django_field_type} {attr!r} "
                f"of Django model {django_model_name!r}."
            )

        serializer = SERIALIZERS.get(django_field_type, DEFAULT_SERIALIZER)
        serializer.update_proto(proto_obj, attr, value)

    return proto_obj


def django_to_proto_bytes(django_obj, proto_obj=None) -> bytes:
    proto_obj = django_to_proto(django_obj, proto_obj)
    proto_bytes = proto_obj.SerializeToString()
    return proto_bytes
