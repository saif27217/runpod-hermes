#!/usr/bin/env python3
"""Submit image generation job to RunPod SD endpoint."""
import argparse
import json
import urllib.request
import sys

def main():
    parser = argparse.ArgumentParser(description='Submit RunPod SD image gen job')
    parser.add_argument('--prompt', required=True, help='Image generation prompt')
    parser.add_argument('--negative-prompt', default='blurry, bad quality', help='Negative prompt')
    parser.add_argument('--width', type=int, default=512)
    parser.add_argument('--height', type=int, default=512)
    parser.add_argument('--steps', type=int, default=20, help='Inference steps')
    parser.add_argument('--cfg', type=float, default=7.5, help='Guidance scale')
    parser.add_argument('--seed', type=int, default=-1, help='Seed (-1=random)')
    parser.add_argument('--batch', type=int, default=1, help='Batch size')
    parser.add_argument('--endpoint', default='187vrz5cvrrxl6')
    parser.add_argument('--key-file', default='/tmp/rp.key')
    args = parser.parse_args()

    with open(args.key_file) as f:
        api_key = f.read().strip()

    url = f"https://api.runpod.ai/v2/{args.endpoint}/run"
    payload = {
        "input": {
            "prompt": args.prompt,
            "negative_prompt": args.negative_prompt,
            "width": args.width,
            "height": args.height,
            "num_inference_steps": args.steps,
            "guidance_scale": args.cfg,
            "seed": args.seed,
            "batch_size": args.batch,
        }
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        print(f'HTTP {e.code}: {e.read().decode()}', file=sys.stderr)
        sys.exit(1)

    run_id = data.get('id')
    status = data.get('status')
    print(f'Submitted: {run_id}')
    print(f'Status: {status}')
    print(f'{run_id}')

if __name__ == '__main__':
    main()
