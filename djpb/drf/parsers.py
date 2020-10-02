import msgpack
from msgpack import UnpackException
from rest_framework.exceptions import ParseError
from rest_framework.parsers import BaseParser


class MsgpackParser(BaseParser):
    media_type = "application/msgpack"

    def parse(self, stream, media_type=None, parser_context=None):
        try:
            return msgpack.load(stream)
        except UnpackException as e:
            raise ParseError(f"MessagePack parse error - {e!r}") from e
