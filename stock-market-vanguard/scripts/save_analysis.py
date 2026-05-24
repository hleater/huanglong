#!/usr/bin/env python3
"""
股市先锋 - 分析历史保存脚本

用于保存每日股票分析结果到历史记录。
"""

import sys
import json
from pathlib import Path
from datetime import datetime

def save_analysis(date_str, data):
    """
    保存分析结果到历史文件
    
    Args:
        date_str: 日期字符串，格式 YYYY-MM-DD
        data: 分析数据字典
    """
    history_dir = Path(__file__).parent.parent / "references" / "history"
    history_dir.mkdir(parents=True, exist_ok=True)
    
    md_file = history_dir / f"{date_str}.md"
    json_file = history_dir / f"{date_str}.json"
    
    # 保存 Markdown 格式
    md_content = f"""# {date_str} 市场分析

## 今日热点
{chr(10).join(f"- 热点{i+1}：{h['板块']} - {h['简评']}" for i, h in enumerate(data.get('热点', [])))}

## 推荐股票
{chr(10).join(f"{i+1}. {s['代码']} {s['名称']} - {s['所属热点']}\n   理由：{s['推荐理由']}" for i, s in enumerate(data.get('推荐股票', [])))}

## 市场情绪
{data.get('市场情绪', '暂无')}

---
分析时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
    
    md_file.write_text(md_content, encoding='utf-8')
    
    # 保存 JSON 格式（便于程序读取）
    json_file.write_text(json.dumps({
        "日期": date_str,
        "分析时间": datetime.now().isoformat(),
        **data
    }, ensure_ascii=False, indent=2), encoding='utf-8')
    
    print(f"✅ 已保存分析结果到 {md_file}")

def load_history(date_str):
    """加载指定日期的分析结果"""
    history_dir = Path(__file__).parent.parent / "references" / "history"
    md_file = history_dir / f"{date_str}.md"
    
    if md_file.exists():
        return md_file.read_text(encoding='utf-8')
    return None

def main():
    if len(sys.argv) < 2:
        print("用法: python save_analysis.py <日期> [JSON数据]")
        print("示例: python save_analysis.py 2026-04-02 '{\"热点\":[],\"推荐股票\":[]}'")
        sys.exit(1)
    
    date_str = sys.argv[1]
    
    if len(sys.argv) > 2:
        data = json.loads(sys.argv[2])
        save_analysis(date_str, data)
    else:
        # 交互式输入
        print(f"📝 为 {date_str} 创建分析记录")
        print("（请手动编辑生成的 Markdown 文件）")
        save_analysis(date_str, {"热点": [], "推荐股票": [], "市场情绪": ""})

if __name__ == "__main__":
    main()
