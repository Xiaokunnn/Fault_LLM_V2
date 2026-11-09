#!/usr/bin/env python3
"""Run the frozen twelve-request RP1 development pilot, preserving every response.

Default is read-only verification. --execute requires the named environment key.
No retries, model substitution, graph publication, or accuracy/recall calculation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / 'results/experiments/research_point_1/adjudication_targeted_v2_1'


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def payload_bytes(value: dict) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()


def read_rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines()]


def write_new(path: Path, value: dict) -> None:
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def check_package(package: Path = PACKAGE, root: Path = ROOT) -> tuple[dict, list[dict]]:
    freeze = json.loads((package / 'request_freeze.json').read_text())
    for required in ['requests.jsonl', 'experiment_protocol.json', 'pilot_sources.jsonl', 'page_reference_v2_1.jsonl']:
        if str((package / required).relative_to(root)) not in freeze['sha256']:
            raise ValueError(f'Missing required frozen dependency: {required}')
    for name, expected in freeze['sha256'].items():
        target = (root / name).resolve()
        if not target.is_relative_to(root.resolve()) or digest(target.read_bytes()) != expected:
            raise ValueError(f'Frozen dependency mismatch: {name}')
    protocol = json.loads((package / 'experiment_protocol.json').read_text())
    requests = read_rows(package / 'requests.jsonl')
    if len(requests) != 12 or len({x['request_id'] for x in requests}) != 12:
        raise ValueError('Expected exactly twelve unique requests')
    pages = {x['page_key']: x for x in read_rows(package / 'pilot_sources.jsonl')}
    if len(pages) != 6:
        raise ValueError('Expected six source pages')
    for key, page in pages.items():
        if digest(page['page_text'].encode()) != page['page_text_sha256']:
            raise ValueError(f'Source page hash mismatch: {key}')
        paired = [x for x in requests if x['page_key'] == key]
        if len(paired) != 2 or {x['arm'] for x in paired} != {'E0', 'E1'}:
            raise ValueError(f'Missing paired arm: {key}')
        if paired[0]['payload']['messages'][1] != paired[1]['payload']['messages'][1]:
            raise ValueError('Paired arms must have identical input')
    for item in requests:
        if digest(payload_bytes(item['payload'])) != item['payload_sha256']:
            raise ValueError('Request payload hash mismatch')
        if item['page_key'] not in pages or item['source_page_sha256'] != pages[item['page_key']]['page_text_sha256']:
            raise ValueError('Request/source mismatch')
        if digest(item['payload']['messages'][1]['content'].encode()) != item['shared_input_sha256']:
            raise ValueError('Shared input hash mismatch')
    if protocol['base_url'] != 'https://dashscope.aliyuncs.com/compatible-mode/v1':
        raise ValueError('Unexpected provider URL; freeze a new protocol to change provider')
    return protocol, requests


def parse_response(raw: bytes, expected_model: str | None = None) -> tuple[dict, dict]:
    response = json.loads(raw)
    choice = response['choices'][0]
    if choice.get('finish_reason') != 'stop':
        raise ValueError('Non-stop finish reason; preserve raw response, do not repair or retry')
    model = response.get('model')
    if not isinstance(model, str) or not model or (expected_model is not None and model != expected_model):
        raise ValueError('Missing or changed returned model identity')
    content = json.loads(choice['message']['content'])
    if not isinstance(content, dict) or any(not isinstance(content.get(k), list) for k in ['assertions', 'auxiliary', 'unresolved']):
        raise ValueError('Output must contain the three declared arrays')
    # Format readiness only; semantic source support must be separately reviewed.
    required = {'head_surface', 'head_type', 'relation', 'tail_surface', 'tail_type', 'conditions', 'modality', 'polarity', 'scope', 'applicability', 'evidence_text', 'evidence_unit_ids'}
    for item in content['assertions']:
        if not isinstance(item, dict) or not required <= item.keys():
            raise ValueError('Incomplete assertion output')
        if not isinstance(item['conditions'], list) or not isinstance(item['evidence_unit_ids'], list):
            raise ValueError('Conditions and evidence_unit_ids must be arrays')
    metadata = {'returned_model': model, 'provider_response_id': response.get('id'), 'usage': response.get('usage'), 'finish_reason': choice['finish_reason'], 'assertion_count': len(content['assertions']), 'semantic_review': 'pending', 'automatic_qualification': False}
    return content, metadata


def request_state(run: Path, item: dict) -> dict | None:
    start = run / (item['request_id'] + '.started.json')
    done = run / (item['request_id'] + '.completed.json')
    if done.exists():
        record = json.loads(done.read_text())
        raw_path = run / (item['request_id'] + '.response.bin')
        if not start.exists() or record['payload_sha256'] != item['payload_sha256'] or digest(raw_path.read_bytes()) != record['response_sha256']:
            raise ValueError('Completed request/cache identity mismatch')
        content, meta = parse_response(raw_path.read_bytes(), record['returned_model'])
        parsed = run / (item['request_id'] + '.parsed.json')
        if json.loads(parsed.read_text()) != content:
            raise ValueError('Parsed response no longer matches raw response')
        if json.loads(start.read_text())['payload_sha256'] != item['payload_sha256']:
            raise ValueError('Started request identity mismatch')
        return meta
    if start.exists() or any(run.glob(item['request_id'] + '.*')):
        raise ValueError(f'{item["request_id"]}: prior uncertain/failed attempt; no automatic billable retry')
    return None


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def execute(package: Path = PACKAGE, root: Path = ROOT) -> dict:
    protocol, requests = check_package(package, root)
    key = os.environ.get(protocol['api_key_env'], '').strip()
    if not key:
        return {'status': 'blocked_missing_api_key', 'api_key_env': protocol['api_key_env'], 'network_calls_this_invocation': 0}
    run = package / 'api_run_001'
    run.mkdir(exist_ok=True)
    freeze_hash = digest((package / 'request_freeze.json').read_bytes())
    manifest = run / 'run_manifest.json'
    if manifest.exists():
        if json.loads(manifest.read_text())['request_freeze_sha256'] != freeze_hash:
            raise ValueError('Run belongs to a different request freeze')
    else:
        write_new(manifest, {'request_freeze_sha256': freeze_hash, 'started_at_unix': time.time(), 'api_key_persisted': False, 'maximum_requests': 12})
    returned_model = None
    completed = 0
    network_calls = 0
    opener = urllib.request.build_opener(NoRedirect())
    for item in requests:
        state = request_state(run, item)
        if state is not None:
            if returned_model is not None and returned_model != state['returned_model']:
                raise ValueError('Different models in saved paired run')
            returned_model = state['returned_model']
            completed += 1
            continue
        # Exclusive file creation precedes the network call; an interrupted attempt is never retried silently.
        write_new(run / (item['request_id'] + '.started.json'), {'payload_sha256': item['payload_sha256'], 'page_key': item['page_key'], 'arm': item['arm'], 'started_at_unix': time.time()})
        started = time.monotonic()
        raw_path = run / (item['request_id'] + '.response.bin')
        http_status = None
        try:
            request = urllib.request.Request(protocol['base_url'] + '/chat/completions', data=payload_bytes(item['payload']), headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json', 'Connection': 'close'}, method='POST')
            network_calls += 1
            # Stream raw bytes into an exclusive research record, including partial responses on interruption.
            with opener.open(request, timeout=protocol['timeout_seconds']) as response, raw_path.open('xb') as stream:
                http_status = response.status
                while True:
                    chunk = response.read(65536)
                    if not chunk:
                        break
                    stream.write(chunk)
            raw = raw_path.read_bytes()
            content, meta = parse_response(raw, returned_model)
            write_new(run / (item['request_id'] + '.parsed.json'), content)
            write_new(run / (item['request_id'] + '.completed.json'), {**meta, 'payload_sha256': item['payload_sha256'], 'response_sha256': digest(raw), 'http_status': http_status, 'elapsed_seconds': time.monotonic()-started})
            returned_model = meta['returned_model']
            completed += 1
            print(json.dumps({'request_id': item['request_id'], 'status': 'archived', 'assertions': meta['assertion_count']}, ensure_ascii=False), flush=True)
        except Exception as error:
            if isinstance(error, urllib.error.HTTPError):
                http_status = error.code
                with raw_path.open('xb') as stream:
                    stream.write(error.read())
            # Do not log exception strings, credentials, request headers or environment contents.
            write_new(run / (item['request_id'] + '.failed.json'), {'exception_class': type(error).__name__, 'http_status': http_status, 'elapsed_seconds': time.monotonic()-started, 'resume_policy': 'stop_no_automatic_retry'})
            raise RuntimeError(f'{item["request_id"]}: response/error archived; stopped without retry ({type(error).__name__})') from None
    return {'status': 'extraction_completed_review_pending', 'completed_requests': completed, 'network_calls_this_invocation': network_calls, 'returned_model': returned_model, 'formal_metrics': 'not_computed', 'automatic_qualified_records': 0}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    if args.execute:
        result = execute()
    else:
        protocol, requests = check_package()
        result = {'status': 'verified_without_network', 'requests': len(requests), 'pages': protocol['pages'], 'api_key_present': bool(os.environ.get(protocol['api_key_env'], '').strip()), 'api_key_env': protocol['api_key_env']}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 2 if result['status'] == 'blocked_missing_api_key' else 0


if __name__ == '__main__':
    raise SystemExit(main())
