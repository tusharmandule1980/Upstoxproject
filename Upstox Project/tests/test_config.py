import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from config import DEFAULT_REDIRECT_URI, parse_keys  # noqa: E402


def test_labelled():
    k = parse_keys("API_KEY=abc\nAPI_SECRET = def\nREDIRECT_URI=http://127.0.0.1:5000/callback")
    assert k["API_KEY"] == "abc" and k["API_SECRET"] == "def"


def test_plain_lines_and_default_redirect():
    k = parse_keys("abc\ndef\n")
    assert (k["API_KEY"], k["API_SECRET"], k["REDIRECT_URI"]) == ("abc", "def", DEFAULT_REDIRECT_URI)


def test_colon_label():
    assert parse_keys("api key: abc")["API_KEY"] == "abc"
