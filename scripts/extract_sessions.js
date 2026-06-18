#!/usr/bin/env node
/*
 * extract_sessions.js
 * 从 Claude Code 的 .jsonl 会话文件中提取对话骨架（Node 版，零依赖）。
 * 与 extract_sessions.py 行为一致——有 Node 没 Python 时用它，反之用 .py。
 *
 * Usage:
 *   node extract_sessions.js --list
 *   node extract_sessions.js --project <序号或hash> [--since 7d] [--output out.md] [--max-chars 0]
 */

const fs = require("fs");
const os = require("os");
const path = require("path");

// ── 跨平台路径 ───────────────────────────────────────────────────────────────
function getClaudeProjectsDir() {
  if (process.platform === "win32") {
    const base = process.env.APPDATA || os.homedir();
    return path.join(base, "Claude", "projects");
  }
  return path.join(os.homedir(), ".claude", "projects");
}

// ── 工具：本地时间格式化（CC 时间戳为 UTC，统一转本地，与会话标题一致）──────────
function pad2(n) { return String(n).padStart(2, "0"); }
function fmtDateTime(d) {
  return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())} ${pad2(d.getHours())}:${pad2(d.getMinutes())}`;
}
function fmtTime(d) { return `${pad2(d.getHours())}:${pad2(d.getMinutes())}`; }

function listJsonl(dir) {
  let entries;
  try { entries = fs.readdirSync(dir); } catch { return []; }
  return entries
    .filter((f) => f.endsWith(".jsonl"))
    .map((f) => path.join(dir, f))
    .map((p) => ({ p, mtime: fs.statSync(p).mtimeMs }))
    .sort((a, b) => a.mtime - b.mtime); // 旧 → 新
}

// ── 项目发现 ─────────────────────────────────────────────────────────────────
function discoverProjects(projectsDir) {
  let dirs;
  try { dirs = fs.readdirSync(projectsDir, { withFileTypes: true }); } catch { return []; }

  const results = [];
  for (const ent of dirs) {
    if (!ent.isDirectory()) continue;
    const projDir = path.join(projectsDir, ent.name);
    const files = listJsonl(projDir);
    if (files.length === 0) continue;
    const latestMtime = Math.max(...files.map((f) => f.mtime));
    results.push({
      hash: ent.name,
      pathHint: guessProjectPath(files) || "(unknown)",
      latestMtime,
      sessionCount: files.length,
    });
  }
  results.sort((a, b) => b.latestMtime - a.latestMtime); // 最近活跃优先
  return results;
}

function guessProjectPath(files) {
  for (let i = files.length - 1; i >= 0; i--) { // 最新文件更可能有 cwd
    let lines;
    try { lines = fs.readFileSync(files[i].p, "utf-8").split("\n"); } catch { continue; }
    for (const line of lines) {
      const s = line.trim();
      if (!s) continue;
      let rec;
      try { rec = JSON.parse(s); } catch { continue; }
      const cwd = rec.cwd || rec.workingDirectory;
      if (cwd) return cwd;
    }
  }
  return null;
}

function printProjectList(projects) {
  console.log("\n📂 Claude Code 项目列表（按最近活跃排序）\n");
  console.log(`  ${"#".padEnd(4)} ${"最近活跃".padEnd(20)} ${"会话数".padEnd(6)} 项目路径`);
  console.log("  " + "─".repeat(75));
  projects.forEach((p, i) => {
    const dt = fmtDateTime(new Date(p.latestMtime));
    console.log(`  ${String(i + 1).padEnd(4)} ${dt.padEnd(20)} ${String(p.sessionCount).padEnd(6)} ${p.pathHint}`);
  });
  console.log("");
}

// ── 消息提取 ─────────────────────────────────────────────────────────────────
const MIN_TEXT_LENGTH = 20;
const NOISE_PREFIXES = [
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
];
function isNoise(text) {
  const s = text.replace(/^\s+/, "");
  return NOISE_PREFIXES.some((p) => s.startsWith(p));
}

function extractTextContent(content) {
  if (typeof content === "string") {
    const s = content.trim();
    return s.length >= MIN_TEXT_LENGTH ? s : null;
  }
  if (Array.isArray(content)) {
    const parts = [];
    for (const block of content) {
      if (!block || typeof block !== "object") continue;
      const t = block.type || "";
      if (t === "tool_use" || t === "tool_result" || t === "thinking") continue;
      if (t === "text") {
        const txt = (block.text || "").trim();
        if (txt) parts.push(txt);
      }
    }
    const combined = parts.join("\n").trim();
    return combined.length >= MIN_TEXT_LENGTH ? combined : null;
  }
  return null;
}

function parseTimestamp(record) {
  for (const key of ["timestamp", "createdAt", "created_at", "ts"]) {
    const val = record[key];
    if (!val) continue;
    if (typeof val === "number") {
      return new Date(val > 1e10 ? val : val * 1000);
    }
    const d = new Date(String(val)); // ISO（含 Z）→ JS Date，本地格式化时即为本地时区
    if (!isNaN(d.getTime())) return d;
  }
  return null;
}

function extractFromJsonl(filepath) {
  const messages = [];
  const fileMtime = new Date(fs.statSync(filepath).mtimeMs);
  let lines;
  try { lines = fs.readFileSync(filepath, "utf-8").split("\n"); }
  catch (e) { process.stderr.write(`  ⚠️  读取 ${path.basename(filepath)} 时出错: ${e.message}\n`); return messages; }

  for (const line of lines) {
    const s = line.trim();
    if (!s) continue;
    let record;
    try { record = JSON.parse(s); } catch { continue; }

    const recordType = record.type;
    if (!["user", "assistant", "message"].includes(recordType)) continue;

    // 结构化过滤：子代理对话 / 系统元消息
    if (record.isSidechain || record.isMeta) continue;

    const msg = (record.message && typeof record.message === "object") ? record.message : record;
    const role = msg.role || record.role;
    if (!["user", "assistant", "human"].includes(role)) continue;

    const content = msg.content;
    if (content == null) continue;

    const text = extractTextContent(content);
    if (!text) continue;

    if ((role === "user" || role === "human") && isNoise(text)) continue;

    const ts = parseTimestamp(record) || fileMtime;
    messages.push({
      role: role === "user" || role === "human" ? "human" : "assistant",
      text,
      timestamp: ts,
    });
  }
  return messages;
}

function loadProjectSessions(projDir, since) {
  let files = listJsonl(projDir);
  if (since) files = files.filter((f) => f.mtime >= since.getTime());

  const all = [];
  for (const f of files) {
    const msgs = extractFromJsonl(f.p);
    if (msgs.length === 0) continue;
    const sessionId = path.basename(f.p, ".jsonl").slice(0, 8);
    // 会话起点用最早一条消息的真实时间戳，而非 mtime（resume 会让 mtime 失真）
    const sessionStart = new Date(Math.min(...msgs.map((m) => m.timestamp.getTime())));
    for (const m of msgs) { m.sessionId = sessionId; m.sessionStart = sessionStart; }
    all.push(...msgs);
  }
  all.sort((a, b) => a.timestamp - b.timestamp);
  return all;
}

// ── 骨架格式化 ───────────────────────────────────────────────────────────────
function formatSkeleton(messages, projectPath, maxChars = 0) {
  const lines = [
    `# 开发过程骨架 — ${projectPath}`,
    `_生成时间：${fmtDateTime(new Date())}_`,
    `_共 ${messages.length} 条对话消息_\n`,
  ];
  let current = null;
  for (const m of messages) {
    if (m.sessionId !== current) {
      current = m.sessionId;
      lines.push(`\n## 会话 ${m.sessionId}  ·  ${fmtDateTime(m.sessionStart)}\n`);
    }
    const roleLabel = m.role === "human" ? "👤 用户" : "🤖 Claude";
    let text = m.text;
    if (maxChars && text.length > maxChars) text = text.slice(0, maxChars) + "…（已截断）";
    lines.push(`**${roleLabel}** \`${fmtTime(m.timestamp)}\`\n${text}\n`);
  }
  return lines.join("\n");
}

