from django.dispatch import Signal

_args = ["proto_obj", "django_obj"]

pre_proto_to_django = Signal(providing_args=_args)
post_proto_to_django = Signal(providing_args=_args)

pre_django_to_proto = Signal(providing_args=_args)
post_django_to_proto = Signal(providing_args=_args)
