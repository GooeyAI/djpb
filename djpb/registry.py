import typing
from collections import defaultdict

from .stubs import DjModelType, ProtoMsgType

# to avoid circular import
if False:
    from .custom_field import CustomField

MODEL_TO_PROTO_CLS: typing.DefaultDict[
    DjModelType, typing.List[ProtoMsgType]
] = defaultdict(lambda: [])

PROTO_CLS_TO_MODEL: typing.Dict[ProtoMsgType, DjModelType] = {}


class ProtoMeta:
    def __init__(
        self,
        exclude: typing.Sequence[str] = (),
        extra: typing.Sequence[str] = (),
        fields: typing.Sequence[str] = (),
        custom: typing.Dict[str, "CustomField"] = None,
        enums: typing.Dict[str, typing.Type] = None,
    ):
        if custom is None:
            custom = {}
        if enums is None:
            enums = {}
        self.exclude = exclude
        self.extra = extra
        self.fields = fields
        self.custom = custom
        self.enums = enums


PROTO_META: typing.DefaultDict[DjModelType, ProtoMeta] = defaultdict(ProtoMeta)


def register_model(
    proto_classes: typing.List[ProtoMsgType], proto_meta: ProtoMeta = None
):
    def decorator(django_model: DjModelType):
        MODEL_TO_PROTO_CLS[django_model] = proto_classes
        if proto_meta:
            PROTO_META[django_model] = proto_meta
        for proto_class in proto_classes:
            PROTO_CLS_TO_MODEL[proto_class] = django_model

        return django_model

    return decorator