// ── 参数解析 ─────────────────────────────────────────────────────────────────
function parseSince(str) {
  const m = /^(\d+)d$/.exec(str);
  if (m) return new Date(Date.now() - parseInt(m[1], 10) * 86400000);
  const d = new Date(str);
  return isNaN(d.getTime()) ? null : d;
}

function parseArgs(argv) {
  const args = { list: false, project: null, since: null, output: null, maxChars: 0 };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--list") args.list = true;
    else if (a === "--project") args.project = argv[++i];
    else if (a === "--since") args.since = argv[++i];
    else if (a === "--output") args.output = argv[++i];
    else if (a === "--max-chars") args.maxChars = parseInt(argv[++i], 10) || 0;
  }
  return args;
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  const projectsDir = getClaudeProjectsDir();
  const projects = discoverProjects(projectsDir);

  if (projects.length === 0) {
    console.log(`❌ 未找到任何 Claude Code 项目，请确认 ${projectsDir} 存在`);
    process.exit(1);
  }

  if (args.list || !args.project) {
    printProjectList(projects);
    if (!args.project) console.log("👉 使用方式：node extract_sessions.js --project <序号或hash> [--since 7d]");
    return;
  }

  const target = String(args.project).trim();
  let projHash = null;
  if (/^\d+$/.test(target)) {
    const idx = parseInt(target, 10) - 1;
    if (idx >= 0 && idx < projects.length) projHash = projects[idx].hash;
    else { console.log(`❌ 序号 ${target} 超出范围（共 ${projects.length} 个项目）`); process.exit(1); }
  } else {
    const hit = projects.find((p) => p.hash.includes(target) || p.pathHint.includes(target));
    if (hit) projHash = hit.hash;
    else { console.log(`❌ 未找到匹配的项目：${target}`); process.exit(1); }
  }

  const projDir = path.join(projectsDir, projHash);
  const since = args.since ? parseSince(args.since) : null;
  console.log("\n⏳ 正在读取项目会话...");

  const messages = loadProjectSessions(projDir, since);
  if (messages.length === 0) {
    console.log("⚠️  未提取到任何有效消息（可能被 --since 过滤或文件格式不符）");
    process.exit(0);
  }

  const matched = projects.find((p) => p.hash === projHash) || {};
  const projectPath = matched.pathHint || projHash;
  const skeleton = formatSkeleton(messages, projectPath, args.maxChars);

  if (args.output) {
    fs.writeFileSync(args.output, skeleton, "utf-8");
    console.log(`✅ 骨架已写入：${args.output}`);
  } else {
    console.log(skeleton);
  }
}

main();
