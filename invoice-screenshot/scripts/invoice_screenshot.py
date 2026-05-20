#!/usr/bin/env python3
"""
电子发票截图工具 — Extract 价税合计 amount from PDF invoices and save screenshots.

Usage:
    python3 invoice_screenshot.py <invoice.pdf>
    python3 invoice_screenshot.py <directory>     # batch process
    python3 invoice_screenshot.py <invoice.pdf> --output ./screenshots/
    python3 invoice_screenshot.py <invoice.pdf> --dpi 200 --all
"""

import argparse
import os
import re
import subprocess
import sys
import glob
import json


# ======================== 金额提取 ========================


def amount_to_float(amount_str: str) -> str:
    """Clean and normalize an amount string to float format like '1234.56'."""
    # Remove currency symbols and spaces
    s = amount_str.strip()
    s = s.replace(",", "")
    s = s.replace("￥", "").replace("¥", "").replace("$", "")
    s = s.strip()
    try:
        f = float(s)
        # Format to 2 decimal places, strip trailing zeros
        formatted = f"{f:.2f}"
        if formatted.endswith(".00"):
            formatted = formatted[:-3]
        return formatted
    except ValueError:
        return None


def extract_amount_from_text(text: str) -> str:
    """
    Extract 价税合计 amount from invoice text.
    Returns the amount as a clean string like '1234.56', or None.
    """
    # Remove page breaks and normalize whitespace
    text = text.replace("\f", "\n")

    # Pattern 1: 价税合计 followed by amount on same or next line
    # Use atomic group to prevent regex backtracking:
    # A number pattern that captures full comma-formatted amounts (e.g. 1,234.56)
    # without letting \d+ match only a partial fragment.
    # (?>...|...) is an atomic group — once matched, the engine can't backtrack
    # into it. We provide two alternatives: one with comma-thousands and one
    # without.
    # Atomic group prevents regex backtracking into the number.
    # Outer (...) captures the full amount for group(1).
    AMT = r"((?>(?:\d{1,3}(?:,\d{3})*|\d+)\.\d{2}))"

    patterns = [
        # "价税合计（大写）...（小写）¥1,234.56"
        rf"价税合计.*?小写[）)]?\s*[￥¥]?\s*{AMT}",
        rf"价税合计.*?小写[：:]\s*[￥¥]?\s*{AMT}",
        # "价税合计：¥1,234.56"
        rf"价税合计[：:]\s*[￥¥]?\s*{AMT}",
        # "价税合计 1,234.56"
        rf"价税合计\s+[￥¥]?\s*{AMT}",
        # "合计（大写）...（小写）¥1,234.56"
        rf"合计.*?小写[）)]?\s*[￥¥]?\s*{AMT}",
        rf"合计.*?小写[：:]\s*[￥¥]?\s*{AMT}",
        # "合计：¥1,234.56"
        rf"合计[：:]\s*[￥¥]?\s*{AMT}",
        # "价税合计" on one line, amount on next line
        rf"价税合计[：:\s]*\n\s*[￥¥]?\s*{AMT}",
        # "（小写）¥1,234.56" near "价税合计"
        rf"价税合计[\s\S]{{0,50}}小写[\s\S]{{0,20}}[￥¥]?\s*{AMT}",
        # Raw number right after 价税合计 (no ¥, no 小写)
        rf"价税合计\s*{AMT}",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            amount = amount_to_float(match.group(1))
            if amount:
                return amount

    # Pattern 2: Look for standalone "价税合计" then scan nearby for numbers
    idx = text.find("价税合计")
    if idx >= 0:
        # Search in a window around 价税合计
        window = text[max(0, idx):idx + 300]
        # Find all potential amounts in this window (atomic groups to prevent fragmentation)
        number_matches = re.findall(r"[￥¥]?\s*((?>(?:\d{1,3}(?:,\d{3})*|\d+)\.\d{2}))", window)
        if number_matches:
            # Last number is usually the 价税合计 (follows 大写 + 小写)
            amount = amount_to_float(number_matches[-1])
            if amount:
                return amount

    # Pattern 3: Look for "合计" with amount
    idx = text.find("合计")
    if idx >= 0:
        window = text[max(0, idx):idx + 200]
        number_matches = re.findall(r"[￥¥]?\s*((?>(?:\d{1,3}(?:,\d{3})*|\d+)\.\d{2}))", window)
        if number_matches:
            amount = amount_to_float(number_matches[-1])
            if amount:
                return amount

    return None


# ======================== PDF 转截图 ========================


def pdf_to_png(pdf_path: str, output_dir: str, dpi: int = 300, all_pages: bool = False) -> list[str]:
    """
    Convert PDF page(s) to PNG using pdftocairo.
    Returns list of generated PNG file paths.
    """
    os.makedirs(output_dir, exist_ok=True)

    # Generate a unique prefix based on the input filename
    base = os.path.splitext(os.path.basename(pdf_path))[0]
    # Clean filename for safe filesystem
    base = re.sub(r'[^\w\-_. ]', '_', base)

    output_prefix = os.path.join(output_dir, base)
    cmd = ["pdftocairo", "-png", "-r", str(dpi), pdf_path, output_prefix]

    if not all_pages:
        cmd.insert(2, "-singlefile")  # Only first page

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        print(f"  ERROR: pdftocairo failed: {result.stderr.strip()}", file=sys.stderr)
        return []

    # Find generated files
    png_prefix = output_prefix
    generated = []
    for f in sorted(os.listdir(output_dir)):
        fpath = os.path.join(output_dir, f)
        if f.startswith(base) and f.endswith(".png"):
            generated.append(fpath)

    return generated


def rename_png_with_amount(png_paths: list[str], amount: str, output_dir: str) -> list[str]:
    """
    Rename PNG files with the extracted amount.
    Returns list of renamed file paths.
    """
    result = []
    for i, png_path in enumerate(png_paths):
        ext = "_价税合计_" + amount + ".png"
        if i > 0:
            ext = f"_价税合计_{amount}_p{i+1}.png"

        new_path = os.path.join(output_dir, ext)
        # Handle filename conflicts
        counter = 1
        while os.path.exists(new_path):
            new_path = os.path.join(output_dir, f"_价税合计_{amount}_{counter}.png")
            counter += 1

        os.rename(png_path, new_path)
        result.append(new_path)

    return result


# ======================== 主流程 ========================


def process_single_pdf(pdf_path: str, output_dir: str = None, dpi: int = 300, all_pages: bool = False) -> dict:
    """Process a single invoice PDF and return results."""
    pdf_path = os.path.abspath(pdf_path)
    basename = os.path.basename(pdf_path)

    if not os.path.exists(pdf_path):
        return {"file": basename, "status": "error", "message": "文件不存在"}

    if not pdf_path.lower().endswith(".pdf"):
        return {"file": basename, "status": "skipped", "message": "不是PDF文件"}

    print(f"\n📄 处理: {basename}")

    # Step 1: Extract text
    try:
        result = subprocess.run(
            ["pdftotext", "-layout", "-nopgbrk", pdf_path, "-"],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            return {"file": basename, "status": "error", "message": f"pdftotext失败: {result.stderr.strip()}"}
        text = result.stdout
    except subprocess.TimeoutExpired:
        return {"file": basename, "status": "error", "message": "pdftotext超时"}
    except FileNotFoundError:
        return {"file": basename, "status": "error", "message": "未找到pdftotext，请安装poppler-utils"}

    if not text.strip():
        print("  ⚠️  提示: 未提取到文字，可能是扫描件PDF。截图仍会生成但无法自动命名。")

    # Step 2: Extract amount
    amount = extract_amount_from_text(text) if text.strip() else None
    if amount:
        print(f"  ✅ 识别到价税合计: {amount}")
    else:
        print(f"  ⚠️  未识别到价税合计金额，将使用原文件名")

    # Step 3: Determine output dir
    if output_dir is None:
        output_dir = os.path.dirname(pdf_path) or "."

    # Step 4: Convert to PNG
    png_files = pdf_to_png(pdf_path, output_dir, dpi, all_pages)
    if not png_files:
        return {"file": basename, "status": "error", "message": "PDF转PNG失败"}

    print(f"  📸 生成截图: {len(png_files)} 张")

    # Step 5: Rename with amount
    if amount:
        renamed = rename_png_with_amount(png_files, amount, output_dir)
        for r in renamed:
            print(f"  ✅ 截图: {r}")
        return {"file": basename, "status": "success", "amount": amount, "outputs": renamed}
    else:
        print(f"  ⚠️  截图保持原名: {png_files[0]}")
        return {"file": basename, "status": "partial", "outputs": png_files}


def main():
    parser = argparse.ArgumentParser(
        description="电子发票截图工具 — 识别价税合计并截图命名",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python3 invoice_screenshot.py ~/发票/2024年发票.pdf
  python3 invoice_screenshot.py ~/发票/          # 批量处理
  python3 invoice_screenshot.py invoice.pdf --output ./截图/
  python3 invoice_screenshot.py invoice.pdf --dpi 200
  python3 invoice_screenshot.py invoice.pdf --all  # 多页截图
        """
    )
    parser.add_argument("input", help="PDF文件路径或包含PDF的目录")
    parser.add_argument("--output", "-o", help="输出目录（默认与PDF同目录）")
    parser.add_argument("--dpi", type=int, default=300, help="截图分辨率（默认300）")
    parser.add_argument("--all", action="store_true", help="截图所有页面（默认仅第一页）")
    parser.add_argument("--json", action="store_true", help="以JSON格式输出结果")

    args = parser.parse_args()

    # Collect PDF files
    input_path = args.input
    if os.path.isdir(input_path):
        pdf_files = sorted(glob.glob(os.path.join(input_path, "*.pdf")))
        if not pdf_files:
            print(f"❌ 目录中未找到PDF文件: {input_path}")
            sys.exit(1)
        print(f"📁 找到 {len(pdf_files)} 个PDF文件")
    elif os.path.isfile(input_path):
        pdf_files = [input_path]
    else:
        print(f"❌ 文件或目录不存在: {input_path}")
        sys.exit(1)

    # Check dependencies
    for cmd in ["pdftotext", "pdftocairo"]:
        if not subprocess.run(["which", cmd], capture_output=True).returncode == 0:
            print(f"❌ 缺少依赖: {cmd}。请安装: sudo apt-get install poppler-utils")
            sys.exit(1)

    # Process each
    results = []
    for pdf_file in pdf_files:
        result = process_single_pdf(pdf_file, args.output, args.dpi, args.all)
        results.append(result)

    # Summary
    success = [r for r in results if r["status"] == "success"]
    partial = [r for r in results if r["status"] == "partial"]
    errors = [r for r in results if r["status"] == "error"]
    skipped = [r for r in results if r["status"] == "skipped"]

    print(f"\n{'='*40}")
    print(f"处理完成: 成功{len(success)} | 部分{len(partial)} | 失败{len(errors)} | 跳过{len(skipped)}")

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
