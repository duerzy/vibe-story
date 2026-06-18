# Vibe Story

把 Claude Code 跨多个会话的开发过程，提取成可读的**时间线骨架**，再生成一篇适合公众号发布的**长文**。

让你的 Vibe Coding 过程——那些被中断的尝试、反复的调试、最终的突破——不再只躺在
`~/.claude/projects/` 的日志里，而是变成一篇能发出去的故事。

---

## 先看产出 👀

下面这篇就是 vibe-story 从真实开发会话里生成的——一次烧掉 50 美元的 code review，
意外揪出一个当晚真在生产上爆发的 0 级 bug：

> **《50 美元，买到了什么》**
>
> 凡事要稳，这是我一直信奉的原则。但 6 月 10 日凌晨三点多，我把这句话踩了第一脚。
>
> Fable 5 发布了……我告诉自己：就浅浅看一下，快的。**13 分钟。** 系统提示：
> `You've hit your monthly spend limit`。账户余额：$0.00。
>
> ……但那次烧掉 50 美元的 code review，找到了一个真实的 0 级 bug。那个 bug 当晚在生产上
> 出现了。修复代码早就在本地等着，只差一次部署。能说什么。值了。

👉 **完整文章：[examples/article-fable-review.md](examples/article-fable-review.md)**

这篇的"原料"只是一堆 `.jsonl` 会话日志，时间线、挫折、反转全是 vibe-story 自动还原的。

---

## 它能做什么

- 扫描本机所有 Claude Code 项目，按最近活跃排序列出
- 从指定项目的会话日志（`.jsonl`）里**只抽对话文字**，自动过滤工具调用、子代理对话、系统注入的噪声
- 把多个会话按真实时间线拼成一份骨架 Markdown
- 由 Claude 依据骨架，写成 1500–2500 字、第一人称、保留挫折与反转的公众号长文

## 工作流程

```
用户触发 /vibe-story
  ↓
Step 0  探测运行时（Python / Node / 都没有则 Claude 手动解析）
  ↓
Step 1  列出项目，确定目标（命中当前目录则自动选择）
  ↓
Step 2  提取对话骨架 → <项目>/vibe-story/skeleton.md
  ↓
Step 3  展示骨架摘要，请用户确认时间范围 / 排除会话 / 标题偏好
  ↓
Step 4  Claude 依据骨架直接撰写文章 → <项目>/vibe-story/article.md
  ↓
Step 5  输出文章，告知文件路径
```

## 环境要求

提取脚本提供 **Python 与 Node 两个等价实现**（输出逐字节一致），有谁用谁：

| 运行时 | 版本 | 说明 |
|--------|------|------|
| Python | 3.10+ | 纯标准库，无需 `pip install` |
| Node   | 16+   | 零依赖，无需 `npm install` |
| 都没有 | —     | 降级：Claude 直接读 `.jsonl` 解析，流程照样跑通 |

撰写文章（Step 4）由 Claude 在会话内完成，**不需要任何运行时、不需要 API key**。

## 安装

> 把下面的 `duerzy/vibe-story` 换成你自己的 GitHub 仓库。

### 方式一：一句话让 Claude 帮你装（推荐）

把这句话直接发给 Claude Code（或任何支持 Agent Skills 的工具）：

```
帮我安装这个 skill：https://github.com/duerzy/vibe-story
```

Claude 会自动克隆仓库、放进你的技能目录。重启后输入 `/vibe-story` 即可用。

### 方式二：通用 CLI 一键安装

```bash
npx skills add duerzy/vibe-story
```

### 方式三：手动安装

```bash
git clone https://github.com/duerzy/vibe-story ~/.claude/skills/vibe-story
```

只想给某个项目用，就 clone 到项目级目录 `<项目>/.claude/skills/vibe-story/`。

| 平台 | 个人技能目录 |
|------|--------------|
| macOS / Linux | `~/.claude/skills/` |
| Windows | `%APPDATA%\Claude\skills\` |

> 三种方式都把整个仓库作为 skill 目录使用——**仓库根目录就是 `SKILL.md`**，无需任何
> marketplace 或插件清单。这也意味着别人想安装就得先来这个仓库拿链接，顺手就能给个 star ⭐

## 使用方式

通常直接在 Claude Code 里输入 `/vibe-story` 触发，由 Claude 按上面的流程引导你完成。

也可以手动调用提取脚本：

```bash
SKILL_DIR=~/.claude/skills/vibe-story

