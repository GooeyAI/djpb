from dataclasses import dataclass

from django.db import models
from google.protobuf.message import Message

from .serializers import SaveNode


@dataclass
class CustomField:
    proto_type: str
    null: bool = False

    def update_proto(
        self, django_obj: models.Model, proto_obj: Message, field_name: str
    ):
        pass

    def update_django(self, node: "SaveNode", proto_obj: Message, field_name: str):
        pass


@dataclass
class ReadOnlyField(CustomField):
    query: str = None

    def update_proto(
        self, django_obj: models.Model, proto_obj: Message, field_name: str
    ):
        model = type(django_obj)
        value = (
            model.objects.filter(pk=django_obj.pk)
            .values_list(self.query or field_name, flat=True)
            .first()
        )
        if value is None:
            return
        setattr(proto_obj, field_name, value)