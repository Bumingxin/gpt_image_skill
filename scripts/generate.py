import argparse
import base64
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

# ── size constraint rules ──────────────────────────────────────────
# 1. max edge <= 3840px
# 2. width & height must be multiples of 16
# 3. long / short ratio <= 3:1
# 4. total pixels in [655360, 8294400]
SIZE_OPTIONS = [
    'auto',
    '1024x1024',
    '1536x1024',
    '1024x1536',
    '2048x2048',
    '2048x1152',
    '3840x2160',
    '2160x3840',
]

QUALITY_OPTIONS = ['auto', 'low', 'medium', 'high']
FORMAT_OPTIONS = ['png', 'jpeg', 'webp']
BACKGROUND_OPTIONS = ['auto', 'opaque']
MODERATION_OPTIONS = ['auto', 'low']

CONFIG_PATH = Path(__file__).parent.parent / 'config.json'


def load_config():
    if CONFIG_PATH.exists():
        return json.loads(CONFIG_PATH.read_text(encoding='utf-8'))
    return {}


def save_config(config):
    CONFIG_PATH.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding='utf-8')


def ensure_config():
    config = load_config()
    if config.get('base_url') and config.get('token'):
        if not config.get('model'):
            config['model'] = 'gpt-image-2'
            save_config(config)
        return config

    print('首次使用，需要配置 API 信息。', file=sys.stderr)
    base_url = input('请输入 API 地址（如 http://api.aicli.cn/v1）: ').strip()
    token = input('请输入 API Token: ').strip()
    if not base_url or not token:
        print('错误：API 地址和 Token 不能为空', file=sys.stderr)
        sys.exit(1)

    config['base_url'] = base_url.rstrip('/')
    config['token'] = token
    config['model'] = 'gpt-image-2'
    save_config(config)
    print(f'配置已保存到 {CONFIG_PATH}', file=sys.stderr)
    return config


def validate_size(size):
    if size == 'auto':
        return
    m = re.match(r'^(\d+)x(\d+)$', size)
    if not m:
        raise ValueError(f'无效的尺寸格式: {size}，应为 WxH 或 auto')
    w, h = int(m.group(1)), int(m.group(2))
    if w > 3840 or h > 3840:
        raise ValueError(f'边长不能超过3840px，当前: {w}x{h}')
    if w % 16 != 0 or h % 16 != 0:
        raise ValueError(f'宽高必须为16的倍数，当前: {w}x{h}')
    long_side, short_side = max(w, h), min(w, h)
    if short_side > 0 and long_side / short_side > 3:
        raise ValueError(f'长宽比不能超过3:1，当前 {w}x{h} 比值为 {long_side/short_side:.1f}:1')
    total = w * h
    if total < 655360 or total > 8294400:
        raise ValueError(f'总像素须在 655360~8294400 之间，当前 {w}x{h} = {total}')


def validate_n(n):
    if not (1 <= n <= 10):
        raise ValueError(f'图片数量须在 1~10 之间，当前: {n}')


def validate_prompt(prompt):
    if len(prompt) > 1000:
        raise ValueError(f'提示词不能超过1000个字符，当前长度: {len(prompt)}')


def timestamp():
    return datetime.now().strftime('%Y%m%d_%H%M%S')


def resolve_proxies(args, config):
    no_proxy = getattr(args, 'no_proxy', False)
    if no_proxy:
        return {'http': None, 'https': None}
    proxy = getattr(args, 'proxy', None) or config.get('proxy')
    if proxy:
        return {'http': proxy, 'https': proxy}
    return None


