# GPT-Image-2 图片生成与编辑工具

对接 OpenAI 兼容 API，支持文生图和图片编辑功能。

## 快速开始

### 1. 安装依赖

```bash
pip install requests
```

### 2. 配置 API

首次使用会自动引导配置，或手动设置：

```bash
python scripts/generate.py config --set-url "http://你的API地址/v1"
python scripts/generate.py config --set-token "你的API Token"
```

查看当前配置：

```bash
python scripts/generate.py config --show
```

## 使用方法

### 文生图

```bash
python scripts/generate.py generate \
  --prompt "一只可爱的猫咪在阳光下打盹" \
  --n 1 \
  --size 1024x1024 \
  --quality auto \
  --format png \
  --outdir ./
```

### 图片编辑

```bash
python scripts/generate.py edit \
  --image input.png \
  --prompt "把背景改成海滩" \
  --n 1 \
  --size auto \
  --quality auto \
  --outdir ./
```

支持多图编辑：

```bash
python scripts/generate.py edit \
  --image img1.png \
  --image img2.png \
  --prompt "将两张图融合" \
  --outdir ./
```

## 参数说明

| 参数 | 说明 | 可选值 |
|------|------|--------|
| `--prompt` | 提示词（必填） | 最多1000字符 |
| `--n` | 生成数量 | 1-10 |
| `--size` | 图片尺寸 | auto, 1024x1024, 1536x1024, 1024x1536, 2048x2048, 2048x1152, 3840x2160, 2160x3840 |
| `--quality` | 图片质量 | auto, low, medium, high |
| `--format` | 输出格式 | png, jpeg, webp |
| `--background` | 背景设置（仅edit） | auto, opaque |
| `--moderation` | 内容审核（仅edit） | auto, low |
| `--mask` | 蒙版路径（仅edit） | PNG 文件路径 |

## 配置管理

```bash
# 查看配置
python scripts/generate.py config --show

# 修改 API 地址
python scripts/generate.py config --set-url "http://新地址/v1"

# 修改 Token
python scripts/generate.py config --set-token "新Token"

# 修改模型
python scripts/generate.py config --set-model "模型名称"

# 设置代理
python scripts/generate.py config --set-proxy "http://代理:端口"

# 清除代理
python scripts/generate.py config --clear-proxy
```

## 注意事项

- API Token 保存在 `config.json` 中，已加入 `.gitignore`
- 图片边长最大 3840px，必须为 16 的倍数
- 长宽比不能超过 3:1
- 编辑模式下单张图片不超过 50MB
