"""image.embed effect — local file → data URL, http URL pass-through."""
import base64
import tempfile
from pathlib import Path

from ail.parser.parser import parse
from ail.runtime import Executor, MockAdapter


def _run(src: str) -> str:
    program = parse(src)
    ex = Executor(program, MockAdapter())
    return ex.run_entry({"_": ""}).value


def test_image_embed_http_url_passthrough():
    out = _run('''
entry main(_: Text) {
    md = perform image.embed("https://example.com/pic.png", "hi")
    return md
}
''')
    assert out == "![hi](https://example.com/pic.png)"


def test_image_embed_local_file_inlines_as_data_url():
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tf:
        tf.write(b"\x89PNG\r\n\x1a\n" + b"x" * 32)
        path = tf.name
    try:
        out = _run(f'''
entry main(_: Text) {{
    md = perform image.embed("{path}", "local")
    return md
}}
''')
        assert out.startswith("![local](data:image/png;base64,")
        # Round-trip the base64 to confirm bytes survived
        b64 = out.split("base64,", 1)[1].rstrip(")")
        assert base64.b64decode(b64).startswith(b"\x89PNG")
    finally:
        Path(path).unlink()


def test_image_embed_missing_file_returns_error_result():
    out = _run('''
entry main(_: Text) {
    r = perform image.embed("/no/such/file.png", "x")
    if is_error(r) {
        return "ERR"
    }
    return "OK"
}
''')
    assert out == "ERR"


def test_image_embed_default_alt():
    out = _run('''
entry main(_: Text) {
    md = perform image.embed("https://x.test/a.png")
    return md
}
''')
    assert out == "![image](https://x.test/a.png)"


def test_image_embed_alt_with_brackets_sanitized():
    out = _run('''
entry main(_: Text) {
    md = perform image.embed("https://x.test/a.png", "alt [1] x")
    return md
}
''')
    # ] chars stripped to keep markdown bracket pair intact
    assert "![alt  1  x](https://x.test/a.png)" == out
