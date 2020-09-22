import typing

from django.db import models
from google.protobuf.message import Message

DjModel = typing.TypeVar("DjModel", bound=models.Model)
DjModelType = typing.TypeVar("DjModelType", bound=typing.Type[models.Model])

DjField = typing.TypeVar("DjField", bound=models.Field)
DjFieldType = typing.TypeVar("DjFieldType", bound=typing.Type[models.Field])

ProtoMsg = typing.TypeVar("ProtoMsg", bound=Message)
ProtoMsgType = typing.TypeVar("ProtoMsgType", bound=typing.Type[Message])
