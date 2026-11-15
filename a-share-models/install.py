#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把本仓库的 A 股分析「调用层」安装到用户级 WorkBuddy 技能目录。

    python install.py             # 安装（已存在的文件默认跳过，不覆盖本地修改）
    python install.py --force     # 覆盖，覆盖前自动备份为 .bak-<时间戳>
    python install.py --check     # 只检查安装状态，不写文件
    python install.py --uninstall # 移除本技能安装的文件（保留目录）

安装位置：<用户主目录>/.workbuddy/skills/a-share-analysis-models/
跨平台：Windows / macOS / Linux，纯标准库，无第三方依赖。
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL_NAME = "a-share-analysis-models"
FILES = ["SKILL.md", "registry.json", "models.py", "projects.json"]
TARGET = Path.home() / ".workbuddy" / "skills" / SKILL_NAME


def stamp():
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def render_skill_md(text):
    """把仓库版里的可移植占位符替换为本机真实主目录（Windows 统一用正斜杠）。"""
    return text.replace("<用户主目录>", str(Path.home()).replace("\\", "/"))


def check():
    print(f"目标目录: {TARGET}")
    ok = True
    for f in FILES:
        src, dst = HERE / f, TARGET / f
        state = "OK" if dst.exists() else "MISSING"
        if state == "MISSING":
            ok = False
        print(f"  {f:<16} {state:<8} (源文件: {'存在' if src.exists() else '缺失'})")
    print("安装状态:", "已安装" if ok else "未完整安装")
    return 0 if ok else 1


def install(force=False):
    missing = [f for f in FILES if not (HERE / f).exists()]
    if missing:
        print(f"[ERROR] 缺少源文件: {missing}", file=sys.stderr)
        return 2
    TARGET.mkdir(parents=True, exist_ok=True)
    for f in FILES:
        src, dst = HERE / f, TARGET / f
        if dst.exists() and not force:
            print(f"  SKIP    {f} (已存在，--force 可覆盖)")
            continue
        if dst.exists() and force:
            bak = dst.with_name(dst.name + f".bak-{stamp()}")
            shutil.copy2(dst, bak)
            print(f"  BACKUP  -> {bak.name}")
        if f == "SKILL.md":
            dst.write_text(render_skill_md(src.read_text(encoding="utf-8")), encoding="utf-8")
            print(f"  INSTALL {f} (路径已渲染为本机)")
        else:
            shutil.copy2(src, dst)
            print(f"  INSTALL {f}")
    print(f"\n已安装到: {TARGET}")
    print("验证: python", str(TARGET / "models.py"), "selftest")
    print("查看路由: python", str(TARGET / "models.py"), "route sector_pick")
    print("\n后续任何股票分析任务，WorkBuddy 会按 SKILL.md 的触发词自动加载本技能。")
    return 0


def uninstall():
    if not TARGET.exists():
        print("未安装，无需卸载")
        return 0
    for f in FILES:
        p = TARGET / f
        if p.exists():
            p.unlink()
            print(f"  REMOVE  {f}")
    print(f"已移除安装文件，目录保留: {TARGET}")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--force", action="store_true", help="覆盖已存在文件（自动备份）")
    ap.add_argument("--check", action="store_true", help="只检查安装状态")
    ap.add_argument("--uninstall", action="store_true", help="卸载安装文件")
    a = ap.parse_args()
    if a.uninstall:
        return uninstall()
    if a.check:
        return check()
    return install(a.force)


if __name__ == "__main__":
    sys.exit(main())