# 选运行时
if command -v python3 >/dev/null 2>&1; then
  RUNNER="python3 $SKILL_DIR/scripts/extract_sessions.py"
else
  RUNNER="node $SKILL_DIR/scripts/extract_sessions.js"
fi

# 1) 列出项目
$RUNNER --list

# 2) 提取某个项目的骨架（按序号或 hash）
PROJ=/path/to/your/project
mkdir -p "$PROJ/vibe-story"
$RUNNER --project 1 --output "$PROJ/vibe-story/skeleton.md"
```

### 提取脚本参数

| 参数 | 说明 | 示例 |
|------|------|------|
| `--list` | 列出所有项目 | — |
| `--project` | 项目序号或 hash | `1` / `a3f2b1c0` |
| `--since` | 只含最近 N 天或某日期之后 | `7d` / `30d` / `2025-01-01` |
| `--output` | 输出文件路径（默认打印到 stdout） | `out.md` |
| `--max-chars` | 单条消息最大字符数，`0`=不截断（默认） | `300` |

> 默认不截断：最终的分析报告 / 交付物往往就在最长的几条消息里，
> 那通常是文章最有料的部分。仅当骨架过大、只想要预览时才设 `--max-chars`。

## 产物位置

产物落在**目标项目目录**下的 `vibe-story/` 子目录（而非 `/tmp`，避免被系统清理、便于和项目一起留存）：

```
<目标项目>/vibe-story/
├── skeleton.md   # 时间线骨架
└── article.md    # 公众号长文
```

若该目录在 git 仓库内，可按需把 `vibe-story/` 加进 `.gitignore`。

## 文件结构

```
vibe-story/
├── SKILL.md                      # 给 Claude 看的工作流说明（仓库根目录即 skill）
├── README.md                     # 本文件
├── LICENSE                       # MIT
├── examples/
│   └── article-fable-review.md   # 真实产出示例
├── references/
│   └── article-style.md          # 文章风格的唯一事实源（撰文 / 脚本回退共用）
└── scripts/
    ├── extract_sessions.py       # 提取骨架（Python 版）
    ├── extract_sessions.js       # 提取骨架（Node 版，与 .py 输出一致）
    └── generate_article.py       # 脱离会话的批量生成回退（需 ANTHROPIC_API_KEY）
```

## 关于文章生成的两条路

1. **首选 —— Claude 在会话内直接撰写**：Claude 就在现场，能完整读骨架、回读原始 `.jsonl`
   补细节、和你来回改稿，质量最高，且无需任何 key。
2. **回退 —— `generate_article.py`**：仅当需要脱离会话、批量生成时使用，需先
   `export ANTHROPIC_API_KEY=...`。它与首选方式**共用** `references/article-style.md`，风格一致。

## 注意事项

- 提取逻辑有 Python / Node 两份实现——**改逻辑时两个文件都要同步改**，否则两版输出会漂移。
- 跨平台日志目录：Windows 在 `%APPDATA%\Claude\projects\`，Mac/Linux 在 `~/.claude/projects/`。
- 会话很多时建议加 `--since 30d` 限定范围。
- 时间戳已统一为本地时区；会话起点取最早一条消息的真实时间（而非文件 mtime，避免 resume 失真）。

## 隐私

所有处理都在**本机本地**完成：脚本只读你自己的 `~/.claude/projects/` 日志，产物写到你的项目目录。
唯一会把内容发出去的是回退脚本 `generate_article.py`（调 Anthropic API）；首选的会话内撰写方式不外发任何额外数据。

---

## 觉得有用？给个 Star ⭐

如果 vibe-story 帮你把开发过程变成了能发出去的故事，欢迎点个 Star——
这是对作者最直接的鼓励，也能让更多人发现它。

有想法、bug 或想要的功能，随时开 [Issue](https://github.com/duerzy/vibe-story/issues)。

## License

[MIT](LICENSE) © 花照小赵 (duerzy)
