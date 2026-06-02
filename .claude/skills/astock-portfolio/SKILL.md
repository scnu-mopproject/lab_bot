---
name: astock-portfolio
description: 结合用户实仓（成本价、数量）与候选打分，给出持仓诊断（盈亏、止盈止损建议）和候选建仓的仓位分配，并提示组合风险。当用户问"我的持仓怎么操作、该不该止损止盈、剩余资金买什么、帮我做仓位管理"时使用。
---

# A 股持仓策略 Skill

读取用户持仓与最新价、候选打分，输出：
1. 每只持仓的盈亏与基于风控线的止盈/止损建议；
2. 用可用现金对候选股的建仓建议（按手取整、单票不超上限）；
3. 组合层面的风险提示。

## 何时使用
- "我的持仓现在该怎么操作" / "要不要止损" / "剩下的钱买点什么" / "帮我管仓位"

## 准备工作
复制 `config/positions.example.json` 为 `config/positions.json` 并填入真实持仓
（symbol/cost/qty）。也可用 `--positions` 指定路径。

## 用法

```bash
# 先确保已采集行情、已有候选打分
python .claude/skills/astock-portfolio/scripts/analyze.py

# 指定资金与风控参数
python .claude/skills/astock-portfolio/scripts/analyze.py --capital 200000 --stop-loss 0.07 --take-profit 0.15
```

## 规则
- 所有建议均为**基于规则的风险管理提示，不构成投资建议**，须如实转达用户。
- 仓位建议遵循单票上限、按手取整、不超过可用现金。
- 触及止损线的持仓应在结论中优先、显著提示。
- agent 应结合该股最新基本面/消息面再做判断，不要机械执行规则输出。
