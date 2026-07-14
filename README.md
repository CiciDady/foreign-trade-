# foreign-trade-

外贸(跨境出口)辅助工具的探索仓库。当前落地了一个**最小闭环多 Agent 原型**
(方案 C):输入品类 → 输出「能不能做 + 落地利润 + 合规待办」。

- 业务分析与方案讨论记录见 [`docs/`](./docs/)(索引:[`docs/README.md`](./docs/README.md))。
- 本原型对应方案 C,详见 [`docs/三方案操作步骤.md`](./docs/三方案操作步骤.md)。

## 原型:选品 + 合规 + 利润测算

三个专职 Agent 由 Orchestrator 串成流水线,核心决策(合规红黄绿灯、利润公式)
用**确定性规则**兜底,LLM 仅做可选的自然语言摘要增强。

```
选品 Agent  →  (人工/默认)定案  →  合规 Agent + 利润测算 Agent  →  综合结论 + 摘要
```

### 快速开始

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"

# 列出示例品类
python -m ftagents.cli --list-categories

# 跑一次分析
python -m ftagents.cli --category "silicone kitchen utensils" --market US --budget 5000

# JSON 输出 / 交互式人工定案
python -m ftagents.cli -c "yoga mat" -m EU --json
python -m ftagents.cli -c "bluetooth earbuds" --interactive
```

### Web 界面(交互验证)

```bash
python -m ftagents.server --host 127.0.0.1 --port 8000
# 或安装后:ftagents-web --port 8000
```

浏览器打开 http://127.0.0.1:8000,顶部为全局参数(市场/预算/汇率/是否用 LLM),下面三个 Tab:

1. **选品分析**:输入品类 → 从示例数据源选出机会最高的候选并给结论。
2. **手动测算**:手动填真实商品参数(供货价/重量/售价/月销/竞争度 + 电池·利器等属性、侵权风险),
   直接算落地利润与合规——用于把真实询价立刻套进来测算。
3. **批量对比**:多选品类一次性对比,输出按机会分排序的表格(色标结论 + 利润/ROI/合规),
   点某一行可下钻查看完整报告。

结果卡片右上角支持**导出**:单个报告导 JSON / Markdown,批量对比导 CSV。

**实时汇率**:页面加载时自动获取实时人民币汇率(免费源 open.er-api.com,失败降级 7.2),
`汇率` 字段旁标注来源;CLI 不加 `--cny-per-usd` 时同样自动取实时汇率。

接口:
- `GET  /api/categories` 返回示例品类 + LLM 是否可用
- `GET  /api/fx` 返回实时汇率 `{cny_per_usd, source, live}`(失败降级)
- `POST /api/analyze` 入参 `{category, market, budget, cny_per_usd, use_llm}`;
  传入可选 `product` 对象即进入**手动测算**模式(跳过选品数据源);`cny_per_usd` 省略时用实时汇率。
- `POST /api/compare` 入参 `{categories:[...], market, budget, cny_per_usd, use_llm}`,返回排序后的对比数组。

### 接入 LLM(可选,DeepSeek 兼容)

不配置 key 时自动降级为模板摘要,闭环照常运行。配置后自动增强:

```bash
export DEEPSEEK_API_KEY=sk-xxx          # 或 FTAGENTS_LLM_API_KEY / OPENAI_API_KEY
# 可选:export FTAGENTS_LLM_BASE_URL=https://api.deepseek.com/v1
# 可选:export FTAGENTS_LLM_MODEL=deepseek-chat
```

### 测试

```bash
pytest -q
```

## 目录结构

```
src/ftagents/
  models.py          # 共享状态数据模型
  datastore.py       # 加载示例数据(选品/合规规则/费率)
  llm.py             # 可插拔 LLM 层(无 key 降级)
  agents/            # 选品 / 合规 / 利润测算 三个 Agent
  orchestrator.py    # 流水线编排 + 人工定案 + 综合结论
  cli.py             # 命令行入口
  server.py          # 标准库 Web 服务(API + 单页 UI)
  static/index.html  # Web 单页界面
  rates.py           # 实时汇率(免费源 + 缓存 + 降级)
  data/*.json        # 示例数据(真实项目替换为 API/规则库)
tests/               # pytest 用例
docs/                # 业务分析与方案讨论记录
```

> 示例数据仅用于原型演示。真实使用时,把 `data/products.json` 换成选品数据源
> (如 Jungle Scout API),`compliance_rules.json` 换成维护中的合规规则库,
> `fees.json` 换成实时费率/汇率。
