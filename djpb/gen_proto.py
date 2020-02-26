import inspect
import io
from contextlib import redirect_stdout

from django.contrib.postgres.fields import JSONField
from django.db import models
from django.db.models.fields.related_descriptors import (
    ReverseManyToOneDescriptor,
    ReverseOneToOneDescriptor,
)

PROTO_TIMESTAMP_IMPORT = "google/protobuf/timestamp.proto"
PROTO_TIMESTAMP = "google.protobuf.Timestamp"

PROTO_STRUCT_IMPORT = "google/protobuf/struct.proto"
PROTO_STRUCT = "google.protobuf.Struct"

DJANGO_TO_PROTO_FIELD_TYPE = {
    models.FileField: "string",
    models.TextField: "string",
    models.CharField: "string",
    models.UUIDField: "string",
    JSONField: "string",
    models.IntegerField: "int32",
    models.BooleanField: "bool",
    models.DateTimeField: PROTO_TIMESTAMP,
}

RELATED_FIELD_TYPES = [
    models.ForeignKey,
    models.OneToOneField,
    models.ManyToManyField,
    ReverseManyToOneDescriptor,
    ReverseOneToOneDescriptor,
]
RELATED_FIELD_TYPES_MANY = [models.ManyToManyField, ReverseManyToOneDescriptor]


def gen_proto_for_models(dj_models):
    proto_models = {}
    imports = set()

    for model in dj_models:
        _gen_proto_for_model(model, proto_models)

    with io.StringIO() as f, redirect_stdout(f):
        for model, fields in proto_models.items():
            print("message %s {" % model.__name__)

            for i, (field_name, proto_type) in enumerate(fields.items()):
                line = f"{proto_type} {field_name} = {i + 1};"
                print(" " * 4 + line)

                if proto_type == PROTO_STRUCT:
                    imports.add(PROTO_STRUCT_IMPORT)
                if proto_type == PROTO_TIMESTAMP:
                    imports.add(PROTO_TIMESTAMP_IMPORT)

            print("}\n")

        body = f.getvalue()

    with io.StringIO() as f, redirect_stdout(f):
        print('syntax = "proto3";\n')

        for i in imports:
            print(f'import "{i}";')
        print()

        body = f.getvalue() + body

    body = body.strip()
    return body


def _gen_proto_for_model(model, proto_models):
    if model in proto_models:
        return

    proto_models[model] = {}

    try:
        exclude = set(model.ProtoMeta.exclude)
    except AttributeError:
        exclude = set()
    try:
        extra = set(model.ProtoMeta.extra)
    except AttributeError:
        extra = set()

    field_map = {f.name: f for f in model._meta.fields}

    for name in extra:
        if name in field_map:
            continue
        field_map[name] = getattr(model, name)
    for name in exclude:
        del field_map[name]

    fields = {
        name: _resolve_proto_type(name, field, model, proto_models)
        for name, field in field_map.items()
    }

    proto_models[model] = fields


def _resolve_proto_type(field_name, field, model, proto_models):
    field_type = type(field)

    try:
        enums = model.ProtoMeta.enums
    except AttributeError:
        enums = {}

    if field_name in enums:
        enum_cls = enums[field_name]
        enum_clsname = enum_cls.DESCRIPTOR.name
        return enum_clsname

    if field_type in RELATED_FIELD_TYPES:
        try:
            related_model = field.related_model
        except AttributeError:
            related_model = field.field.model

        _gen_proto_for_model(related_model, proto_models)

        proto_type = related_model.__name__
        if field_type in RELATED_FIELD_TYPES_MANY:
            proto_type = f"repeated {proto_type}"

        return proto_type

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

    return proto_type