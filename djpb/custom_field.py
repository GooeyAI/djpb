from dataclasses import dataclass

from django.db import models
from google.protobuf.message import Message

from .serializers import SaveNode


@dataclass
class CustomField:
    proto_type: str
    null: bool = False

    def update_proto(self, django_obj: models.Model, proto_obj: Message):
        pass

    def update_django(self, node: "SaveNode", proto_obj: Message):
        pass
