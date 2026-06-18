#!/usr/bin/env python3
"""
extract_sessions.py
从 Claude Code 的 .jsonl 会话文件中提取对话骨架

Usage:
    python extract_sessions.py --list                  # 列出所有项目
    python extract_sessions.py --project <hash_or_path> [--since 7d]
"""

import json
import os
import sys
import argparse
import re
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional


# ── 跨平台路径 ─────────────────────────────────────────────────────────────────
def get_claude_projects_dir() -> Path:
    """返回 ~/.claude/projects 的跨平台路径"""
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home()))
        return base / "Claude" / "projects"
    else:
        return Path.home() / ".claude" / "projects"


# ── 项目发现 ──────────────────────────────────────────────────────────────────
def discover_projects(projects_dir: Path) -> list[dict]:
    """
    扫描 projects 目录，尝试从 .jsonl 里的 cwd 字段反推项目路径
    返回 [{ hash, path_hint, latest_mtime, session_count }]
    """
    if not projects_dir.exists():
        return []

    results = []
    for proj_dir in sorted(projects_dir.iterdir()):
        if not proj_dir.is_dir():
            continue

        jsonl_files = sorted(proj_dir.glob("*.jsonl"), key=lambda f: f.stat().st_mtime)
        if not jsonl_files:
            continue

        latest_mtime = max(f.stat().st_mtime for f in jsonl_files)
        path_hint = _guess_project_path(jsonl_files)

        results.append({
            "hash": proj_dir.name,
            "path_hint": path_hint or "(unknown)",
            "latest_mtime": latest_mtime,
            "latest_dt": datetime.fromtimestamp(latest_mtime),
            "session_count": len(jsonl_files),
        })

    # 按最近活跃排序
    results.sort(key=lambda x: x["latest_mtime"], reverse=True)
    return results


def _guess_project_path(jsonl_files: list[Path]) -> Optional[str]:
    """从 .jsonl 文件的第一条记录里尝试读取 cwd"""
    for f in reversed(jsonl_files):  # 最新的文件更可能有 cwd
        try:
            with open(f, "r", encoding="utf-8") as fp:
                for line in fp:
                    line = line.strip()
                    if not line:
                        continue
                    record = json.loads(line)
                    cwd = record.get("cwd") or record.get("workingDirectory")
                    if cwd:
                        return cwd
        except Exception:
            continue
    return None


def print_project_list(projects: list[dict]):
    """打印可交互的项目列表"""
    print("\n📂 Claude Code 项目列表（按最近活跃排序）\n")
    print(f"  {'#':<4} {'最近活跃':<22} {'会话数':<6} 项目路径")
    print("  " + "─" * 75)
    for i, p in enumerate(projects):
        dt_str = p["latest_dt"].strftime("%Y-%m-%d %H:%M")
        print(f"  {i+1:<4} {dt_str:<22} {p['session_count']:<6} {p['path_hint']}")
    print()


# ── 消息提取 ──────────────────────────────────────────────────────────────────
MIN_TEXT_LENGTH = 20  # 短于这个字符数的消息丢弃

# 注入型内容前缀：skill / hook / system-reminder 注入的伪 user 消息，应当过滤
NOISE_PREFIXES = (
    "Base directory for this skill",
    "<system-reminder",
    "<SUBAGENT-STOP",
    "<command-message",
    "<command-name",
    "<local-command",
    "<task-notification",
    "[Request interrupted",
    "Caveat:",
    "This session is being continued",
)


def is_noise(text: str) -> bool:
    """判断一条 user 文本是否为注入型噪声（skill/hook/系统提示），而非真实用户发言"""
    stripped = text.lstrip()
    return any(stripped.startswith(p) for p in NOISE_PREFIXES)

def extract_text_content(content) -> Optional[str]:
    """
    从 message content 字段中提取纯文本。
    content 可能是 str，或 list of blocks。
    跳过含 tool_use / tool_result / thinking 类型的块。
    """
    if isinstance(content, str):
        return content.strip() if len(content.strip()) >= MIN_TEXT_LENGTH else None

    if isinstance(content, list):
        text_parts = []
        has_tool = False
        for block in content:
            if not isinstance(block, dict):
                continue
            btype = block.get("type", "")
            if btype in ("tool_use", "tool_result", "thinking"):
                has_tool = True
                continue
            if btype == "text":
                t = block.get("text", "").strip()
                if t:
                    text_parts.append(t)

        # 如果整条消息只有工具调用，没有文字，丢弃
        combined = "\n".join(text_parts).strip()
        if not combined or len(combined) < MIN_TEXT_LENGTH:
            return None
        return combined

    return None


