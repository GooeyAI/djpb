import typing

from django.db import models
from google.protobuf.reflection import GeneratedProtocolMessageType

DjModel = typing.TypeVar("DjModel", bound=models.Model)
DjModelType = typing.Type[DjModel]

DjField = typing.TypeVar("DjField", bound=models.Field)
DjFieldType = typing.Type[DjField]

ProtoMsg = typing.TypeVar("ProtoMsg", bound=GeneratedProtocolMessageType)
ProtoMsgType = typing.Type[ProtoMsg]
