#!/usr/bin/env python3
"""
股票推荐数据库管理工具
数据库: /root/.hermes/stock_recommendations.db

用法:
  python3 stock_db.py list                          # 列出所有推荐记录
  python3 stock_db.py list --today                  # 列出今日推荐
  python3 stock_db.py add <code> <name> <date> <price>    # 快速添加推荐
  python3 stock_db.py add                           # 交互式添加
  python3 stock_db.py update <code> <price>         # 更新指定股价
  python3 stock_db.py update                        # 交互式更新
  python3 stock_db.py auto-update                   # 🚀 自动: 列出待更新+生成搜索词
  python3 stock_db.py auto-update <code>:<price> [<code2>:<price2> ...]  # 批量写入搜索结果
  python3 stock_db.py summary                       # 查看汇总统计
  python3 stock_db.py stats                         # 同summary
"""

import sqlite3
import sys
import os
import re
from datetime import datetime

DB_PATH = '/root/.hermes/stock_recommendations.db'

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS stock_recommendations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stock_code TEXT NOT NULL,
            stock_name TEXT NOT NULL,
            recommend_date TEXT NOT NULL,
            recommend_price REAL NOT NULL,
            current_date TEXT,
            current_price REAL,
            change_pct REAL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_stock_code_date 
        ON stock_recommendations(stock_code, recommend_date)
    ''')
    conn.commit()
    conn.close()

def list_records(today_only=False):
    conn = get_conn()
    cursor = conn.cursor()
    
    if today_only:
        today = datetime.now().strftime('%Y-%m-%d')
        cursor.execute('''
            SELECT * FROM stock_recommendations 
            WHERE recommend_date = ? 
            ORDER BY id
        ''', (today,))
    else:
        cursor.execute('''
            SELECT * FROM stock_recommendations 
            ORDER BY recommend_date DESC, id
        ''')
    
    rows = cursor.fetchall()
    
    if not rows:
        print("📭 暂无推荐记录")
        conn.close()
        return
    
    header = f"{'ID':<4} {'代码':<8} {'名称':<10} {'推荐日':<12} {'推荐价':<10} {'当前日':<12} {'当前价':<10} {'涨幅':<8}  {'状态':<6}"
    print(f"\n{header}")
    print("="*88)
    for r in rows:
        change = r['change_pct']
        change_str = f"{change:+.2f}%" if change is not None else "待更新"
        cur_price = f"{r['current_price']:.2f}" if r['current_price'] else "待更新"
        cur_date = r['current_date'] if r['current_date'] else "待更新"
        
        # 状态标记
        today = datetime.now().strftime('%Y-%m-%d')
        if r['current_date'] == today:
            status = "✅今日"
        elif r['current_price'] is not None:
            status = "📅旧日"
        else:
            status = "⏳待更"
        
        print(f"{r['id']:<4} {r['stock_code']:<8} {r['stock_name']:<10} {r['recommend_date']:<12} {r['recommend_price']:<10.2f} {cur_date:<12} {cur_price:<10} {change_str:<8}  {status:<6}")
    
    conn.close()

def add_record(code, name, date, price):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO stock_recommendations 
        (stock_code, stock_name, recommend_date, recommend_price)
        VALUES (?, ?, ?, ?)
    ''', (code, name, date, price))
    conn.commit()
    print(f"✅ 已添加: {name}({code}) | {date} | 推荐价: {price}元")
    conn.close()

