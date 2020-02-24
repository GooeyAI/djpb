def create_django_field_map(django_obj):
    return {f.name: f for f in django_obj._meta.get_fields()}


def get_django_field_type(django_model, field_map, attr):
    django_field = None
    try:
        django_field = field_map[attr]
    except KeyError:
        try:
            django_field = getattr(django_model, attr)
        except AttributeError:
            pass

    if django_field is None:
        raise ValueError(
            f"Protobuf field {attr!r} does not exist "
            f"in Django model {django_model.__qualname__!r}."
        )

    django_field_type = type(django_field)
    return django_field_type