def call_generate(args, config):
    validate_prompt(args.prompt)
    validate_size(args.size)
    validate_n(args.n)

    base_url = args.base_url or config['base_url']
    token = args.token or config['token']
    model = getattr(args, 'model', None) or config.get('model', 'gpt-image-2')

    payload = {
        'model': model,
        'prompt': args.prompt,
        'n': args.n,
    }
    if args.size != 'auto':
        payload['size'] = args.size
    if args.quality != 'auto':
        payload['quality'] = args.quality
    if args.background != 'auto':
        payload['background'] = args.background
    if args.moderation != 'auto':
        payload['moderation'] = args.moderation
    payload['format'] = args.format

    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
        'Accept': 'application/json',
    }

    proxies = resolve_proxies(args, config)
    resp = requests.post(
        f'{base_url}/images/generations',
        headers=headers,
        json=payload,
        timeout=300,
        proxies=proxies,
    )
    data = resp.json()

    if not resp.ok:
        return {'success': False, 'error': data, 'status_code': resp.status_code}

    saved = []
    items = data.get('data', [])

    for i, item in enumerate(items):
        b64 = item.get('b64_json', '')
        url = item.get('url', '')

        if b64:
            img_bytes = base64.b64decode(b64)
            ext = args.format
            fname = f'gpt-image-2_{timestamp()}_{i + 1}.{ext}'
            outpath = Path(args.outdir) / fname
            outpath.write_bytes(img_bytes)
            saved.append(str(outpath.resolve()))
        elif url:
            img_resp = requests.get(url, timeout=120, proxies=proxies)
            ext = args.format
            fname = f'gpt-image-2_{timestamp()}_{i + 1}.{ext}'
            outpath = Path(args.outdir) / fname
            outpath.write_bytes(img_resp.content)
            saved.append(str(outpath.resolve()))

    if not saved:
        return {
            'success': True,
            'saved_paths': saved,
            'raw_response': data,
            'warning': '响应中未找到图片数据 (b64_json 或 url)，请检查原始响应',
        }

    return {'success': True, 'saved_paths': saved}


def call_edit(args, config):
    validate_prompt(args.prompt)
    validate_size(args.size)
    if args.n is not None:
        validate_n(args.n)

    base_url = args.base_url or config['base_url']
    token = args.token or config['token']
    model = getattr(args, 'model', None) or config.get('model', 'gpt-image-2')

    files = []
    for img_path in args.image:
        p = Path(img_path)
        if not p.exists():
            raise FileNotFoundError(f'图片文件不存在: {img_path}')
        if p.stat().st_size > 50 * 1024 * 1024:
            raise ValueError(f'图片文件超过50MB: {img_path}')
        files.append(('image', (p.name, p.read_bytes(), 'application/octet-stream')))

    data_fields = {
        'prompt': args.prompt,
        'model': model,
    }
    if args.mask:
        mask_p = Path(args.mask)
        if not mask_p.exists():
            raise FileNotFoundError(f'蒙版文件不存在: {args.mask}')
        files.append(('mask', (mask_p.name, mask_p.read_bytes(), 'image/png')))
    if args.n is not None:
        data_fields['n'] = str(args.n)
    if args.size != 'auto':
        data_fields['size'] = args.size
    if args.quality != 'auto':
        data_fields['quality'] = args.quality
    if args.background != 'auto':
        data_fields['background'] = args.background
    if args.moderation != 'auto':
        data_fields['moderation'] = args.moderation

    headers = {
        'Authorization': f'Bearer {token}',
        'Accept': 'application/json',
    }

    proxies = resolve_proxies(args, config)
    resp = requests.post(
        f'{base_url}/images/edits',
        headers=headers,
        files=files,
        data=data_fields,
        timeout=300,
        proxies=proxies,
    )
    data = resp.json()

    if not resp.ok:
        return {'success': False, 'error': data, 'status_code': resp.status_code}

    saved = []
    items = data.get('data', [])
    if isinstance(items, dict):
        items = [items]

    for i, item in enumerate(items):
        b64 = item.get('b64_json', '')
        url = item.get('url', '')
        if b64:
            img_bytes = base64.b64decode(b64)
            fname = f'gpt-image-2_edit_{timestamp()}_{i + 1}.{args.format}'
            outpath = Path(args.outdir) / fname
            outpath.write_bytes(img_bytes)
            saved.append(str(outpath.resolve()))
        elif url:
            img_resp = requests.get(url, timeout=120, proxies=proxies)
            fname = f'gpt-image-2_edit_{timestamp()}_{i + 1}.{args.format}'
            outpath = Path(args.outdir) / fname
            outpath.write_bytes(img_resp.content)
            saved.append(str(outpath.resolve()))

    if not saved:
        return {
            'success': True,
            'saved_paths': saved,
            'raw_response': data,
            'warning': '响应中未包含图片数据，请检查原始响应',
        }

    return {'success': True, 'saved_paths': saved}


