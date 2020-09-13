import typing

from django.db.models import Model
from google.protobuf.reflection import GeneratedProtocolMessageType

DjModel = typing.TypeVar("DjModel", bound=Model)
DjModelType = typing.Type[DjModel]

ProtoMsg = typing.TypeVar("ProtoMsg", bound=GeneratedProtocolMessageType)
ProtoMsgType = typing.Type[ProtoMsg]
