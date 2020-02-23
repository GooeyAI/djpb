from django.core.management.base import BaseCommand

from djpb.gen_proto import gen_proto_for_models
from djpb.registry import MODEL_TO_PROTO_CLS


class Command(BaseCommand):
    help = "Generate protobuf file for all registered models."

    def handle(self, *args, **options):
        print(gen_proto_for_models(MODEL_TO_PROTO_CLS.keys()))
