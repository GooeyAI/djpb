import typing

from django.db.models.fields.related_descriptors import ForeignKeyDeferredAttribute

from djpb.stubs import DjModel, DjField, DjModelType, DjFieldType, ProtoMsg

DjangoFieldMap = typing.Dict[str, DjField]


def build_django_field_map(django_obj: DjModel) -> DjangoFieldMap:
    options = django_obj._meta
    fields = options.fields + options.many_to_many
    field_map = {f.name: f for f in fields}
    return field_map


def resolve_django_field_type(
    django_model: DjModelType, field_map: DjangoFieldMap, field_name: str
) -> DjFieldType:
    django_field = None
    try:
        django_field = field_map[field_name]
    except KeyError:
        try:
            django_field = getattr(django_model, field_name)
        except AttributeError:
            pass

    if django_field is None:
        raise ValueError(
            f"Protobuf field {field_name!r} does not exist "
            f"in Django model {django_model.__qualname__!r}."
        )

    if isinstance(django_field, ForeignKeyDeferredAttribute):
        related_model = django_field.field.related_model
        django_field = related_model._meta.pk

    django_field_type = type(django_field)
    return django_field_type


def get_django_field_repr(
    django_field_type: DjFieldType, django_model: DjModelType, field_name: str,
) -> str:
    return f"field '{django_model.__qualname__}.{field_name}' of type {django_field_type.__qualname__!r}"


def disjoint(x, y):
    return set(x).isdisjoint(y)


def create_proto_field_obj(proto_obj: ProtoMsg, field_name: str) -> ProtoMsg:
    fields = {field.name: field for field in proto_obj.DESCRIPTOR.fields}
    field = fields[field_name]
    return field.message_type._concrete_class()
