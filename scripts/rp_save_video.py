#!/usr/bin/env python3
"""Download base64 video from a completed RunPod run and save as MP4."""
import argparse
import json
import base64
import urllib.request
import sys

def main():
    parser = argparse.ArgumentParser(description='Save RunPod video output')
    parser.add_argument('--run-id', required=True, help='RunPod run ID')
    parser.add_argument('--endpoint', default='cbrzbzlinjhsc0')
    parser.add_argument('--key-file', default='/tmp/rp.key')
    parser.add_argument('--output', default='/tmp/runpod_video.mp4')
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

    if data.get('status') != 'COMPLETED':
        print(f'Job not completed yet: {data.get("status")}', file=sys.stderr)
        sys.exit(2)

    output = data.get('output')
    if not output:
        print('No output field', file=sys.stderr)
        sys.exit(3)

    # Output is typically a JSON string with base64 video inside
    if isinstance(output, str):
        try:
            outer = json.loads(output)
        except json.JSONDecodeError:
            outer = {"raw": output}
    else:
        outer = output

    video_b64 = outer.get('video')
    if not video_b64:
        # Try to find any base64 blob in keys
        for k, v in outer.items():
            if isinstance(v, str) and len(v) > 100000:
                video_b64 = v
                break
        if not video_b64:
            print(f'No video found. Keys: {list(outer.keys())[:10]}', file=sys.stderr)
            sys.exit(4)

    video_bytes = base64.b64decode(video_b64)
    with open(args.output, 'wb') as f:
        f.write(video_bytes)

    print(f'Wrote {len(video_bytes)} bytes to {args.output}')
    print(f'Header: {video_bytes[:12]}')

if __name__ == '__main__':
    main()
