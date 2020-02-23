MODEL_TO_PROTO_CLS = {}
PROTO_CLS_TO_MODEL = {}


def register_model(django_model):
    proto_cls = None

    try:
        proto_cls = django_model.ProtoMeta.cls
    except AttributeError:
        pass

    MODEL_TO_PROTO_CLS[django_model] = proto_cls

    if proto_cls is not None:
        PROTO_CLS_TO_MODEL[proto_cls] = django_model

    return django_model