def update_prices(code=None, price=None):
    """更新当前股价并自动计算涨幅"""
    conn = get_conn()
    cursor = conn.cursor()
    today = datetime.now().strftime('%Y-%m-%d')
    
    if code and price:
        # 更新指定股票（所有该代码的末更新记录）
        cursor.execute('''
            UPDATE stock_recommendations 
            SET current_date = ?, current_price = ?,
                change_pct = ROUND((? - recommend_price) / recommend_price * 100, 2),
                updated_at = CURRENT_TIMESTAMP
            WHERE stock_code = ? AND (current_price IS NULL OR current_date != ?)
        ''', (today, price, price, code, today))
        count = cursor.rowcount
        conn.commit()
        if count > 0:
            print(f"✅ 已更新 {code}({count}条) 当前价: {price}元 (日期: {today})")
        else:
            print(f"⚠️ 未找到 {code} 的待更新记录")
        conn.close()
        return
    
    # 交互式更新
    cursor.execute('''
        SELECT * FROM stock_recommendations 
        WHERE current_price IS NULL OR current_date != ?
        ORDER BY recommend_date DESC
    ''', (today,))
    rows = cursor.fetchall()
    
    if not rows:
        print("📭 所有记录均已更新")
        conn.close()
        return
    
    print("🔍 以下记录需要更新当前价:")
    for r in rows:
        print(f"  [{r['id']}] {r['stock_name']}({r['stock_code']}) | 推荐日: {r['recommend_date']} | 推荐价: {r['recommend_price']}")
        try:
            new_price = float(input(f"  输入当前价 (留空跳过): ").strip())
            if new_price > 0:
                change = round((new_price - r['recommend_price']) / r['recommend_price'] * 100, 2)
                cursor.execute('''
                    UPDATE stock_recommendations 
                    SET current_date = ?, current_price = ?, change_pct = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (today, new_price, change, r['id']))
                print(f"  ✅ 已更新 → 当前价: {new_price}元 | 涨幅: {change:+.2f}%")
            else:
                print(f"  ⏭️ 跳过")
        except (ValueError, EOFError):
            print(f"  ⏭️ 跳过")
    
    conn.commit()
    conn.close()


def auto_update(batch_data=None):
    """
    auto-update 模式（供Hermes Agent使用）:
    
    模式1: auto-update（无参数）
      列出所有待更新记录，并输出web_search查询建议
      Agent据此搜索各股票最新价
      
    模式2: auto-update <code>:<price> [<code2>:<price2> ...]
      批量写入搜索结果到数据库
    """
    conn = get_conn()
    cursor = conn.cursor()
    today = datetime.now().strftime('%Y-%m-%d')
    
    if batch_data:
        # 模式2: 批量写入搜索结果
        updated_count = 0
        for item in batch_data:
            if ':' not in item:
                print(f"⚠️ 跳过无效格式: {item} (应为 code:price)")
                continue
            parts = item.split(':')
            code = parts[0].strip()
            try:
                price = float(parts[1].strip())
            except ValueError:
                print(f"⚠️ 跳过无效价格: {item}")
                continue
            
            cursor.execute('''
                SELECT * FROM stock_recommendations 
                WHERE stock_code = ? AND (current_price IS NULL OR current_date != ?)
            ''', (code, today))
            rows = cursor.fetchall()
            
            for r in rows:
                change = round((price - r['recommend_price']) / r['recommend_price'] * 100, 2)
                cursor.execute('''
                    UPDATE stock_recommendations 
                    SET current_date = ?, current_price = ?, change_pct = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (today, price, change, r['id']))
                print(f"  ✅ {r['stock_name']}({code}): 推荐价{r['recommend_price']} → 当前价{price} | 涨幅{change:+.2f}%")
                updated_count += 1
        
        conn.commit()
        print(f"\n📊 共更新 {updated_count} 条记录")
        conn.close()
        return
    
    # 模式1: 列出待更新 + 生成搜索建议
    cursor.execute('''
        SELECT * FROM stock_recommendations 
        WHERE current_price IS NULL OR current_date != ?
        ORDER BY recommend_date DESC
    ''', (today,))
    rows = cursor.fetchall()
    
    if not rows:
        print("✅ 所有推荐记录均已有今日最新数据，无需更新！")
        conn.close()
        return
    
    print("=" * 60)
    print("🚀 数据库自动更新准备")
    print("=" * 60)
    print(f"📅 当前日期: {today}")
    print(f"📋 待更新记录: {len(rows)} 条")
    print()
    
    print("📋 待更新列表:")
    print(f"{'ID':<4} {'代码':<8} {'名称':<10} {'推荐日':<12} {'推荐价':<10}")
    print("-"*50)
    for r in rows:
        print(f"{r['id']:<4} {r['stock_code']:<8} {r['stock_name']:<10} {r['recommend_date']:<12} {r['recommend_price']:<10.2f}")
    
    print()
    print("🔍 请运行以下web_search命令搜索各股票最新价：")
    print()
    for r in rows:
        print(f"  搜索 \"{r['stock_name']} {r['stock_code']} {today} 收盘价 股价\"")
    print()
    print("📝 找到股价后，运行批量更新:")
    print(f"  python3 {__file__} auto-update CODE1:PRICE1 CODE2:PRICE2 ...")
    print()
    print("💡 示例:")
    print(f"  python3 {__file__} auto-update 300476:388.50 300274:160.20 300124:82.60")
    
    conn.close()


