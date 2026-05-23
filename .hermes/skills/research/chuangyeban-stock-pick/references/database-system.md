# 股票推荐数据库系统

数据库路径：`/root/.hermes/stock_recommendations.db`
管理脚本：`/root/.hermes/scripts/stock_db.py`

---

## 表结构

```sql
CREATE TABLE stock_recommendations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_code TEXT NOT NULL,       -- 股票代码 (300xxx)
    stock_name TEXT NOT NULL,       -- 股票名称
    recommend_date TEXT NOT NULL,   -- 推荐日 (YYYY-MM-DD)
    recommend_price REAL NOT NULL,  -- 推荐日收盘价
    current_date TEXT,              -- 当前日期 (YYYY-MM-DD)
    current_price REAL,             -- 当前股价
    change_pct REAL,                -- 涨幅 (%)
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## 所有命令速查

### 基础查询

```bash
# 列出所有推荐记录（表格形式，涨幅带颜色：红色↑ 绿色↓）
python3 /root/.hermes/scripts/stock_db.py list

# 仅查看今日推荐
python3 /root/.hermes/scripts/stock_db.py list --today

# 查看汇总统计（总推荐次数、胜率、平均涨幅、最佳/最差）
python3 /root/.hermes/scripts/stock_db.py summary
```

### 添加记录

```bash
# 推荐完成后立即录入
python3 /root/.hermes/scripts/stock_db.py add 300476 胜宏科技 2026-05-22 375.50

# 交互式添加
python3 /root/.hermes/scripts/stock_db.py add
```

### 股价更新（核心流程）

```bash
# 【Step 0】列出待更新记录 + 生成搜索词
python3 /root/.hermes/scripts/stock_db.py auto-update

# 【Step 1】web_search 搜索各股票最新价
# 【Step 2】批量写入搜索结果，自动算涨幅
python3 /root/.hermes/scripts/stock_db.py auto-update 300476:388.50 300274:160.20

# 或单只更新
python3 /root/.hermes/scripts/stock_db.py update 300476 388.50

# 交互式更新
python3 /root/.hermes/scripts/stock_db.py update
```

---

## auto-update 双模式工作流

### 模式1：列出 + 生成搜索词（无参数）

```
$ python3 stock_db.py auto-update
============================================================
🚀 数据库自动更新准备
============================================================
📅 当前日期: 2026-05-2X
📋 待更新记录: 3 条

📋 待更新列表:
ID   代码       名称         推荐日          推荐价
1    300476   胜宏科技       2026-05-22   375.50
2    300274   阳光电源       2026-05-22   152.95

🔍 请运行以下web_search命令搜索各股票最新价：
  搜索 "胜宏科技 300476 2026-05-2X 收盘价 股价"
  搜索 "阳光电源 300274 2026-05-2X 收盘价 股价"

📝 找到股价后，运行批量更新:
  python3 stock_db.py auto-update CODE1:PRICE1 CODE2:PRICE2 ...
```

### 模式2：批量写入（带参数）

```
$ python3 stock_db.py auto-update 300476:388.50 300274:160.20
  ✅ 胜宏科技(300476): 推荐价375.50 → 当前价388.50 | 涨幅+3.46%
  ✅ 阳光电源(300274): 推荐价152.95 → 当前价160.20 | 涨幅+4.74%

📊 共更新 2 条记录
```

---

## 显示约定

| 涨幅范围 | 颜色  | 含义 |
|:-------:|:-----:|:----|
| > 0     | 🔴 红色 | 上涨盈利 |
| < 0     | 🟢 绿色 | 下跌亏损 |
| = 0     | ⚫ 默认 | 持平 |
| 待更新  | ⚪ 灰色 | 还未填入当前价 |

---

## 字段说明

| 字段名 | 中文名 | 说明 |
|:------|:------|:----|
| recommend_date | **推荐日** | 你推荐这支股票的日期 |
| recommend_price | **推荐价** | 推荐当日的收盘价 |
| current_date | **当前日期** | 最新更新股价的日期 |
| current_price | **当前价** | 最新更新时的股价 |
| change_pct | **涨幅** | `(当前价 - 推荐价) / 推荐价 × 100%` |

注意：`current_date` 和 `current_price` 是**联动字段**，更新股价时必须同时更新日期。
