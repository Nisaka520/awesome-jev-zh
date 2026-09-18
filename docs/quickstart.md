# Jev 中文上手指南

> 从零到第一个生产可用的分类器。假设你会 Python 或 TypeScript，不假设你懂 ML。
> 配套阅读：[概念与心法](concepts.md) · 回到 [主列表](../README.md)

---

## 目录

- [一、先解决「怎么用上」](#一先解决怎么用上)
- [二、三个原语，逐个讲透](#二三个原语逐个讲透)
- [三、置信度门控：用对 Jev 的分水岭](#三置信度门控用对-jev-的分水岭)
- [四、投机扇出：为什么可以「多问几题」](#四投机扇出为什么可以多问几题)
- [五、完整示例：一个能上线的工单分类器](#五完整示例一个能上线的工单分类器)
- [六、常见坑与报错对照](#六常见坑与报错对照)
- [七、上生产前的检查清单](#七上生产前的检查清单)

---

## 一、先解决「怎么用上」

官方直连要排 waitlist。按「最快能写上代码」排序：

### 路径 A · 官方 adapter（0 成本，现在就能写）

还没拿到 key，但想先把代码结构定下来：

```bash
pip install system-one-adapter
```

它提供一个和官方 `TypeSafeClient` **接口完全一致**的替身，后端走普通 LLM API。你现在写的代码，拿到 key 之后改一行 import 就能切到真 Jev。这也是官方推荐的「同一套问题横向对比 Jev 与聊天模型」的办法。

### 路径 B · Vercel AI Gateway（不用排队）

[Vercel 已官宣接入](https://vercel.com/changelog/typesafe-ai-jev-now-available-on-ai-gateway)，模型 ID `typesafe-ai/jev`：

```bash
pnpm add @ai-sdk/typesafe-ai
```

```ts
import { typeSafeAi } from '@ai-sdk/typesafe-ai';
import { experimental_evaluate } from 'ai';

const result = await experimental_evaluate({
  model: typeSafeAi.evaluationModel('jev-latest'),
  state: {
    message: '我被重复扣款了两次，请退掉多扣的那笔。',
  },
  questions: {
    department: {
      type: 'choice',
      instructions: '这个工单该给哪个组',
      criteria: {
        billing: { includes: ['扣款', '账单', '退款'] },
        technical: ['Bug', '服务中断'],
        other: null,
      },
    },
    severity: {
      type: 'score',
      instructions: '问题严重程度',
      criteria: ['只是观感问题', '有绕过办法', '完全卡住，无绕过办法'],
    },
    requestsRefund: {
      type: 'boolean',
      instructions: '客户在要求退钱',
    },
  },
});

console.log(result.answers.department.choice);       // 'billing'
console.log(result.answers.severity.score);          // 2.0x
console.log(result.answers.requestsRefund.probability);
console.log(result.usage);
```

> 注意 AI SDK 里 Noul 叫 `type: 'boolean'`，读结果用 `.probability`；官方 SDK 里叫 `Noul`，读结果用 `.noul`。同一个东西，两套命名。

### 路径 C · 官方 SDK（拿到 key 之后的正式姿势）

```bash
pip install typesafe-sdk          # 或 uv add typesafe-sdk
npm install @typesafe-ai/sdk      # TS/JS
export TYPESAFE_API_KEY=sk-...    # 客户端自动读这个变量
```

### 路径 D · 裸 HTTP

```
POST https://api.typesafe.ai/v1/systemone
```

没有官方 SDK 的语言走这条，或者直接用[社区 SDK](../README.md#社区与-typesafe-无隶属关系)（Go / Rust / Ruby / PHP / .NET / Elixir / Erlang / Scala 都有人写了）。

---

## 二、三个原语，逐个讲透

所有 Jev 请求都是同一个形状：**一份 `state` + 一组带名字的问题**。问题只有三种。

### Choice —— 从给定选项里选一个

```python
from typesafe_sdk import Choice

Choice(
    instructions="这个工单该给哪个组",
    criteria={
        "billing":   "支付、扣款、订阅、退款相关",
        "technical": "Bug、集成失败、服务不可用",
        "sales":     "定价、试用、扩容咨询",
    },
)
```

返回 `choice`（命中的 key）、`probabilities`（每个选项的概率分布）、`confidence`。

**要点：**

- `criteria` 的 **key 是代码要用的标识符，value 是给模型的判据说明**。key 写得像代码（`billing`），value 写得像人话，两边都别省。
- 单个 Choice 最多 **255 个候选**。超了就分层：先粗分类，再对粗类内部细分（官方的 [hierarchical classification](https://docs.typesafe.ai/cookbooks/hierarchical_classification) cookbook 讲的就是这个）。
- **选项必须是闭集**。「从页面上 40 个按钮里选一个点」是它的主场；「从文章里抽出人名」不是——那要先用正则/NER 出候选，再让它选。
- 概率分布别扔掉。`probabilities` 里第一名和第二名差多少，比 `confidence` 更能说明「这题是不是本来就模棱两可」。

### Score —— 在你定义的量表上打分

```python
from typesafe_sdk import Score

Score(
    instructions="客户的不满程度",
    criteria=["平静陈述事实", "有情绪但还讲道理", "非常愤怒，措辞激烈"],
)
```

返回的 `score` 是**小数**（比如 `1.035`），不是整数档位——它落在你给的档位之间，所以你能拿到比三档更细的分辨率。

**要点：**

- 量表档位要**互斥、单调、可观测**。「好 / 中 / 差」这种没有可观测锚点的量表，结果会很飘；换成「无错别字 / 有 1–2 处 / 满篇错」就稳了。
- 3–5 档最好用。档位太多，模型和你都说不清相邻两档差在哪。
- **不要把多个维度塞进一个 Score。**「这段代码质量如何」应该拆成「可读性」「有没有明显 bug」「测试覆盖够不够」三个独立 Score，权重由你的代码定——这就是官方的[组合打分模式](https://docs.typesafe.ai/patterns/composite-scoring)。

### Noul —— 这句话是真的吗

```python
from typesafe_sdk import Noul

Noul(instructions="这条消息表达了紧急或时间压力")
```

返回一个 0–1 的 `noul`，就是「这个陈述为真」的概率。

**要点：**

- **`instructions` 要写成一个陈述句，不是问句。** 写「用户在抱怨」，别写「用户在抱怨吗？」。
- Noul 是三个原语里最便宜好用的一个：护栏、内容审核、语义检索、事实核对，全是 Noul。
- 一次问几十个 Noul 完全没问题——见下面的投机扇出。

### 三个一起用

```python
response = client.system_one(
    state=ticket_text,
    questions={
        "department":  Choice(...),
        "frustration": Score(...),
        "is_urgent":   Noul(...),
    },
)
```

**同一份 state 上的多个问题是并行、隔离求值的**——问题之间互相看不见，所以不存在「前一题影响后一题」。这既是它快的原因，也意味着**需要串联推理的任务不适合它**。

---

## 三、置信度门控：用对 Jev 的分水岭

这是整份指南最重要的一节。

> **答案告诉你「是什么」，置信度告诉你「要不要直接动手」。**

绝大多数把 Jev 用砸的案例，都是直接拿 `choice` 去执行，不看 `confidence`。正确姿势是三段式：

```python
ans = response.answers["department"]

if ans.confidence >= 0.85:
    route_to(ans.choice)                    # 高置信：直接执行
elif ans.confidence >= 0.60:
    route_to(ans.choice, flag="需复核")      # 中置信：执行但打标
else:
    escalate_to_llm_or_human(ticket_text)   # 低置信：上抛
```

**阈值怎么定？** 不要拍脑袋，跑一批你自己的真实数据，按置信度分桶统计准确率：

```python
buckets = {}                                 # 0.5-0.6, 0.6-0.7, ...
for sample in labeled_data:
    ans = ask(sample.text)
    b = round(ans.confidence, 1)
    buckets.setdefault(b, []).append(ans.choice == sample.label)

for b in sorted(buckets):
    hits = buckets[b]
    print(f"置信度 {b:.1f}: 准确率 {sum(hits)/len(hits):.1%}  样本 {len(hits)}")
```

模型宣称是**校准**的——置信度 0.7 的那一桶，长期准确率就该在 70% 附近。**跑这张表，既是在定阈值，也是在验证它在你的数据上到底校不校准。** 中文数据上目前没有任何公开评测，这一步不能省。

拿到表之后，阈值就是业务决定：能接受多少错误率，就把线划在哪。

---

## 四、投机扇出：为什么可以「多问几题」

Jev 的**输出 token 免费**，输入按 $0.042/MTok 计费，而同一次请求里的所有问题**共享同一份 state**。这意味着：

> 一次请求问 1 个问题和问 20 个问题，**成本几乎一样**（state 只算一次）。

所以正确的用法是反直觉的：**把可能用得上的问题一次全问了，在代码里筛。** 这就是官方的[投机扇出模式](https://docs.typesafe.ai/patterns/fan-out)。

```python
# ❌ 低效：按需一题一题问，每次都重传 state
dept = ask(ticket, {"department": Choice(...)})
if dept.choice == "billing":
    refund = ask(ticket, {"wants_refund": Noul(...)})      # 又付一遍 state 的钱

# ✅ 一次问全，代码里挑
r = ask(ticket, {
    "department":    Choice(...),
    "wants_refund":  Noul(...),     # 可能用不上
    "is_urgent":     Noul(...),     # 可能用不上
    "frustration":   Score(...),
    "is_spam":       Noul(...),
    "needs_human":   Noul(...),
})
```

**上限是 64k 上下文**（state + 最长的那个问题 ≤ 32k），在这个预算内尽情扇出。

---

## 五、完整示例：一个能上线的工单分类器

把上面几条合起来，带降级、带门控、带成本统计：

```python
import os
from typesafe_sdk import Choice, Noul, Score, TypeSafeClient

client = TypeSafeClient()          # 自动读 TYPESAFE_API_KEY

DEPARTMENTS = {
    "billing":   "支付、扣款、订阅、发票、退款",
    "technical": "Bug、集成失败、API 报错、服务不可用",
    "sales":     "定价、试用、扩容、商务合作咨询",
    "other":     "以上都不是",
}

QUESTIONS = {
    "department": Choice(instructions="这个工单该给哪个组", criteria=DEPARTMENTS),
    "frustration": Score(
        instructions="客户的不满程度",
        criteria=["平静陈述事实", "有情绪但还讲道理", "非常愤怒，措辞激烈"],
    ),
    "is_urgent":    Noul(instructions="这条消息表达了紧急或时间压力"),
    "wants_refund": Noul(instructions="客户明确要求退款"),
    "is_spam":      Noul(instructions="这条消息是广告、推广或无意义内容"),
}

AUTO_ROUTE_THRESHOLD = 0.85        # 跑完置信度分桶表之后再定这个数


def triage(ticket_text: str) -> dict:
    r = client.system_one(state=ticket_text, questions=QUESTIONS)
    a = r.answers

    if a["is_spam"].noul > 0.9:
        return {"action": "drop", "reason": "spam"}

    dept = a["department"]
    priority = "P0" if (a["is_urgent"].noul > 0.8 or a["frustration"].score > 1.6) else "P2"

    if dept.confidence < AUTO_ROUTE_THRESHOLD:
        return {
            "action": "escalate",            # 交给 LLM 或人工
            "hint": dept.choice,             # 但把它的猜测一起带上
            "confidence": dept.confidence,
            "priority": priority,
        }

    return {
        "action": "route",
        "team": dept.choice,
        "priority": priority,
        "wants_refund": a["wants_refund"].noul > 0.7,
        "cost_tokens": r.usage.input_tokens,   # output 不计费
    }
```

**这段代码的几个设计点，都是前面几节的直接结果：**

1. spam 用 Noul 先拦，省掉后面所有处理。
2. 优先级由**两个独立信号**在代码里合成，不让模型一次判断「优先级」这种复合概念。
3. 低置信度不丢弃模型的猜测，而是作为 `hint` 一起上抛——人工复核时这是有用信息。
4. 只统计 `input_tokens`，因为输出免费。

---

## 六、常见坑与报错对照

| 现象 | 多半是因为 | 怎么改 |
| :-- | :-- | :-- |
| 结果飘、同样输入每次不同 | 问题问得太复合，或量表档位没有可观测锚点 | 拆成原子问题；档位改成能用眼睛验证的描述 |
| 置信度普遍很低 | 选项之间语义重叠，或漏了「其他」兜底项 | 选项互斥化；补一个 `other` |
| 想抽取信息但选项列不全 | 把开放式抽取当成 Choice 在用 | 先正则/NER 出候选，再让 Jev 选（[pre-parsed value extraction](https://docs.typesafe.ai/cookbooks/pre_parsed_value_extraction_cookbook)） |
| 上下文超限 | state + 最长问题 > 32k，或整体 > 64k | 先做检索/截断；长文档切块后逐块问再在代码里合并 |
| Choice 报候选过多 | 超过 255 个候选上限 | 分层分类，或先用 BM25 出短名单再问 |
| 想让它解释为什么 | 它不会，这是设计 | 要理由就上 LLM；Jev 只给概率 |
| 中文任务表现不如预期 | 训练语料构成未公开，中文无公开评测 | **必须自己跑置信度分桶表**，别照搬英文结论 |
| 速率限制 | 250k token/秒、1200 请求/分钟 | 合并问题（投机扇出）比提高并发更有效 |

---

## 七、上生产前的检查清单

- [ ] 读过[官方公布的 Jev 1.13 能力毛边](https://docs.typesafe.ai/model-jaggedness/jev-1.13)
- [ ] 在**你自己的真实数据**上跑过置信度分桶表，阈值是量出来的不是拍出来的
- [ ] 每个决策点都有低置信度的降级路径（LLM 或人工）
- [ ] 问题都是原子的，复合逻辑在你的代码里
- [ ] 用投机扇出合并了请求，而不是一题一个请求
- [ ] 有降级方案：供应商挂了能切到 [system-one-adapter](https://github.com/typesafe-ai/system-one-adapter-python) 或自己的规则
- [ ] 记录了 `input_tokens` 和置信度分布，能持续观察线上漂移
- [ ] 装的是 `typesafe-sdk`，不是蹭名字的包

---

**下一步** → [概念与心法](concepts.md)：System One 到底新在哪、RLCD 和 RLHF 差在哪、怎么把现有 LLM 流程改造成 Jev 流程。
