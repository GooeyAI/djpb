import inspect
import io
import typing
from contextlib import redirect_stdout
from textwrap import indent

from django.db import models
from django.db.models.fields.related_descriptors import (
    ReverseManyToOneDescriptor,
    ReverseOneToOneDescriptor,
    ManyToManyDescriptor,
    ForeignKeyDeferredAttribute,
)

from .registry import PROTO_META
from .stubs import DjField, DjFieldType, DjModelType
from .util import get_django_field_repr, build_django_field_map, disjoint

PROTO_TIMESTAMP_TYPE = "google.protobuf.Timestamp"
PROTO_STRUCT_TYPE = "google.protobuf.Struct"
PROTO_ANY_TYPE = "google.protobuf.Any"
PROTO_VALUE_TYPE = "google.protobuf.Value"

PROTO_IMPORTS = {
    PROTO_ANY_TYPE: "google/protobuf/any.proto",
    PROTO_VALUE_TYPE: "google/protobuf/struct.proto",
    PROTO_STRUCT_TYPE: "google/protobuf/struct.proto",
    PROTO_TIMESTAMP_TYPE: "google/protobuf/timestamp.proto",
}

DJANGO_TO_PROTO_FIELD_TYPE = {
    models.TextField: "string",
    models.CharField: "string",
    models.IntegerField: "int32",
    models.BooleanField: "bool",
    models.FloatField: "double",
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

SCALAR_FIELD_TYPES = {
    "double",
    "float",
    "int32",
    "int64",
    "uint32",
    "uint64",
    "sint32",
    "sint64",
    "fixed32",
    "fixed64",
    "sfixed32",
    "sfixed64",
    "bool",
    "string",
    "bytes",
}

ProtoFields = typing.Dict[str, typing.Tuple[DjField, str]]
ProtoModels = typing.Dict[DjFieldType, ProtoFields]


def gen_proto_for_models(dj_models: typing.Iterable[DjModelType]):
    proto_models: ProtoModels = {}
    imports = set()

    for model in dj_models:
        _gen_proto_for_model(model, proto_models)

    with io.StringIO() as f, redirect_stdout(f):
        for model, fields in proto_models.items():
            print("message %s {" % model.__name__)

            for i, (field_name, (field, proto_type)) in enumerate(fields.items()):
                line = f"{proto_type} {field_name} = {i + 1};"

                oneof = (
                    getattr(field, "null", False) and proto_type in SCALAR_FIELD_TYPES
                )
                if oneof:
                    line = indent(line, " " * 4)
                    line = "oneof __%s_oneof {\n%s\n}" % (field_name, line)

                line = indent(line, " " * 4)
                print(line)

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


def _gen_proto_for_model(model: DjModelType, proto_models: ProtoModels):
    if model in proto_models:
        return
    proto_models[model] = {}

    proto_meta = PROTO_META[model]

    field_map = build_django_field_map(model)

    if proto_meta.fields:
        assert not (
            proto_meta.exclude or proto_meta.extra
        ), "'exclude' and 'extra' are not allowed if 'fields' is specified.."

        field_map = {
            name: field_map.get(name) or getattr(model, name)
            for name in proto_meta.fields
        }
    else:
        assert disjoint(
            proto_meta.exclude, proto_meta.extra
        ), "'exclude' and 'extra' must be disjoint sets."

        # exclude the primary key by default
        pk_name = model._meta.pk.name
        if pk_name not in proto_meta.extra:
            del field_map[pk_name]

        for name in proto_meta.exclude:
            del field_map[name]

        for name in proto_meta.extra:
            if name in field_map:
                continue
            field_map[name] = getattr(model, name)

    proto_fields = {
        name: _resolve_proto_type(name, field, model, proto_models)
        for name, field in field_map.items()
    }

    # add custom fields
    custom = getattr(proto_meta, "custom", {})
    proto_fields.update(
        {name: (field, field.proto_type) for name, field in custom.items()}
    )

    proto_models[model] = proto_fields


def _resolve_proto_type(
    field_name: str, field, model: DjModelType, proto_models: ProtoModels
) -> typing.Tuple[DjField, str]:
    field_type = type(field)

    proto_meta = PROTO_META[model]

    if field_name in proto_meta.enums:
        enum_cls = proto_meta.enums[field_name]
        enum_clsname = enum_cls.DESCRIPTOR.name
        return field, enum_clsname

    if issubclass(field_type, ForeignKeyDeferredAttribute):
        field = field.field
        model = field.related_model
        pk_field = model._meta.pk
        proto_type = _proto_type_for_field(pk_field.name, type(pk_field), model)

    elif field_type in RELATED_FIELD_TYPES:
        try:
            related_model = field.related_model
        except AttributeError:
            related_model = field.field.model

        _gen_proto_for_model(related_model, proto_models)

        proto_type = related_model.__name__
        if field_type in RELATED_FIELD_TYPES_MANY:
            proto_type = f"repeated {proto_type}"

    else:
        proto_type = _proto_type_for_field(field_name, field_type, model)

    return field, proto_type


def _proto_type_for_field(
    field_name: str, field_type: DjFieldType, model: DjModelType,
) -> str:
    # walk down the MRO to resolve the field type
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
