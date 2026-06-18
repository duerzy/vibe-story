# Vibe Story

你是不是 Vibe Coding 了一整天——和 Claude 你来我往几十轮，改了又改、报错又修，
终于把东西跑通了——到晚上想把这一天记下来，却只剩满屏的 diff 和一段记不太清的过程？

**Vibe Story 把你和 Claude Code 的开发会话，自动还原成完整的时间线，再写成一篇文章。**

开发日志、项目复盘、技术分享、公众号推文都行。那些被中断的尝试、反复的调试、
最终的突破，不再只躺在日志里，而是变成一篇能发出去的故事。

---

## 先看产出 👀

下面这篇就是 Vibe Story 从真实开发会话里生成的——一次烧掉 50 美元的 code review，
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

这篇的"原料"只是一堆会话日志，时间线、挫折、反转全是 Vibe Story 自动还原的。

---

## 它能做什么

- 自动找到你本机的 Claude Code 项目，把跨多个会话的开发过程拼成一条时间线
- 只保留真正的对话，滤掉工具调用和系统噪声，还原"你想了什么、Claude 做了什么"
- 由 Claude 写成第一人称、保留挫折与反转的长文——读起来像故事，不像流水账
- 不需要额外的 API key 或服务，产物就存在你自己的项目目录里

## 安装

装好后，在 Claude Code 里输入 `/vibe-story` 就能用。

### 方式一：一句话让 Claude 帮你装（推荐）

把这句话发给 Claude Code：

```
帮我安装这个 skill：https://github.com/duerzy/vibe-story
```

### 方式二：通用 CLI

```bash
npx skills add duerzy/vibe-story      # 装到当前项目
npx skills add duerzy/vibe-story -g   # 全局安装（推荐，任何项目都能用）
```

### 方式三：手动

```bash
git clone https://github.com/duerzy/vibe-story ~/.claude/skills/vibe-story
```

（Windows 技能目录在 `%APPDATA%\Claude\skills\`）

## 怎么用

最省事——把需求直接跟在命令后面，一句话搞定：

```
/vibe-story 把我今天在这个项目里的开发过程，写成一篇开发日志
```

或者只敲 `/vibe-story`，Claude 会问你想写哪个项目、什么时间范围，再开始。

接下来它会自己找出相关会话、还原时间线、和你确认，然后把文章写好交给你。
不满意随时让它换标题、调风格、重写。

## 产物在哪

文章和时间线都存在你**目标项目目录**下的 `vibe-story/` 里：

```
<你的项目>/vibe-story/
├── skeleton.md   # 还原出来的时间线
└── article.md    # 写好的文章
```

## 隐私

提取和解析全部在**本机本地**完成，不向任何服务器上传数据。文章由你正在用的
Claude 撰写——和你平时用 Claude Code 写代码一样，没有额外的数据外发。

---

## 想改它 / 参与贡献

仓库根目录就是这个 skill 本身，`SKILL.md` 定义了完整工作流。结构：

```
vibe-story/
├── SKILL.md                       # 工作流定义（给 Claude 读）
├── references/article-style.md    # 文章风格（想改文风改这里）
├── scripts/
│   ├── extract_sessions.py / .js  # 提取时间线（Python / Node 双实现，输出一致）
│   └── generate_article.py        # 脱离会话的批量生成（可选）
└── examples/                      # 产出示例
```

> 提取逻辑有 Python 与 Node 两份等价实现，**改一处记得同步改另一处**。

欢迎提 [Issue](https://github.com/duerzy/vibe-story/issues) 或 PR。

## 觉得有用？给个 Star ⭐

如果 Vibe Story 帮你把开发过程变成了能发出去的故事，欢迎点个 Star，让更多人发现它。

## License

[MIT](LICENSE) © 花照小赵 (duerzy)
