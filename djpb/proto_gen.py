import inspect
import io
from contextlib import redirect_stdout

from django.contrib.postgres.fields import JSONField
from django.db import models

PROTO_TIMESTAMP_IMPORT = 'import "google/protobuf/timestamp.proto";'
PROTO_TIMESTAMP = "google.protobuf.Timestamp"

PROTO_STRUCT_IMPORT = 'import "google/protobuf/struct.proto";'
PROTO_STRUCT = "google.protobuf.Struct"

DJANGO_TO_PROTO_FIELD_TYPE = {
    models.FileField: "string",
    models.TextField: "string",
    models.CharField: "string",
    models.UUIDField: "string",
    models.IntegerField: "string",
    models.BooleanField: "bool",
    JSONField: PROTO_STRUCT,
    models.DateTimeField: PROTO_TIMESTAMP,
}


def gen_proto_for_models(*dj_models, prefix=""):
    gen_types = {}
    gen_imports = set()

    for model in dj_models:
        _gen_proto_for_model(model, gen_types, gen_imports, prefix)

    with io.StringIO() as f, redirect_stdout(f):
        for i in gen_imports:
            print(i)

        print()

        for name, lines in gen_types.items():
            print("message %s {" % name)
            for line in lines:
                print(" " * 4 + line)
            print("}\n")

        return f.getvalue()


def _gen_proto_for_model(model, gen_types, gen_imports, prefix):
    lines = [
        _gen_proto_field(i, field, model, gen_types, gen_imports, prefix)
        for i, field in enumerate(model._meta.fields)
    ]
    gen_types[prefix + model.__name__] = lines


def _gen_proto_field(i, field, model, gen_types, gen_imports, prefix):
    field_name = field.name
    field_type = type(field)

    if field_type in [models.ForeignKey, models.OneToOneField, models.ManyToManyField]:
        related_model = field.related_model
        _gen_proto_for_model(related_model, gen_types, gen_imports, prefix)

        proto_type = prefix + related_model.__name__
        if field_type == models.ManyToManyField:
            proto_type = f"repeated {proto_type}"
    else:
        proto_type = None
        for base_type in inspect.getmro(field_type):
            try:
                proto_type = DJANGO_TO_PROTO_FIELD_TYPE[base_type]
            except KeyError:
                continue
            else:
                break

        if proto_type is None:
            raise ValueError(
                f"Cannot convert {field_type.__qualname__!r} "
                f"'{model.__qualname__}.{field_name}' to protobuf type."
            )

    if proto_type == PROTO_STRUCT:
        gen_imports.add(PROTO_STRUCT_IMPORT)

    if proto_type == PROTO_TIMESTAMP:
        gen_imports.add(PROTO_TIMESTAMP_IMPORT)

    return f"{proto_type} {field_name} = {i + 1};"
