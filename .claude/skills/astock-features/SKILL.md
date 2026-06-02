---
name: astock-features
description: 基于已采集的行情计算技术特征（均线、量比、MACD、RSI、动量、距高点等）并标注涨停。当用户需要"计算技术指标、做特征工程、准备打分/回测的特征、查看某些股票的技术形态"时使用。需先用 astock-data 采集行情。
---

# A 股特征工程 Skill

读取本地库中的行情，计算一组确定性技术指标，并标注历史涨停，产出特征表，
供 astock-screen 打分与 astock-backtest 回测使用。

## 何时使用
- "算一下这些票的技术指标" / "做特征工程" / "为选股准备特征"
- "看看某只股票现在是什么技术形态"

## 用法

```bash
# 基于库内全部行情构建特征表，输出统计摘要，并存 output/features.csv
python .claude/skills/astock-features/scripts/build_features.py

# 只看某只股票的最新特征快照
python .claude/skills/astock-features/scripts/build_features.py --symbol 600519
```

## 产出的特征（节选）
- `ma5/ma10/ma20`、`ma_bull`（均线多头排列）
- `vol_ratio`（量比）、`rsi14`、`macd/macd_signal/macd_hist`
- `dist_high20`（距20日高点）、`up_streak`（连阳天数）、`amp`（振幅）
- 标注：`limit_up`（当日涨停）、`next_limit_up`、`next_ret`（次日收益，仅供研究/回测）

## 规则
- 指标均为确定性计算，**不含预测**；形态研判由 agent 在快照之上完成。
- `next_*` 列是前瞻标注，**只能用于历史回测**，严禁在实时决策中当作已知信息。
