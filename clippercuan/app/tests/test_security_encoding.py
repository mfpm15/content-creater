import json
from urllib.parse import quote

from clipper import security


def test_encoded_credentials_are_redacted_in_errors_and_logs(monkeypatch):
    value='quoted"\\example-secret'
    monkeypatch.setenv('LLM_API_KEY',value)
    for encoded in (value,quote(value,safe=''),json.dumps(value)[1:-1]):
        assert encoded not in security.redact('Provider failed: '+encoded)
    assert security.redact('https://example.org/?%74oken=private&title=example')=='https://example.org/?%74oken=[REDACTED]&title=example'
    assert security.redact('Basic dXNlcjpwYXNz')=='Basic [REDACTED]'

    assert security.redact('basic training')=='basic training'
