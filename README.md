# lab_bot —— A 股量化研究 / 决策支持智能体

一个面向 A 股市场的自动化研究工具，采用 **Claude Code Skill + Agent** 架构：
确定性的 Python 脚本封装成 Skill，负责"可靠地拿数据、算指标、做回测"；
真正的多维研判、选股推理、复盘由 agent（Claude）在脚本输出之上完成，
过程**透明可解释**。

> ⚠️ **重要声明**
> 没有任何模型能可靠预测涨停。本项目是**量化研究与决策支持工具**，不是稳赚的
> 套利机器。所有打分、候选、建议均为研究参考，**不构成投资建议**。
> 市场有风险，决策与风险由使用者自行承担。

## 设计理念：为什么是 Skill + Agent

把"智能"和"确定性"分开：

| 层 | 负责 | 实现 |
|----|------|------|
| **Skill（确定性）** | 拉行情/新闻、算技术指标、规则打分、回测、仓位计算 | `lab_bot/` 共享库 + `.claude/skills/*/scripts/` |
| **Agent（智能）** | 编排 skill、结合新闻题材/资金/大盘做研判、解释理由、复盘 | Claude 运行时推理 |

这样底层结果可复现、可审计，而判断不被"黑箱模型"伪装成精确概率。

## 五个 Skill

| Skill | 作用 |
|-------|------|
| `astock-data` | 采集行情与财经新闻并落库（AKShare，失败自动回退合成数据） |
| `astock-features` | 计算技术指标（均线/量比/MACD/RSI/动量/距高点）与涨停标注 |
| `astock-screen` | 对当日快照透明打分（0-100），输出 Top-K 候选及分项明细 |
| `astock-backtest` | 对打分策略做 walk-forward 历史回测，输出胜率/回撤/夏普 |
| `astock-portfolio` | 结合实仓给出止盈止损、建仓仓位与组合风险提示 |

每个 skill 是 `.claude/skills/<name>/`，含 `SKILL.md`（激活说明）+ `scripts/`。
agent 会根据你的自然语言请求自动激活相应 skill。

## 快速开始

```bash
# 1. 安装依赖（建议虚拟环境）
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt

# 2. 跑通整条链（无网络时自动用合成数据，流程照常可跑）
python .claude/skills/astock-data/scripts/fetch.py all          # 采集
python .claude/skills/astock-features/scripts/build_features.py # 特征
python .claude/skills/astock-screen/scripts/score.py --top-k 10 # 选股打分
python .claude/skills/astock-backtest/scripts/run_backtest.py   # 回测验证
python .claude/skills/astock-portfolio/scripts/analyze.py       # 持仓策略
```

或者直接对 Claude 说："**帮我更新今天的行情，选出 10 只技术面最强的票并回测一下**"，
agent 会自动编排上述 skill 并给出有保留的研判。

## 配置

- `config/config.yaml`：数据源、股票池、特征/模型/回测/风控参数、报告输出。
- `config/positions.example.json`：持仓示例。复制为 `config/positions.json` 填入
  真实持仓（已在 `.gitignore` 中，不会被提交）。

数据源失败时若 `data.allow_fallback=true`，会回退到**合成数据**并在输出里以
`data_quality: synthetic` / `fallback: true` 明确标注——此时结论仅验证流程、
无参考意义，agent 会如实告知。

## 项目结构

```
lab_bot/
├── .claude/skills/          # 五个 Agent Skill（SKILL.md + scripts/）
├── lab_bot/                 # 共享确定性库
│   ├── config.py            # 配置加载
│   ├── pipeline.py          # 跨 skill 复用的流水线辅助
│   ├── data/                # 采集(market/news/mock) + 存储(storage)
│   ├── features/            # 技术指标 + 涨停标注
│   ├── screen/              # 规则打分
│   ├── backtest/            # 回测引擎
│   ├── portfolio/           # 持仓策略与风控
│   └── report/              # Markdown 报告
├── config/                  # 配置与持仓示例
├── tests/                   # 端到端测试（合成数据，离线可跑）
└── requirements.txt
```

## 测试

```bash
. .venv/bin/activate && python -m pytest tests/ -q
```

## 路线图（后续可扩展）

- 接入 Tushare/问财作为可选数据源；新闻情绪/题材热度量化
- 定时调度（APScheduler / cron），收盘后自动跑链并产出报告
- 消息机器人推送（Telegram / 企业微信 / 钉钉）
- 更严谨的回测（滑点、涨停买不进、停牌处理、分层检验）
