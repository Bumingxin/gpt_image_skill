---
name: gpt-image-2
description: Use when user wants to generate or edit images using gpt-image-2 model via OpenAI-compatible API. Triggers on "generate image", "create picture", "文生图", "画一张", "生成图片", or any image generation request.
---

# gpt-image-2 图片生成与编辑

对接 OpenAI 兼容 API，通过交互式问答引导用户选择参数，完成文生图或图片编辑。

## 前置步骤：配置确认

首次使用时，脚本会引导用户输入 API 地址和 Token 并保存到 `config.json`。后续使用自动读取，无需重复输入。

如需查看或修改配置：

```bash
python "{skill_path}/scripts/generate.py" config --show
python "{skill_path}/scripts/generate.py" config --set-url "http://新的地址/v1"
python "{skill_path}/scripts/generate.py" config --set-token "新的token"
```

---

## 流程一：文生图

按以下顺序逐一询问，每轮只问一个问题：

### Q1: 提示词（必填）

请描述您想要生成的图片内容（不超过1000个字符）。

### Q2: 图片数量 n

选项：
- 1 张（推荐）
- 2 张
- 4 张
- 10 张

### Q3: 图片尺寸 size

选项：
- auto 自动（推荐）
- 1024x1024 正方形
- 1536x1024 横版
- 1024x1536 竖版
- 2048x2048 2K正方形
- 2048x1152 2K横版
- 3840x2160 4K横版
- 2160x3840 4K竖版

### Q4: 图片质量 quality

选项：
- auto 自动（推荐）
- low 低质量（速度最快）
- medium 中等
- high 高质量

### Q5: 图片格式 format

选项：
- png（推荐）
- jpeg
- webp

### 收集完毕后

汇总所有参数展示给用户确认，确认无误后调用脚本：

```bash
python "{skill_path}/scripts/generate.py" generate \
  --prompt "<提示词>" \
  --n <数量> \
  --size <尺寸> \
  --quality <质量> \
  --format <格式> \
  --outdir ./
```

执行后解析 stdout 中的 JSON。成功时告知用户保存路径；失败时展示错误信息并引导重试。

---

## 流程二：图片编辑

按以下顺序逐一询问：

### Q1: 输入图片（必填）

请提供要编辑的图片文件路径（最多16张，每张不超过50MB）。

### Q2: 编辑提示词（必填）

请描述您期望的编辑效果。

### Q3: 蒙版图片 mask（可选）

- 不使用蒙版（推荐）
- 提供蒙版PNG文件路径

### Q4: 图片数量 n

选项同文生图。

### Q5-Q8: 尺寸、质量、背景、审核

选项同文生图流程。

### 收集完毕后

```bash
python "{skill_path}/scripts/generate.py" edit \
  --image <图片路径1> --image <图片路径2> \
  --prompt "<提示词>" \
  [--mask <蒙版路径>] \
  [--n <数量>] \
  --size <尺寸> \
  --quality <质量> \
  --outdir ./
```

---

## 错误处理

- 参数校验失败：告知用户具体原因，引导修改后重新调用
- API 返回错误：展示错误详情，建议调整参数或稍后重试
- 网络超时：提示用户检查网络后重试

## 输出结果

成功生成后向用户报告：
- 生成了几张图片
- 每张图片的保存路径
