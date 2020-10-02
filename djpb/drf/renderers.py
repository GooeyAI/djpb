import msgpack
from rest_framework.renderers import BaseRenderer


class MsgpackRenderer(BaseRenderer):
    media_type = "application/msgpack"
    format = "msgpack"
    render_style = "binary"
    charset = None

    def render(self, data, media_type=None, renderer_context=None):
        return msgpack.packb(data, use_bin_type=True)
