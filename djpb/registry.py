import typing
from collections import defaultdict

from djpb.stubs import DjModelType, ProtoMsgType

MODEL_TO_PROTO_CLS: typing.DefaultDict[
    DjModelType, typing.List[ProtoMsgType]
] = defaultdict(lambda: [])

PROTO_CLS_TO_MODEL: typing.Dict[ProtoMsgType, DjModelType] = {}


def register_model(proto_classes: typing.List[ProtoMsgType]):
    def decorator(django_model: DjModelType):
        MODEL_TO_PROTO_CLS[django_model] = proto_classes

        for proto_class in proto_classes:
            PROTO_CLS_TO_MODEL[proto_class] = django_model

        return django_model

    return decorator
