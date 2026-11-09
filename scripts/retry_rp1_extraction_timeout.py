#!/usr/bin/env python3
"""One explicit retry per timed-out page; preserve the uncertain first attempt.

Same frozen payload, no failed-page replacement or content-based retry. At most
ten extra requests in the worst case. Called explicitly after the first run ends.
"""
import getpass
import json
import os
from pathlib import Path
import time
import urllib.error
import urllib.request
from validate_rp1_extraction import OUT, ROOT, ENDPOINT, now, verify, write, sha, payload_bytes, NoRedirect


def main():
    requests=verify()
    eligible=[]
    for item in requests:
        prefix=OUT/'api'/item['request_id'];failed=Path(str(prefix)+'.failed.json')
        if Path(str(prefix)+'.completed.json').exists() or not failed.exists():continue
        if json.loads(failed.read_text()).get('exception_class')!='TimeoutError':continue
        assert not Path(str(prefix)+'.response.bin').exists(),'Partial original raw response requires separate handling; do not overwrite'
        if Path(str(prefix)+'.retry.started.json').exists():continue
        eligible.append(item)
    if not eligible:
        print('No eligible timeout retries');return
    write(OUT/'transport_retry.json',dict(authorized_scope='User requested API re-extraction of this fixed small page batch; one explicitly logged transport retry per timeout',
        declared_at=now(),request_ids=[r['request_id'] for r in eligible],maximum_extra_calls=len(eligible),timeout_seconds=600,
        reason='180-second first attempt timed out; no output available; first attempt may have been billed or completed remotely',
        source_prompt_schema_and_selection_changed=False,quality_threshold_changed=False,
        first_attempt_preserved=True,raw_candidate_denominator='All received candidate outputs, never assume unknown timed-out output is zero',
        runner_sha256=sha(Path(__file__))))
    key=os.environ.get('DASHSCOPE_API_KEY','').strip() or getpass.getpass('DASHSCOPE_API_KEY (hidden, memory only): ').strip()
    if not key:raise ValueError('No key; no network calls')
    for item in eligible:
        prefix=OUT/'api'/item['request_id'];started=Path(str(prefix)+'.retry.started.json');raw=Path(str(prefix)+'.response.bin')
        write(started,dict(page_key=item['page_key'],payload_sha256=item['payload_sha256'],started_at=now(),transport_attempt=2))
        begin=time.monotonic();status=None
        try:
            req=urllib.request.Request(ENDPOINT,data=payload_bytes(item['payload']),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json','Connection':'close'},method='POST')
            with urllib.request.build_opener(NoRedirect()).open(req,timeout=600) as response,raw.open('xb') as stream:
                status=response.status
                while True:
                    chunk=response.read(65536)
                    if not chunk:break
                    stream.write(chunk)
            response=json.loads(raw.read_bytes());choice=response['choices'][0];content=json.loads(choice['message']['content'])
            if choice.get('finish_reason')!='stop' or not isinstance(content,dict) or not isinstance(content.get('records'),list) or not isinstance(content.get('contexts'),list):raise ValueError('Incomplete or invalid response')
            write(Path(str(prefix)+'.parsed.json'),content)
            write(Path(str(prefix)+'.completed.json'),dict(payload_sha256=item['payload_sha256'],response_sha256=sha(raw),returned_model=response.get('model'),response_id=response.get('id'),usage=response.get('usage'),finish_reason=choice.get('finish_reason'),records=len(content['records']),contexts=len(content['contexts']),elapsed_seconds=time.monotonic()-begin,http_status=status,transport_attempt=2,first_attempt_uncertain=True))
            print(json.dumps(dict(page_key=item['page_key'],status='retry_archived',records=len(content['records'])),ensure_ascii=False),flush=True)
        except Exception as e:
            if isinstance(e,urllib.error.HTTPError):
                status=e.code
                with raw.open('xb') as stream:stream.write(e.read())
            write(Path(str(prefix)+'.retry.failed.json'),dict(exception_class=type(e).__name__,http_status=status,elapsed_seconds=time.monotonic()-begin,no_further_retry=True))
            print(json.dumps(dict(page_key=item['page_key'],status='retry_failed',exception_class=type(e).__name__)),flush=True)


if __name__=='__main__':main()