def summary():
    conn = get_conn()
    cursor = conn.cursor()
    
    # 统计概览
    cursor.execute('SELECT COUNT(*) as total FROM stock_recommendations')
    total = cursor.fetchone()['total']
    
    cursor.execute('SELECT COUNT(*) as updated FROM stock_recommendations WHERE current_price IS NOT NULL')
    updated = cursor.fetchone()['updated']
    
    cursor.execute('''
        SELECT COUNT(*) as positive FROM stock_recommendations 
        WHERE change_pct IS NOT NULL AND change_pct > 0
    ''')
    positive = cursor.fetchone()['positive']
    
    cursor.execute('''
        SELECT COUNT(*) as negative FROM stock_recommendations 
        WHERE change_pct IS NOT NULL AND change_pct < 0
    ''')
    negative = cursor.fetchone()['negative']
    
    cursor.execute('''
        SELECT AVG(change_pct) as avg_return FROM stock_recommendations 
        WHERE change_pct IS NOT NULL
    ''')
    avg_row = cursor.fetchone()
    avg_return = avg_row['avg_return'] if avg_row['avg_return'] else 0
    
    cursor.execute('''
        SELECT stock_name, stock_code, change_pct FROM stock_recommendations 
        WHERE change_pct IS NOT NULL 
        ORDER BY change_pct DESC LIMIT 1
    ''')
    best = cursor.fetchone()
    
    cursor.execute('''
        SELECT stock_name, stock_code, change_pct FROM stock_recommendations 
        WHERE change_pct IS NOT NULL 
        ORDER BY change_pct ASC LIMIT 1
    ''')
    worst = cursor.fetchone()
    
    print("\n" + "="*50)
    print("📊 股票推荐数据库统计")
    print("="*50)
    print(f"  总推荐次数: {total}")
    print(f"  已更新涨幅: {updated}")
    if updated > 0:
        print(f"  ✅ 上涨: {positive} | ❌ 下跌: {negative} | 🟰 零: {updated - positive - negative}")
        win_rate = round(positive / updated * 100, 1) if updated > 0 else 0
        print(f"  📈 胜率: {win_rate}%")
        print(f"  📉 平均涨幅: {avg_return:+.2f}%")
    if best:
        print(f"  🏆 最佳: {best['stock_name']}({best['stock_code']}) {best['change_pct']:+.2f}%")
    if worst:
        print(f"  💀 最差: {worst['stock_name']}({worst['stock_code']}) {worst['change_pct']:+.2f}%")
    print("="*50)
    
    # 按推荐日分组统计
    print("\n📅 按推荐日统计:")
    cursor.execute('''
        SELECT recommend_date, COUNT(*) as cnt,
               ROUND(AVG(CASE WHEN change_pct IS NOT NULL THEN change_pct END), 2) as avg_chg
        FROM stock_recommendations 
        GROUP BY recommend_date
        ORDER BY recommend_date DESC
    ''')
    rows = cursor.fetchall()
    print(f"{'推荐日':<12} {'数量':<6} {'平均涨幅':<10}")
    print("-"*30)
    for r in rows:
        avg = f"{r['avg_chg']:+.2f}%" if r['avg_chg'] else "待更新"
        print(f"{r['recommend_date']:<12} {r['cnt']:<6} {avg:<10}")
    
    conn.close()

def interactive_add():
    print("\n➕ 添加新推荐 (输入空值退出)")
    try:
        code = input("  股票代码: ").strip()
        if not code: return
        name = input("  股票名称: ").strip()
        if not name: return
        date = input(f"  推荐日 [{datetime.now().strftime('%Y-%m-%d')}]: ").strip()
        if not date:
            date = datetime.now().strftime('%Y-%m-%d')
        price_str = input("  推荐价: ").strip()
        price = float(price_str)
        add_record(code, name, date, price)
    except (ValueError, EOFError):
        print("❌ 输入无效")

if __name__ == '__main__':
    init_db()
    
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)
    
    action = sys.argv[1]
    
    if action == 'list':
        today_only = '--today' in sys.argv
        list_records(today_only)
    elif action == 'add':
        if len(sys.argv) >= 6:
            add_record(sys.argv[2], sys.argv[3], sys.argv[4], float(sys.argv[5]))
        else:
            interactive_add()
    elif action == 'update':
        if len(sys.argv) >= 4:
            update_prices(sys.argv[2], float(sys.argv[3]))
        else:
            update_prices()
    elif action in ('auto-update', 'autoupdate'):
        if len(sys.argv) >= 3:
            # auto-update code:price code2:price2 ...
            auto_update(sys.argv[2:])
        else:
            auto_update()
    elif action == 'summary':
        summary()
    elif action == 'stats':
        summary()
    else:
        print(f"❌ 未知操作: {action}")
        print(__doc__)
