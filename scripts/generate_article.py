#!/usr/bin/env python3
"""
generate_article.py
将对话骨架喂给 Claude API，生成公众号长文

Usage:
    python generate_article.py --skeleton skeleton.md [--title "我的开发日记"]
    python generate_article.py --skeleton skeleton.md --output article.md
"""

import argparse
import os
import sys
import json
from pathlib import Path
from datetime import datetime


# 风格定义的唯一事实源：references/article-style.md（SKILL.md Step 4 与本脚本共用）。
# 不在此处内联，避免两处描述漂移——改风格只改那一个文件。
STYLE_FILE = Path(__file__).resolve().parent.parent / "references" / "article-style.md"


def load_system_prompt() -> str:
    """从共享的风格文件加载 system prompt"""
    try:
        return STYLE_FILE.read_text(encoding="utf-8")
    except Exception:
        print(f"❌ 无法读取风格文件：{STYLE_FILE}", file=sys.stderr)
        print("💡 该文件是文章风格的单一事实源，请确认它随 skill 一起存在。", file=sys.stderr)
        sys.exit(1)


def call_claude_api(skeleton_text: str, title_hint: str = "") -> str:
    """调用 Claude API 生成文章"""
    try:
        import urllib.request

        user_prompt = f"""以下是一次 Vibe Coding 开发过程的对话骨架记录，包含了多个会话的关键对话。
请根据这些内容，写一篇公众号长文，还原这次开发的完整过程。

{f'参考标题：{title_hint}' if title_hint else '请自拟一个吸引人的标题'}

--- 对话骨架开始 ---
{skeleton_text}
--- 对话骨架结束 ---

请开始写文章："""

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            print("❌ 未找到 ANTHROPIC_API_KEY 环境变量。", file=sys.stderr)
            print("💡 推荐做法：在 Claude Code 会话内直接由 Claude 依据骨架撰写文章；", file=sys.stderr)
            print("   或导出 ANTHROPIC_API_KEY 后再运行本脚本作为回退。", file=sys.stderr)
            sys.exit(1)

        payload = json.dumps({
            "model": os.environ.get("VIBE_STORY_MODEL", "claude-sonnet-4-5"),
            "max_tokens": 4000,
            "system": load_system_prompt(),
            "messages": [
                {"role": "user", "content": user_prompt}
            ]
        }).encode("utf-8")

        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "anthropic-version": "2023-06-01",
                "x-api-key": api_key,
            }
        )

        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["content"][0]["text"]

    except Exception as e:
        print(f"❌ API 调用失败：{e}", file=sys.stderr)
        print("💡 请确认 Claude Code 环境中 API 可用（无需手动传 key）", file=sys.stderr)
        sys.exit(1)


def truncate_skeleton(skeleton_text: str, max_chars: int = 40000) -> str:
    """
    如果骨架太长，按会话分段后均匀采样截断
    保留头部和尾部，中间均匀抽取
    """
    if len(skeleton_text) <= max_chars:
        return skeleton_text

    print(f"⚠️  骨架长度 {len(skeleton_text)} 字符，超过限制，将自动精简...", file=sys.stderr)

    lines = skeleton_text.split("\n")
    # 保留所有标题行和时间戳行
    header_lines = [l for l in lines if l.startswith("#") or l.startswith("**")]
    # 内容行均匀采样
    content_lines = [l for l in lines if not l.startswith("#")]
    step = max(1, len(content_lines) // (max_chars // 100))
    sampled = content_lines[::step]

    result = "\n".join(header_lines[:20] + ["...(已精简)..."] + sampled)
    return result[:max_chars]


def main():
    parser = argparse.ArgumentParser(description="根据对话骨架生成公众号文章")
    parser.add_argument("--skeleton", type=str, required=True, help="骨架 Markdown 文件路径")
    parser.add_argument("--title", type=str, default="", help="文章标题提示（可选）")
    parser.add_argument("--output", type=str, default=None, help="输出文件路径（默认打印到 stdout）")
    args = parser.parse_args()

    skeleton_path = Path(args.skeleton)
    if not skeleton_path.exists():
        print(f"❌ 文件不存在：{args.skeleton}")
        sys.exit(1)

    skeleton_text = skeleton_path.read_text(encoding="utf-8")
    skeleton_text = truncate_skeleton(skeleton_text)

    print("✍️  正在生成文章，请稍候...", file=sys.stderr)
    article = call_claude_api(skeleton_text, args.title)

    if args.output:
        out_path = Path(args.output)
        out_path.write_text(article, encoding="utf-8")
        print(f"✅ 文章已写入：{args.output}", file=sys.stderr)
    else:
        print(article)


if __name__ == "__main__":
    main()