def parse_timestamp(record: dict) -> Optional[datetime]:
    """尝试解析记录中的时间戳"""
    for key in ("timestamp", "createdAt", "created_at", "ts"):
        val = record.get(key)
        if not val:
            continue
        try:
            if isinstance(val, (int, float)):
                return datetime.fromtimestamp(val / 1000 if val > 1e10 else val)
            dt = datetime.fromisoformat(str(val).replace("Z", "+00:00"))
            # CC 时间戳是 UTC（带 tzinfo）。会话标题用的是本地 mtime，若这里直接
            # strftime 会打印 UTC 墙钟，导致同一条时间线 UTC/本地混用、自相矛盾。
            # 统一转成本地时区再去掉 tzinfo，与会话标题保持一致。
            if dt.tzinfo is not None:
                dt = dt.astimezone().replace(tzinfo=None)
            return dt
        except Exception:
            continue
    return None


def extract_from_jsonl(filepath: Path) -> list[dict]:
    """
    从单个 .jsonl 文件提取对话骨架消息列表
    返回 [{ role, text, timestamp }]
    """
    messages = []
    file_mtime = datetime.fromtimestamp(filepath.stat().st_mtime)

    try:
        with open(filepath, "r", encoding="utf-8") as fp:
            for line in fp:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue

                # 当前 CC 格式：每行 type 为 "user"/"assistant"，role/content 嵌在 message 里；
                # 兼容旧格式 type == "message"（顶层 role/content）
                record_type = record.get("type")
                if record_type not in ("user", "assistant", "message"):
                    continue

                # 结构化过滤（比文本前缀匹配更稳健，跨 CC 版本不易失效）：
                # isSidechain=子代理内部对话，会污染主线骨架；isMeta=系统注入的元消息
                if record.get("isSidechain") or record.get("isMeta"):
                    continue

                msg = record.get("message")
                if not isinstance(msg, dict):
                    msg = record

                role = msg.get("role") or record.get("role")
                if role not in ("user", "assistant", "human"):
                    continue

                content = msg.get("content")
                if content is None:
                    continue

                text = extract_text_content(content)
                if not text:
                    continue

                # 过滤 skill/hook 注入到 user 角色里的伪消息
                if role in ("user", "human") and is_noise(text):
                    continue

                ts = parse_timestamp(record) or file_mtime

                messages.append({
                    "role": "human" if role in ("user", "human") else "assistant",
                    "text": text,
                    "timestamp": ts,
                })
    except Exception as e:
        print(f"  ⚠️  读取 {filepath.name} 时出错: {e}", file=sys.stderr)

    return messages


def load_project_sessions(
    proj_dir: Path,
    since: Optional[datetime] = None
) -> list[dict]:
    """
    加载项目下所有会话，返回按时间排序的消息列表
    每条消息额外带 session_id 字段
    """
    jsonl_files = sorted(proj_dir.glob("*.jsonl"), key=lambda f: f.stat().st_mtime)

    if since:
        jsonl_files = [f for f in jsonl_files if datetime.fromtimestamp(f.stat().st_mtime) >= since]

    all_messages = []
    for f in jsonl_files:
        session_msgs = extract_from_jsonl(f)
        if not session_msgs:
            continue
        session_id = f.stem[:8]  # 取 UUID 前8位作为简短标识
        # 会话起点用最早一条消息的真实时间戳，而非文件 mtime——
        # mtime 是"最后修改时刻"，被 resume 过的会话会偏成"恢复时刻"，失真。
        session_start = min(m["timestamp"] for m in session_msgs)
        for msg in session_msgs:
            msg["session_id"] = session_id
            msg["session_start"] = session_start
        all_messages.extend(session_msgs)

    # 全局按时间戳排序
    all_messages.sort(key=lambda m: m["timestamp"])
    return all_messages


