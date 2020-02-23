def create_django_field_map(django_obj):
    return {f.name: f for f in django_obj._meta.get_fields()}


def get_django_field_type(field_map, attr, django_model_name):
    try:
        django_field = field_map[attr]
    except KeyError:
        raise ValueError(
            f"Protobuf field {attr!r} does not exist "
            f"in Django model {django_model_name!r}."
        )
    django_field_type = type(django_field)
    return django_field_type
