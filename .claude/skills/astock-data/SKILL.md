---
name: astock-data
description: 采集 A 股行情与财经新闻并落库。当用户需要"拉取/更新/采集股票数据、历史K线、行情、财经新闻、快讯"，或需要为后续选股/分析准备数据时使用。基于 AKShare，无网络时自动回退到合成数据以保证流程可跑通。
---

# A 股数据采集 Skill

封装确定性的数据采集脚本（基于 AKShare），把行情与新闻落入本地 SQLite，
供 features / screen / backtest / portfolio 等环节复用。

## 何时使用
- "更新一下今天的行情数据" / "拉取沪深300成分股近一年K线"
- "采集最新财经新闻" / "准备选股需要的数据"

## 用法

脚本：`scripts/fetch.py`，从项目根目录运行（建议使用项目虚拟环境 `.venv`）。

```bash
# 更新股票池行情（默认读 config/config.yaml 的 universe 设置）
python .claude/skills/astock-data/scripts/fetch.py prices

# 采集财经新闻
python .claude/skills/astock-data/scripts/fetch.py news

# 一次性更新行情 + 新闻
python .claude/skills/astock-data/scripts/fetch.py all

# 指定股票与回看天数
python .claude/skills/astock-data/scripts/fetch.py prices --symbols 600519,000001 --days 120
```

脚本以 JSON 输出采集摘要（写入条数、股票数、数据源是否为回退等），并把数据
写入 `output/lab_bot.db`。

## 规则
- 优先真实数据；接口失败且配置 `data.allow_fallback=true` 时回退到合成数据，
  输出中 `fallback=true` 会明确标注，agent 据此判断结论可信度。
- 不做任何分析或预测，只负责"可靠地拿到干净数据"。
- 全市场（universe.mode=all）数据量大、耗时长，默认使用指数成分股。
