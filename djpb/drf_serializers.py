import typing as T

from django.core.exceptions import ValidationError
from django.db import models
from google.protobuf.json_format import MessageToDict, ParseDict
from rest_framework import serializers
from rest_framework.fields import get_error_detail

from .django_to_proto import django_to_proto
from .proto_to_django import proto_to_django
from .registry import MODEL_TO_PROTO_CLS


def create_drf_serializer(django_model: T.Type[models.Model], *, do_full_clean=True):
    proto_cls = MODEL_TO_PROTO_CLS[django_model]

    class DjangoToProtoDictSerializer(serializers.BaseSerializer):
        def to_representation(self, instance: models.Model):
            proto_obj = proto_cls()
            proto_obj = django_to_proto(instance, proto_obj)
            json = MessageToDict(proto_obj)
            return json

        def to_internal_value(self, data):
            return data

        def create(self, validated_data):
            django_obj = django_model()
            django_obj = proto_to_django(validated_data, django_obj)
            return django_obj

        def update(self, instance, validated_data):
            proto_obj = proto_cls()
            ParseDict(validated_data, proto_obj)

            try:
                instance = proto_to_django(
                    proto_obj, instance, do_full_clean=do_full_clean
                )
            except ValidationError as e:
                raise serializers.ValidationError(get_error_detail(e))

            return instance

    return DjangoToProtoDictSerializer
