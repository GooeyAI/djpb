import typing as T

from django.core.exceptions import ValidationError
from django.db import models
from google.protobuf.json_format import MessageToDict, ParseDict
from google.protobuf.message import Message
from rest_framework import serializers
from rest_framework.fields import get_error_detail

from .django_to_proto import django_to_proto
from .proto_to_django import proto_to_django
from .registry import MODEL_TO_PROTO_CLS


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
        obj = self.update(self.Meta.model(), validated_data)
        return obj

    def update(self, instance, validated_data):
        """Update a django `instance` with validated json data"""
        proto_obj = self.proto_cls()
        ParseDict(validated_data, proto_obj)
        return self.from_proto_representation(proto_obj, instance)

    def to_representation(self, instance: models.Model):
        """Convert a django model `instance` to json"""
        proto_obj = self.to_proto_representation(instance)
        json = MessageToDict(proto_obj)
        return json

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
    def proto_cls(self) -> T.Type[Message]:
        return MODEL_TO_PROTO_CLS[self.Meta.model]
