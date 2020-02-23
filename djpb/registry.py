MODEL_TO_PROTO_CLS = {}
PROTO_CLS_TO_MODEL = {}


def register_model(proto_cls):
    def wrapper(django_model):
        MODEL_TO_PROTO_CLS[django_model] = proto_cls
        PROTO_CLS_TO_MODEL[proto_cls] = django_model
        return django_model

    return wrapper
