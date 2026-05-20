---
name: invoice-screenshot
description: Open PDF electronic invoices, extract the 价税合计 amount, screenshot the invoice body, and save PNG files named by the amount.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [invoice, PDF, screenshot, finance, 发票]
---

# 电子发票截图技能

## Overview
对 PDF 格式的电子发票进行截图，自动识别发票中的 **价税合计（价税合计）** 金额，
并以该金额命名截图文件。支持批量处理多个发票文件。

## Requirements
- `poppler-utils` — 提供 `pdftotext`（文字提取）和 `pdftocairo`（PDF 转 PNG）
- Python3（系统自带即可，无需额外包）

确保已安装：
```bash
sudo apt-get install -y poppler-utils
```

## Usage

### 单张发票截图
```bash
python3 ~/.hermes/skills/productivity/invoice-screenshot/scripts/invoice_screenshot.py <发票PDF路径>
```
输出：与该 PDF 同目录下生成 `价税合计_1234.56.png`

### 批量处理目录下所有发票
```bash
python3 ~/.hermes/skills/productivity/invoice-screenshot/scripts/invoice_screenshot.py <目录路径>
```
自动扫描目录下所有 `.pdf` 文件并逐个处理。

### 自定义输出目录
```bash
python3 ~/.hermes/skills/productivity/invoice-screenshot/scripts/invoice_screenshot.py <发票PDF路径> --output ./截图/
```

### 指定 DPI（默认 300）
```bash
python3 ~/.hermes/skills/productivity/invoice-screenshot/scripts/invoice_screenshot.py <发票PDF路径> --dpi 200
```

## How It Works

1. **`pdftotext -layout`** 提取 PDF 文字（保留原始布局，适合中文发票）
2. **正则匹配** 价税合计后面的阿拉伯数字金额（支持 `¥1,234.56`、`1234.56` 等格式）
3. **`pdftocairo -png`** 将 PDF 页面转为高分辨率 PNG
4. **重命名** 截图文件为 `价税合计_1234.56.png`

## Common Pitfalls

- **扫描件发票**：此技能针对 **电子发票（PDF 中包含可提取文字）**。扫描件（图片式 PDF）需先用 OCR 工具（见 `ocr-and-documents` 技能）转文字后再截图。
- **多页发票**：目前默认只截图第一页。如需多页，可使用 `--all` 参数。
- **金额格式**：支持价税合计后跟 `¥1,234.56`、`1,234.56`、`¥1234.56` 等格式。如未匹配到，会回退为文件原名。
- **Windows 上传文件名乱码**：从 Windows 上传的电子发票，中文文件名常出现 `?` 乱码（例如 `�?00出行-12.67...pdf`）。这是 GBK→UTF-8 转换截断导致。见 `references/filename-encoding-fix.md` 恢复方法。
- **PDF 加密**：不支持加密/密码保护的 PDF。

## Example Output
```
输入: ~/发票/2024年1月-电子发票-ABC科技有限公司.pdf
输出: ~/发票/价税合计_1234.56.png
```

## Related Reference
- `references/filename-encoding-fix.md` — How to fix garbled Chinese filenames when transferring from Windows (GBK/UTF-8 encoding corruption). Common issue when invoice PDFs come from Windows machines.

## Verification Checklist
- [ ] 截图文件正确显示发票正文内容
- [ ] 文件名包含正确的价税合计金额
- [ ] 截图清晰可读（300 DPI 以上）
