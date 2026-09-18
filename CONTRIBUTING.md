# 贡献指南

感谢愿意花时间。这份列表只有一个目标：**让中文开发者用最短的路径把 Jev 用明白。**

## 提 PR 前先看这几条

### ✅ 欢迎的

- 真正基于 Jev / TypeSafe System One 的开源项目（或明确声明受其接口启发的复现）
- 中文原创的实践文章、踩坑记录、评测数据 —— **这是最缺的，优先合并**
- 中文场景的评测（分类、审核、工单、检索），哪怕结论对 Jev 不利，尤其欢迎
- 官方文档的更新、失效链接修复、术语译法改进
- 给 `scripts/denylist.txt` 补充误收的无关项目

### ❌ 不收的

- 空仓库、只有 README 没有代码的「占位」项目
- 纯 API 中转 / 代理 / 倒卖 key 的服务
- 只有 landing page、没有开源代码也没有可用 demo 的产品
- 纯链接堆砌，没有一句中文说明
- 与 Jev 无关但名字里带 jev 的项目（jevois、jEveAssets、JEvents 等）

## 格式要求

人工精选区的每一行都是表格，格式：

```markdown
| [**owner/repo**](https://github.com/owner/repo) | ![](https://badgen.net/github/stars/owner/repo) | 一句话中文说明，讲清楚它用 Jev 干什么、有什么特别的数字 |
```

- **必须有中文说明**，不接受直接贴英文 description。
- 说明里有具体数字（延迟、成本、准确率）的，请一并写上并注明来源。
- 厂商自评数据请标注「官方数据」，别当成独立结论。

## 关于 🔥 热门项目自动榜

那一段由 [`scripts/collect_hot.py`](scripts/collect_hot.py) 每天自动重写，**不要手动改**，改了也会被覆盖。

- 误收了无关项目 → 往 [`scripts/denylist.txt`](scripts/denylist.txt) 加一行 `owner/repo`
- 漏收了 → 多半是仓库描述里没有关键词，或创建时间早于 2026-09-10，提个 Issue 说一声
- 想调整收录规则 → 直接改脚本顶部的常量，PR 里说明理由

本地试跑（不写文件）：

```bash
GITHUB_TOKEN=$(gh auth token) python3 scripts/collect_hot.py --dry-run
```

## 提交前自查

- [ ] 链接都能打开（`curl -o /dev/null -w "%{http_code}" <url>` 返回 200）
- [ ] 中文说明一句话讲清楚了「它用 Jev 干什么」
- [ ] 放在了正确的分类下
- [ ] 没有动 `<!-- HOT:START -->` 和 `<!-- HOT:END -->` 之间的内容

## 许可

提交即表示你同意以 [CC0 1.0](LICENSE) 授权你的贡献。
