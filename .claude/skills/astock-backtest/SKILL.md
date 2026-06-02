---
name: astock-backtest
description: 对打分选股策略做历史回测（walk-forward），输出胜率、平均收益、累计净值、最大回撤、夏普等指标。当用户问"这个策略/打分靠不靠谱、回测一下、历史表现如何、能不能赚钱"时使用。需先采集行情。
---

# A 股策略回测 Skill

对 astock-screen 的打分策略做历史验证：每个交易日买入分数最高的 Top-K 只，
持有 N 天后卖出，计入交易成本，汇总绩效指标。

## 何时使用
- "这套打分历史上有效吗" / "回测一下策略" / "胜率和回撤怎么样"

## 用法

```bash
python .claude/skills/astock-backtest/scripts/run_backtest.py

# 自定义参数
python .claude/skills/astock-backtest/scripts/run_backtest.py --top-k 5 --hold-days 2 --fee 0.0013
```

## 输出指标
- `win_rate`（胜率）、`avg_net_ret`（笔均净收益）、`total_return`（累计收益）
- `max_drawdown`（最大回撤）、`sharpe`（夏普）、`equity_curve`（净值曲线）

## 规则（诚实第一）
- 回测基于历史，**不代表未来**；存在过拟合、幸存者偏差、滑点等局限。
- 若数据来自合成回退（astock-data 输出 fallback=true），回测结果**仅验证流程，
  不具任何参考意义**，agent 必须明确告知用户。
- 若回测显示打分无正向区分度（胜率≈随机、收益≤成本），应如实告诉用户不要据此实盘。
