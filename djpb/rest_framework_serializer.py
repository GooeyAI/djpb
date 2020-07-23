import typing as T

import msgpack
from django.core.exceptions import ValidationError
from django.db import models
from google.protobuf.message import Message
from google.protobuf.reflection import GeneratedProtocolMessageType
from msgpack import UnpackException
from rest_framework import serializers
from rest_framework.exceptions import ParseError
from rest_framework.fields import get_error_detail
from rest_framework.parsers import BaseParser
from rest_framework.renderers import BaseRenderer

from .django_to_proto import django_to_proto
from .proto_to_django import proto_to_django
from .registry import MODEL_TO_PROTO_CLS


class MessagePackRenderer(BaseRenderer):
    media_type = "application/msgpack"
    format = "msgpack"
    render_style = "binary"
    charset = None

    def render(self, data, media_type=None, renderer_context=None):
        return msgpack.packb(data, use_bin_type=True)


class MessagePackParser(BaseParser):
    media_type = "application/msgpack"

    def parse(self, stream, media_type=None, parser_context=None):
        try:
            return msgpack.load(stream)
        except UnpackException as e:
            raise ParseError(f"MessagePack parse error - {e!r}") from e


class RestFrameworkSerializer(serializers.BaseSerializer):
    class Meta:
        model: T.Type[models.Model]
        do_full_clean: bool

    @classmethod
    def for_model(
        cls, _model: T.Type[models.Model], _do_full_clean=True,
    ):
        class _RestFrameworkSerializer(RestFrameworkSerializer):
            class Meta:
                model = _model
                do_full_clean = _do_full_clean

        return _RestFrameworkSerializer

    def to_internal_value(self, data):
        return data

    def create(self, validated_data):
        """Create a django `instance` from validated json data"""
        return self.update(self.Meta.model(), validated_data)

    def update(self, instance, validated_data):
        """Update a django `instance` with validated json data"""
        proto_obj = self.proto_cls.FromString(validated_data)
        return self.from_proto_representation(proto_obj, instance)

    def to_representation(self, instance: models.Model):
        """Convert a django model `instance` to binary"""
        proto_obj = self.to_proto_representation(instance)
        return proto_obj.SerializeToString()

    def to_proto_representation(self, instance: models.Model):
        """Convert a django model `instance` to protobuf object"""
        proto_obj = self.proto_cls()
        proto_obj = django_to_proto(instance, proto_obj)
        return proto_obj

    def from_proto_representation(self, proto_obj, instance):
        """Convert protobuf object to a django model instance"""
        try:
            instance = proto_to_django(
                proto_obj,
                instance,
                do_full_clean=getattr(self.Meta, "do_full_clean", True),
            )
        except ValidationError as e:
            raise serializers.ValidationError(get_error_detail(e))

        return instance

    @property
    def proto_cls(self) -> T.Type[GeneratedProtocolMessageType]:
        return MODEL_TO_PROTO_CLS[self.Meta.model]

    def save(self, **kwargs):
        assert not hasattr(self, "save_object"), (
            "Serializer `%s.%s` has old-style version 2 `.save_object()` "
            "that is no longer compatible with REST framework 3. "
            "Use the new-style `.create()` and `.update()` methods instead."
            % (self.__class__.__module__, self.__class__.__name__)
        )

        assert hasattr(
            self, "_errors"
        ), "You must call `.is_valid()` before calling `.save()`."

        assert (
            not self.errors
        ), "You cannot call `.save()` on a serializer with invalid data."

        # Guard against incorrect use of `serializer.save(commit=False)`
        assert "commit" not in kwargs, (
            "'commit' is not a valid keyword argument to the 'save()' method. "
            "If you need to access data before committing to the database then "
            "inspect 'serializer.validated_data' instead. "
            "You can also pass additional keyword arguments to 'save()' if you "
            "need to set extra attributes on the saved model instance. "
            "For example: 'serializer.save(owner=request.user)'.'"
        )

        assert not hasattr(self, "_data"), (
            "You cannot call `.save()` after accessing `serializer.data`."
            "If you need to access data before committing to the database then "
            "inspect 'serializer.validated_data' instead. "
        )

        if self.instance is not None:
            self.instance = self.update(self.instance, self.validated_data)
            assert (
                self.instance is not None
            ), "`update()` did not return an object instance."
        else:
            self.instance = self.create(self.validated_data)
            assert (
                self.instance is not None
            ), "`create()` did not return an object instance."

        return self.instance
