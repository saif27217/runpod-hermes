#!/usr/bin/env python3
"""Submit a video generation job to RunPod endpoint cbrzbzlinjhsc0."""
import argparse
import json
import os
import urllib.request
import sys

def main():
    parser = argparse.ArgumentParser(description='Submit RunPod video gen job')
    parser.add_argument('--prompt', required=True, help='Video generation prompt')
    parser.add_argument('--endpoint', default='cbrzbzlinjhsc0')
    parser.add_argument('--key-file', default='/tmp/rp.key')
    args = parser.parse_args()

    with open(args.key_file) as f:
        api_key = f.read().strip()

    url = f"https://api.runpod.ai/v2/{args.endpoint}/run"
    payload = json.dumps({"input": {"prompt": args.prompt}}).encode()

    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        print(f'HTTP {e.code}: {e.read().decode()}', file=sys.stderr)
        sys.exit(1)

    run_id = data.get('id')
    status = data.get('status')
    print(f'Submitted: {run_id}')
    print(f'Status: {status}')

    if status == 'IN_QUEUE' or status == 'IN_PROGRESS':
        print(f'{run_id}')

if __name__ == '__main__':
    main()
