# AGENTS.md

## Cursor Cloud specific instructions

### 项目概览
- 仓库探索"外贸(跨境出口)辅助工具"。已落地一个 Python 最小闭环多 Agent 原型
  (包 `ftagents`,src 布局):**选品 + 合规 + 利润测算**,由 Orchestrator 串成流水线。
- 业务分析/方案讨论记录在 `docs/`(索引 `docs/README.md`)。

### 环境与运行(标准命令见 README,不赘述)
- 开发在 **虚拟环境 `.venv`** 中进行:`. .venv/bin/activate`。启动时的 update script 已负责
  创建 `.venv` 并 `pip install -e ".[dev]"`(仅当 `pyproject.toml` 存在时执行)。
- 运行时**无第三方依赖**(纯标准库);`pytest` 是唯一开发依赖。
- 两种入口:CLI(`python -m ftagents.cli`)与 Web(`python -m ftagents.server`,默认
  `127.0.0.1:8000`,单页 UI + `/api/analyze`)。二者共享同一套 orchestrator 逻辑。
- **Web 服务读取环境变量 LLM key**:若用 tmux 起服务,注意 tmux server 只继承"首个客户端"的
  环境。要让 `/api/categories` 显示 `llm.available=true`,需在已带 `DEEPSEEK_API_KEY` 的 shell 里
  (必要时先 `tmux kill-server`)重新创建 tmux 会话,或直接在带 key 的 shell 里前台/后台启动。
- 系统依赖:`python3.12-venv`(创建 venv 所需)。已在环境中安装;若未来 pod 缺失,
  需 `apt-get install -y python3.12-venv` 后再建 venv。它**不应**进 update script(系统依赖)。

### 非显而易见的注意事项
- **LLM 是可选增强,不是硬依赖**:未配置 API key 时,`ftagents.llm.LLMClient.available` 为 False,
  摘要自动降级为模板,整个闭环仍完整跑通。因此**无需 secret 也能开发和测试**。
  配置 `DEEPSEEK_API_KEY`(或 `FTAGENTS_LLM_API_KEY`/`OPENAI_API_KEY`)后自动走 LLM。
- **护栏原则**:合规红黄绿灯与利润公式是**确定性**的(在 `agents/compliance.py`、`agents/profit.py`),
  LLM 不参与核心判定。改逻辑要改这两处的规则/公式,并同步更新 `tests/`。
- `data/*.json` 是**演示用示例数据**,不是真实数据源。真实接入时替换为选品 API、合规规则库、实时费率。
- 结论阈值(利润红线 10%、健康线 20%、红海竞争 0.8)集中在 `orchestrator.py` 顶部常量。
