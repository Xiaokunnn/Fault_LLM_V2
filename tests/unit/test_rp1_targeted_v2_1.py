"""No real model calls: test preservation and billing boundaries with temporary fixtures."""
import importlib.util
import json
from pathlib import Path
import shutil

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('rp1_targeted_v21', ROOT / 'scripts/run_rp1_targeted_v2_1.py')
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


@pytest.fixture
def package(tmp_path):
    relative = MODULE.PACKAGE.relative_to(ROOT)
    target = tmp_path / relative
    freeze = json.loads((MODULE.PACKAGE / 'request_freeze.json').read_text())
    for name in list(freeze['sha256']) + [str(relative / 'request_freeze.json')]:
        dest = tmp_path / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, dest)
    return target, tmp_path


def response(model='mock-only-model', finish='stop'):
    return json.dumps({'model': model, 'choices': [{'finish_reason': finish, 'message': {'content': json.dumps({'assertions': [], 'auxiliary': [], 'unresolved': []})}}]}).encode()


class MockResponse:
    status = 200

    def __init__(self, data):
        self.data = data

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, _):
        data, self.data = self.data, b''
        return data


class Opener:
    def __init__(self, raw):
        self.raw = raw
        self.calls = 0

    def open(self, *args, **kwargs):
        self.calls += 1
        return MockResponse(self.raw)


def test_tampered_prompt_stops_before_network(package, monkeypatch):
    path, root = package
    request_file = path / 'requests.jsonl'
    request_file.write_text(request_file.read_text().replace('Extract the page directly', 'Altered instruction'))
    monkeypatch.setenv('DASHSCOPE_API_KEY', 'unit-test-key-not-real')
    opener = Opener(response())
    monkeypatch.setattr(MODULE.urllib.request, 'build_opener', lambda *a: opener)
    with pytest.raises(ValueError, match='Frozen dependency mismatch'):
        MODULE.execute(path, root)
    assert opener.calls == 0
    assert not (path / 'api_run_001').exists()


def test_missing_credential_creates_no_run_or_network(package, monkeypatch):
    path, root = package
    monkeypatch.delenv('DASHSCOPE_API_KEY', raising=False)
    opener = Opener(response())
    monkeypatch.setattr(MODULE.urllib.request, 'build_opener', lambda *a: opener)
    result = MODULE.execute(path, root)
    assert result['network_calls_this_invocation'] == 0
    assert result['status'] == 'blocked_missing_api_key'
    assert opener.calls == 0
    assert not (path / 'api_run_001').exists()


def test_successful_resume_does_not_repeat_paid_calls(package, monkeypatch):
    path, root = package
    monkeypatch.setenv('DASHSCOPE_API_KEY', 'unit-test-key-not-real')
    opener = Opener(response())
    monkeypatch.setattr(MODULE.urllib.request, 'build_opener', lambda *a: opener)
    first = MODULE.execute(path, root)
    second = MODULE.execute(path, root)
    assert opener.calls == 12
    assert first['network_calls_this_invocation'] == 12
    assert second['network_calls_this_invocation'] == 0
    assert len(list((path / 'api_run_001').glob('*.response.bin'))) == 12
    assert first['automatic_qualified_records'] == 0
    assert first['formal_metrics'] == 'not_computed'
    assert all(b'unit-test-key-not-real' not in x.read_bytes() for x in (path / 'api_run_001').iterdir())


def test_truncated_response_preserved_and_never_retried(package, monkeypatch):
    path, root = package
    monkeypatch.setenv('DASHSCOPE_API_KEY', 'unit-test-key-not-real')
    raw = response(finish='length')
    opener = Opener(raw)
    monkeypatch.setattr(MODULE.urllib.request, 'build_opener', lambda *a: opener)
    with pytest.raises(RuntimeError, match='archived'):
        MODULE.execute(path, root)
    assert opener.calls == 1
    assert next((path / 'api_run_001').glob('*.response.bin')).read_bytes() == raw
    with pytest.raises(ValueError, match='uncertain/failed attempt'):
        MODULE.execute(path, root)
    assert opener.calls == 1


def test_interrupted_attempt_is_not_automatically_repeated(package, monkeypatch):
    path, root = package
    run = path / 'api_run_001'
    run.mkdir()
    item = MODULE.read_rows(path / 'requests.jsonl')[0]
    MODULE.write_new(run / (item['request_id'] + '.started.json'), {'payload_sha256': item['payload_sha256']})
    monkeypatch.setenv('DASHSCOPE_API_KEY', 'unit-test-key-not-real')
    opener = Opener(response())
    monkeypatch.setattr(MODULE.urllib.request, 'build_opener', lambda *a: opener)
    with pytest.raises(ValueError, match='uncertain/failed attempt'):
        MODULE.execute(path, root)
    assert opener.calls == 0


def test_returned_model_mismatch_is_not_a_matched_experiment():
    with pytest.raises(ValueError, match='returned model'):
        MODULE.parse_response(response('different-mock-model'), 'first-mock-model')


def test_no_redirect_forwards_provider_authorization():
    assert MODULE.NoRedirect().redirect_request(None, None, 302, '', {}, 'https://other.invalid') is None
