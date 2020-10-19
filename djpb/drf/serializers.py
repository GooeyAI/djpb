from django.core.exceptions import ValidationError
from rest_framework import serializers
from rest_framework.fields import get_error_detail

from ..django_to_proto import django_to_proto
from ..proto_to_django import proto_to_django
from ..registry import MODEL_TO_PROTO_CLS
from ..stubs import DjModelType, ProtoMsgType, DjModel, ProtoMsg


class ProtobufSerializer(serializers.BaseSerializer):
    model: DjModelType
    proto_cls: ProtoMsgType = None
    do_full_clean: bool = True

    @staticmethod
    def for_model(
        model: DjModelType,
        *,
        proto_cls: ProtoMsgType = None,
        do_full_clean: bool = True,
    ):
        class ProtobufSerializerForModel(ProtobufSerializer):
            pass

        ProtobufSerializerForModel.model = model
        ProtobufSerializerForModel.proto_cls = proto_cls
        ProtobufSerializerForModel.do_full_clean = do_full_clean

        return ProtobufSerializerForModel

    def to_internal_value(self, data):
        return data

    def create(self, validated_data: bytes) -> DjModel:
        return self.update(self.model(), validated_data)

    def update(self, instance: DjModel, validated_data: bytes) -> DjModel:
        proto_cls = self.get_proto_cls()
        proto_obj = proto_cls.FromString(validated_data)
        return self._from_proto(proto_obj, instance)

    def _from_proto(self, proto_obj: ProtoMsg, instance: DjModel) -> DjModel:
        try:
            return proto_to_django(
                proto_obj, instance, do_full_clean=self.do_full_clean,
            )
        except ValidationError as e:
            raise serializers.ValidationError(get_error_detail(e))

    def to_representation(self, instance: DjModel) -> bytes:
        proto_obj = self._to_proto(instance)
        return proto_obj.SerializeToString()

    def _to_proto(self, instance: DjModel) -> ProtoMsg:
        proto_cls = self.get_proto_cls()
        proto_obj = proto_cls()
        proto_obj = django_to_proto(instance, proto_obj)
        return proto_obj

    def get_proto_cls(self) -> ProtoMsgType:
        if self.proto_cls:
            return self.proto_cls
        try:
            return MODEL_TO_PROTO_CLS[self.model][0]
        except IndexError:
            raise ValueError(
                f"Please specify at least one protobuf class for the model {self.model.__qualname__!r}."
            )

    #
    # Mostly copy-pasted from the parent class,
    # except a few changes to allow protobuf types to work nicely
    #
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
