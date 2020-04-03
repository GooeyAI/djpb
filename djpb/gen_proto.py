import inspect
import io
from contextlib import redirect_stdout

from django.contrib.postgres.fields import JSONField
from django.db import models
from django.db.models.fields.related_descriptors import (
    ReverseManyToOneDescriptor,
    ReverseOneToOneDescriptor,
    ManyToManyDescriptor,
)

from djpb.util import get_django_field_repr, build_django_field_map

PROTO_TIMESTAMP = "google.protobuf.Timestamp"
PROTO_STRUCT = "google.protobuf.Struct"
PROTO_ANY = "google.protobuf.Any"
PROTO_VALUE = "google.protobuf.Value"

PROTO_IMPORTS = {
    PROTO_ANY: "google/protobuf/any.proto",
    PROTO_VALUE: "google/protobuf/struct.proto",
    PROTO_STRUCT: "google/protobuf/struct.proto",
    PROTO_TIMESTAMP: "google/protobuf/timestamp.proto",
}

DJANGO_TO_PROTO_FIELD_TYPE = {
    models.FileField: "string",
    models.TextField: "string",
    models.CharField: "string",
    models.UUIDField: "string",
    models.IntegerField: "int32",
    models.BooleanField: "bool",
    JSONField: PROTO_VALUE,
    models.DateTimeField: PROTO_TIMESTAMP,
}

RELATED_FIELD_TYPES = [
    models.ForeignKey,
    models.OneToOneField,
    models.ManyToManyField,
    ReverseManyToOneDescriptor,
    ReverseOneToOneDescriptor,
    ManyToManyDescriptor,
]
RELATED_FIELD_TYPES_MANY = [
    models.ManyToManyField,
    ManyToManyDescriptor,
    ReverseManyToOneDescriptor,
]


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

                try:
                    imports.add(PROTO_IMPORTS[proto_type])
                except KeyError:
                    pass

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
    assert exclude.isdisjoint(extra), "'exclude' and 'extra' must be disjoint sets."

    field_map = build_django_field_map(model)

    # exclude the primary key by default
    pk_name = model._meta.pk.name
    if pk_name not in extra:
        del field_map[pk_name]

    for name in exclude:
        del field_map[name]

    for name in extra:
        if name in field_map:
            continue
        field_map[name] = getattr(model, name)

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
        django_field_repr = get_django_field_repr(field_type, model, field_name)
        raise ValueError(
            f"Could not find a suitable protobuf type for {django_field_repr}."
        )

    return proto_type
