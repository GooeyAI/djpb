import typing

from django.db import models
from google.protobuf.message import Message

DjModel = models.Model
DjModelType = typing.Type[models.Model]

DjField = models.Field
DjFieldType = typing.Type[models.Field]

ProtoMsg = Message
ProtoMsgType = typing.Type[Message]
