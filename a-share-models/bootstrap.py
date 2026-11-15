#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
按需拉取四个上游分析项目的源码（git submodule）。

    python bootstrap.py --status                 # 查看各项目初始化状态
    python bootstrap.py                         # 初始化 3 个宽松许可项目（浅克隆）
    python bootstrap.py --all --accept-proprietary-license
                                                # 额外初始化 TradingAgents-CN（须先阅读其 LICENSE）
    python bootstrap.py --update                # 把 submodule 更新到上游最新 HEAD 并打印新 SHA
    python bootstrap.py --commands              # 只输出可复制的命令，不执行（受限环境用）
    python bootstrap.py --dry-run               # 打印将执行的命令

说明：
  - 主仓库只存 gitlink（commit 引用）+ .gitmodules，不复制任何上游源码。
  - 源码体积合计约 244 MB，因此采用 --depth 1 浅克隆；--all 会显著增加下载量。
  - 若运行环境不允许 Python 启动 git 子进程，脚本会打印全部命令供在终端手动执行。
  - 本脚本只拉源码，不安装 pip 依赖、不配置 API Key、不启动服务。
    各项目的部署门槛见 projects.json -> deploy_blockers。
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
# Windows 原生 Python 下，PATH 中的 git shim 有时无法被 CreateProcess 直接执行，
# 因此优先解析成绝对路径（Git for Windows / PortableGit 的 git.exe）。
GIT = shutil.which("git") or shutil.which("git.exe") or "git"
SPAWN_BLOCKED = False
COMMAND_LINES = []


def load():
    with open(HERE / "projects.json", encoding="utf-8") as f:
        return json.load(f)["projects"]


def run_git(args, cwd=REPO, quiet=False):
    """返回 (returncode, output)；失败时返回 (1, 错误文本)，不抛异常。"""
    try:
        r = subprocess.run([GIT, *args], cwd=cwd, text=True,
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        return r.returncode, r.stdout or ""
    except OSError as e:
        return 1, f"{type(e).__name__}: {e}"


def git(*args, dry=False, commands_only=False):
    global SPAWN_BLOCKED
    line = "git " + " ".join(args)
    print("  $", line)
    COMMAND_LINES.append(line)
    if dry or commands_only:
        return 0
    rc, out = run_git(args)
    if rc == 1 and out.startswith(("PermissionError", "OSError", "FileNotFoundError")):
        SPAWN_BLOCKED = True
        print("    [环境限制] 当前进程无法启动 git，命令已保留供手动执行")
        return 0
    if out.strip():
        for ln in out.strip().splitlines()[:12]:
            print("    ", ln)
    return rc


def status(projects):
    print("=== submodule 状态 ===")
    rc, out = run_git(["submodule", "status"])
    if rc == 0:
        print(out.strip() or "(无 submodule 记录)")
    else:
        print(f"[环境限制] 无法查询（{out.strip()[:80]}）")
        print("可在终端手动执行: git submodule status")
    print("\n=== 项目 ===")
    for p in projects:
        d = REPO / p["path"]
        initialized = (d / ".git").exists() or d.joinpath(".git").is_file()
        flag = "已初始化" if initialized else "未初始化"
        print(f"  {p['repo']:<38} {flag:<10} {p['license']}")
        if p.get("requires_confirmation"):
            print(f"    ! {p['license_warning']}")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--all", action="store_true", help="包含需许可确认的项目")
    ap.add_argument("--accept-proprietary-license", action="store_true",
                    help="确认已阅读并接受 TradingAgents-CN 的混合许可")
    ap.add_argument("--update", action="store_true", help="更新到上游最新 HEAD")
    ap.add_argument("--status", action="store_true", help="只查看状态")
    ap.add_argument("--commands", action="store_true", help="只输出命令，不执行")
    ap.add_argument("--dry-run", action="store_true", help="打印将执行的命令")
    a = ap.parse_args()

    projects = load()
    if a.status:
        return status(projects)

    if a.all and not a.accept_proprietary_license:
        print("[BLOCKED] --all 会拉取 TradingAgents-CN，其应用层为专有许可。", file=sys.stderr)
        print("请先阅读 https://github.com/hsliuping/TradingAgents-CN/blob/v3.0/LICENSE", file=sys.stderr)
        print("确认后再加 --accept-proprietary-license。其余 3 个项目未受影响。", file=sys.stderr)
        return 2

    targets = [p for p in projects if a.all or p.get("auto_init", False)]
    print(f"=== 处理 {len(targets)} 个项目（git = {GIT}）===")
    if not (a.dry_run or a.commands):
        git("submodule", "sync", commands_only=a.commands)

    for p in targets:
        print(f"\n[{p['repo']}]  license={p['license']}  pinned={p['pinned_sha'][:12]}")
        for b in p.get("deploy_blockers", []):
            print(f"  - 门槛: {b}")
        args = ["submodule", "update", "--init"]
        if a.update:
            args.append("--remote")
        args += ["--depth", "1", p["path"]]
        rc = git(*args, dry=a.dry_run, commands_only=a.commands)
        if rc not in (0, 1):
            print(f"  [WARN] 返回码 {rc}，该项目可能未成功初始化")

    if a.update and not (a.dry_run or a.commands) and not SPAWN_BLOCKED:
        print("\n=== 上游最新 SHA（请手工同步到 projects.json 并提交以固定新版本）===")
        rc, out = run_git(["submodule", "status"])
        print(out.strip()[:600])
        print("提示：submodule HEAD 变化会使主仓库出现 modified 记录，需 git add + commit 才会固定。")

    if not a.all:
        skipped = [p["repo"] for p in projects if not p.get("auto_init", False)]
        print(f"\n跳过（需显式确认）: {', '.join(skipped)}")
        print("如确需使用: python bootstrap.py --all --accept-proprietary-license")

    if SPAWN_BLOCKED or a.commands:
        print("\n=== 请在终端按顺序执行以下命令 ===")
        for ln in COMMAND_LINES:
            print("  ", ln)
        print("（当前环境不允许 Python 启动 git 子进程，故未自动执行）")

    print("\n注意：源码就位不等于可运行。依赖、API Key、数据库请按各项目 README 另行配置。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