# ── 骨架格式化输出 ────────────────────────────────────────────────────────────
def format_skeleton(messages: list[dict], project_path: str, max_chars: int = 0) -> str:
    """
    输出时间线骨架 Markdown。
    max_chars: 单条消息最大字符数，0 表示不截断（默认）。
    注意：骨架是 Step 4 撰文的源材料，最终的分析报告/交付物往往就在最长的那几条里，
    默认截断会静默地给成品质量设天花板，所以默认保留全文。需要精简预览时再传 max_chars。
    """
    lines = [
        f"# 开发过程骨架 — {project_path}",
        f"_生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}_",
        f"_共 {len(messages)} 条对话消息_\n",
    ]

    current_session = None
    for msg in messages:
        sid = msg["session_id"]
        if sid != current_session:
            current_session = sid
            lines.append(f"\n## 会话 {sid}  ·  {msg['session_start'].strftime('%Y-%m-%d %H:%M')}\n")

        role_label = "👤 用户" if msg["role"] == "human" else "🤖 Claude"
        ts = msg["timestamp"].strftime("%H:%M")
        text = msg["text"]
        if max_chars and len(text) > max_chars:
            text = text[:max_chars] + "…（已截断）"
        lines.append(f"**{role_label}** `{ts}`\n{text}\n")

    return "\n".join(lines)


# ── 主程序 ────────────────────────────────────────────────────────────────────
def parse_since(s: str) -> Optional[datetime]:
    """解析 --since 参数，如 7d / 30d / 2024-01-01"""
    m = re.match(r"^(\d+)d$", s)
    if m:
        return datetime.now() - timedelta(days=int(m.group(1)))
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return None


def main():
    parser = argparse.ArgumentParser(description="Claude Code 会话提取工具")
    parser.add_argument("--list", action="store_true", help="列出所有项目")
    parser.add_argument("--project", type=str, help="项目 hash 或序号（从 --list 获取）")
    parser.add_argument("--since", type=str, default=None, help="只包含最近N天，如 7d 或 2024-01-01")
    parser.add_argument("--output", type=str, default=None, help="输出文件路径（默认打印到 stdout）")
    parser.add_argument("--max-chars", type=int, default=0, help="单条消息最大字符数，0=不截断（默认）。仅在需要精简预览时设置")
    args = parser.parse_args()

    projects_dir = get_claude_projects_dir()
    projects = discover_projects(projects_dir)

    if not projects:
        print(f"❌ 未找到任何 Claude Code 项目，请确认 {projects_dir} 存在")
        sys.exit(1)

    if args.list or not args.project:
        print_project_list(projects)
        if not args.project:
            print("👉 使用方式：python extract_sessions.py --project <序号或hash> [--since 7d]")
        return

    # 解析 --project 参数
    target = args.project.strip()
    proj_dir = None

    if target.isdigit():
        idx = int(target) - 1
        if 0 <= idx < len(projects):
            proj_dir = projects_dir / projects[idx]["hash"]
        else:
            print(f"❌ 序号 {target} 超出范围（共 {len(projects)} 个项目）")
            sys.exit(1)
    else:
        # 尝试按 hash 或路径模糊匹配
        for p in projects:
            if target in p["hash"] or target in p["path_hint"]:
                proj_dir = projects_dir / p["hash"]
                break
        if not proj_dir:
            print(f"❌ 未找到匹配的项目：{target}")
            sys.exit(1)

    since = parse_since(args.since) if args.since else None
    print(f"\n⏳ 正在读取项目会话...")

    messages = load_project_sessions(proj_dir, since=since)

    if not messages:
        print("⚠️  未提取到任何有效消息（可能被 --since 过滤或文件格式不符）")
        sys.exit(0)

    # 找对应的 path_hint
    matched = next((p for p in projects if (projects_dir / p["hash"]) == proj_dir), {})
    project_path = matched.get("path_hint", proj_dir.name)

    skeleton = format_skeleton(messages, project_path, max_chars=args.max_chars)

    if args.output:
        Path(args.output).write_text(skeleton, encoding="utf-8")
        print(f"✅ 骨架已写入：{args.output}")
    else:
        print(skeleton)


if __name__ == "__main__":
    main()
