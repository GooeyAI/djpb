from django.dispatch import Signal

pre_proto_to_django = Signal()
post_proto_to_django = Signal()

pre_django_to_proto = Signal()
post_django_to_proto = Signal()
