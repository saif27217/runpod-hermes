#!/usr/bin/env python3
"""Check RunPod job status and show output metadata."""
import argparse
import json
import urllib.request
import sys

def main():
    parser = argparse.ArgumentParser(description='Check RunPod job status')
    parser.add_argument('--run-id', required=True, help='RunPod run ID')
    parser.add_argument('--endpoint', default='cbrzbzlinjhsc0')
    parser.add_argument('--key-file', default='/tmp/rp.key')
    args = parser.parse_args()

    with open(args.key_file) as f:
        api_key = f.read().strip()

    url = f"https://api.runpod.ai/v2/{args.endpoint}/status/{args.run_id}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {api_key}"})

    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        print(f'HTTP {e.code}: {e.read().decode()}', file=sys.stderr)
        sys.exit(1)

    print('Status:', data.get('status'))
    print('Worker:', data.get('workerId'))
    print('ID:', data.get('id'))

    output = data.get('output')
    if output is None:
        print('No output yet')
        return

    if isinstance(output, str):
        txt = output
    else:
        txt = json.dumps(output)

    print(f'Output type: {type(txt).__name__}, length: {len(txt)}')

    if len(txt) > 500:
        print('First 500 chars:')
        print(txt[:500])
    else:
        print('Output:')
        print(txt)

if __name__ == '__main__':
    main()
