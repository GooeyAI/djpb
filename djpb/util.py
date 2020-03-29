import typing as T

from django.db import models

DjangoFieldMap = T.Dict[str, models.Field]

from django.db import models


def build_django_field_map(django_obj) -> DjangoFieldMap:
    options = django_obj._meta
    fields = options.fields + options.many_to_many
    field_map = {f.name: f for f in fields}
    return field_map


def resolve_django_field_type(
    django_model: T.Type[models.Model], field_map: DjangoFieldMap, field_name: str
) -> T.Type[models.Field]:
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

    django_field_type = type(django_field)
    return django_field_type


def get_django_field_repr(
    django_field_type: T.Type[models.Field],
    django_model: T.Type[models.Model],
    field_name: str,
) -> str:
    return f"field '{django_model.__qualname__}.{field_name}' of type {django_field_type.__qualname__!r}"