def main():
    parser = argparse.ArgumentParser(description='gpt-image-2 API client')
    sub = parser.add_subparsers(dest='command')

    gen = sub.add_parser('generate', help='文生图')
    gen.add_argument('--token', default=None, help='API Token（可选，优先于配置文件）')
    gen.add_argument('--base-url', default=None, help='API 地址（可选，优先于配置文件）')
    gen.add_argument('--model', default=None, help='模型名称（可选，优先于配置文件）')
    gen.add_argument('--proxy', default=None, help='代理地址，优先于配置文件）')
    gen.add_argument('--no-proxy', action='store_true', help='绕过代理')
    gen.add_argument('--prompt', required=True, help='图片描述文本 (<=1000字符)')
    gen.add_argument('--size', default='auto', choices=SIZE_OPTIONS, help='图片尺寸')
    gen.add_argument('--format', default='png', choices=FORMAT_OPTIONS, help='图片格式')
    gen.add_argument('--quality', default='auto', choices=QUALITY_OPTIONS, help='图片质量')
    gen.add_argument('--background', default='auto', choices=BACKGROUND_OPTIONS, help='背景设置')
    gen.add_argument('--moderation', default='auto', choices=MODERATION_OPTIONS, help='内容审核级别')
    gen.add_argument('--n', type=int, default=1, help='生成数量 (1-10)')
    gen.add_argument('--outdir', default='.', help='输出目录')

    ed = sub.add_parser('edit', help='图片编辑')
    ed.add_argument('--token', default=None, help='API Token（可选，优先于配置文件）')
    ed.add_argument('--base-url', default=None, help='API 地址（可选，优先于配置文件）')
    ed.add_argument('--model', default=None, help='模型名称（可选，优先于配置文件）')
    ed.add_argument('--proxy', default=None, help='代理地址，优先于配置文件）')
    ed.add_argument('--no-proxy', action='store_true', help='绕过代理')
    ed.add_argument('--image', action='append', required=True, help='输入图片路径 (可多次指定)')
    ed.add_argument('--prompt', required=True, help='编辑提示词')
    ed.add_argument('--mask', default=None, help='蒙版图片路径 (PNG)')
    ed.add_argument('--size', default='auto', choices=SIZE_OPTIONS, help='图片尺寸')
    ed.add_argument('--quality', default='auto', choices=QUALITY_OPTIONS, help='图片质量')
    ed.add_argument('--format', default='png', choices=FORMAT_OPTIONS, help='图片格式')
    ed.add_argument('--n', type=int, default=None, help='生成数量 (1-10)')
    ed.add_argument('--background', default='auto', choices=BACKGROUND_OPTIONS, help='背景设置')
    ed.add_argument('--moderation', default='auto', choices=MODERATION_OPTIONS, help='内容审核级别')
    ed.add_argument('--outdir', default='.', help='输出目录')

    cfg = sub.add_parser('config', help='查看或修改配置')
    cfg.add_argument('--show', action='store_true', help='显示当前配置')
    cfg.add_argument('--set-url', default=None, help='设置 API 地址')
    cfg.add_argument('--set-token', default=None, help='设置 API Token')
    cfg.add_argument('--set-model', default=None, help='设置模型名称')
    cfg.add_argument('--set-proxy', default=None, help='设置代理地址')
    cfg.add_argument('--clear-proxy', action='store_true', help='清除代理配置')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == 'config':
        config = load_config()
        if args.set_url or args.set_token or args.set_model or args.set_proxy or args.clear_proxy:
            if args.set_url:
                config['base_url'] = args.set_url.rstrip('/')
            if args.set_token:
                config['token'] = args.set_token
            if args.set_model:
                config['model'] = args.set_model
            if args.clear_proxy:
                config.pop('proxy', None)
            elif args.set_proxy:
                config['proxy'] = args.set_proxy
            save_config(config)
            print(json.dumps({'success': True, 'message': '配置已更新'}, ensure_ascii=False))
        else:
            display = {k: (v if k != 'token' else v[:8] + '...' if len(v) > 8 else v) for k, v in config.items()}
            print(json.dumps(display, indent=2, ensure_ascii=False))
        sys.exit(0)

    config = ensure_config()
    os.makedirs(args.outdir, exist_ok=True)

    try:
        if args.command == 'generate':
            result = call_generate(args, config)
        else:
            result = call_edit(args, config)
    except (ValueError, FileNotFoundError) as e:
        result = {'success': False, 'error': str(e)}

    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if result.get('success') else 1)


if __name__ == '__main__':
    main()
