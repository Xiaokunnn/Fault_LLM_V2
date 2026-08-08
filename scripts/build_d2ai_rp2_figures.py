#!/usr/bin/env python3
"""Create publication figures for the RP2 D2AI Chinese review draft."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT / "papers/D2AI_ICDM_2026/figures"


def _font() -> font_manager.FontProperties:
    candidates = [
        Path("C:/Windows/Fonts/NotoSansSC-VF.ttf"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
        Path("/usr/share/fonts/truetype/noto/NotoSansSC-Regular.otf"),
    ]
    for path in candidates:
        if path.exists():
            return font_manager.FontProperties(fname=str(path))
    return font_manager.FontProperties(family="DejaVu Sans")


FONT = _font()
COLORS = {
    "navy": "#1F4E79",
    "blue": "#4C78A8",
    "cyan": "#72B7B2",
    "orange": "#F28E2B",
    "green": "#2A9D8F",
    "red": "#D1495B",
    "gray": "#6B7280",
    "light": "#F4F7FA",
    "ink": "#172033",
}


def _box(ax, xy, width, height, text, *, face, edge=None, fontsize=9.2,
         weight="normal", radius=0.018, align="center"):
    edge = edge or face
    patch = FancyBboxPatch(
        xy,
        width,
        height,
        boxstyle=f"round,pad=0.008,rounding_size={radius}",
        linewidth=1.2,
        edgecolor=edge,
        facecolor=face,
        transform=ax.transAxes,
        clip_on=False,
    )
    ax.add_patch(patch)
    x = xy[0] + (width / 2 if align == "center" else 0.018)
    ax.text(
        x,
        xy[1] + height / 2,
        text,
        ha=align,
        va="center",
        fontsize=fontsize,
        fontproperties=FONT,
        fontweight=weight,
        color=COLORS["ink"],
        transform=ax.transAxes,
        linespacing=1.22,
    )
    return patch


def _arrow(ax, start, end, *, color=None, style="-|>", lw=1.25):
    arrow = FancyArrowPatch(
        start,
        end,
        arrowstyle=style,
        mutation_scale=11,
        linewidth=lw,
        color=color or COLORS["gray"],
        transform=ax.transAxes,
        connectionstyle="arc3,rad=0.0",
        clip_on=False,
    )
    ax.add_patch(arrow)


def build_pipeline_example(output_dir: Path) -> None:
    fig, ax = plt.subplots(figsize=(6.4, 7.4), dpi=240)
    ax.set_axis_off()
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)

    ax.text(
        0.01, 0.985, "(a) 来源可追溯的预算化向量—图查询流水线",
        ha="left", va="top", fontsize=11.2, fontproperties=FONT,
        fontweight="bold", color=COLORS["navy"], transform=ax.transAxes,
    )

    _box(ax, (0.03, 0.855), 0.43, 0.085,
         "证据图：Entity—Claim—Assertion\n页码 · URL · 哈希 · 来源族",
         face="#EAF2F8", edge=COLORS["blue"], fontsize=8.8)
    _box(ax, (0.54, 0.855), 0.43, 0.085,
         "BGE-M3 向量索引\n208条证据 · 1024维",
         face="#EAF7F6", edge=COLORS["green"], fontsize=8.8)

    _box(ax, (0.02, 0.70), 0.17, 0.075, "结构化查询\nq=(x,f,r)",
         face="#FFF4E6", edge=COLORS["orange"], fontsize=9.0, weight="bold")
    _box(ax, (0.235, 0.70), 0.18, 0.075, "Dense Top-32\n前8条作图锚点",
         face="#F2F5F9", edge=COLORS["blue"], fontsize=8.7)
    _box(ax, (0.46, 0.70), 0.22, 0.075, "角色门控 + 一跳传播\n故障实体词面相似度",
         face="#F2F5F9", edge=COLORS["cyan"], fontsize=8.5)
    _box(ax, (0.73, 0.70), 0.24, 0.075, "边际得分选择\n最大证据预算 K=3",
         face="#F2F5F9", edge=COLORS["green"], fontsize=8.7)
    _arrow(ax, (0.19, 0.738), (0.235, 0.738))
    _arrow(ax, (0.415, 0.738), (0.46, 0.738))
    _arrow(ax, (0.68, 0.738), (0.73, 0.738))
    _arrow(ax, (0.25, 0.855), (0.56, 0.775), color=COLORS["blue"])
    _arrow(ax, (0.76, 0.855), (0.34, 0.775), color=COLORS["green"])

    _box(ax, (0.10, 0.535), 0.22, 0.078, "Qwen2.5-7B\n首阶段0/1掩码",
         face="#FCECEF", edge=COLORS["red"], fontsize=8.8)
    _box(ax, (0.39, 0.535), 0.22, 0.078, "对首阶段0项\n逐条召回复核",
         face="#FCECEF", edge=COLORS["red"], fontsize=8.8)
    _box(ax, (0.68, 0.535), 0.22, 0.078, "确定性渲染器\nClaim + evidence ID",
         face="#EDF8F3", edge=COLORS["green"], fontsize=8.8)
    _arrow(ax, (0.85, 0.70), (0.28, 0.613))
    _arrow(ax, (0.32, 0.574), (0.39, 0.574))
    _arrow(ax, (0.61, 0.574), (0.68, 0.574))
    _box(ax, (0.31, 0.415), 0.38, 0.072,
         "有限回答（逐点可追溯）  或  明确拒答",
         face="#E9F7EF", edge=COLORS["green"], fontsize=9.0, weight="bold")
    _arrow(ax, (0.79, 0.535), (0.59, 0.487), color=COLORS["green"])

    ax.plot([0.02, 0.98], [0.375, 0.375], color="#D1D5DB", lw=1.0,
            transform=ax.transAxes)
    ax.text(
        0.01, 0.35, "(b) 真实查询 CQ-F07-SYM：泵—电机不对中有哪些症状？",
        ha="left", va="top", fontsize=10.8, fontproperties=FONT,
        fontweight="bold", color=COLORS["navy"], transform=ax.transAxes,
    )

    _box(ax, (0.03, 0.195), 0.43, 0.115,
         "Dense K3\n原因 · 维护 · 检查（角色均不匹配）\n7B掩码 [0,0,0] → 拒答",
         face="#FFF1F2", edge=COLORS["red"], fontsize=8.7)
    _box(ax, (0.54, 0.195), 0.43, 0.115,
         "Full K3（主动欠填为2条）\n症状证据：DESMI + ABS\n7B掩码 [1,1] → 两条可追溯回答",
         face="#ECFDF5", edge=COLORS["green"], fontsize=8.7)

    ax.text(
        0.54, 0.145,
        "输出：振动水平>7 mm/s提示部件寿命缩短；\n联轴器旁轴承高温提示轴轻微不对中。",
        ha="left", va="top", fontsize=8.5, fontproperties=FONT,
        color=COLORS["ink"], transform=ax.transAxes, linespacing=1.28,
    )
    ax.text(
        0.03, 0.062,
        "每条回答携带 evidence ID，并可回溯原文、PDF页码、URL与哈希。",
        ha="left", va="bottom", fontsize=8.5, fontproperties=FONT,
        color=COLORS["gray"], transform=ax.transAxes,
    )

    fig.tight_layout(pad=0.35)
    for suffix in ("png", "svg"):
        fig.savefig(output_dir / f"rp2_v6_pipeline_example.{suffix}",
                    dpi=320 if suffix == "png" else None,
                    bbox_inches="tight", facecolor="white")
    plt.close(fig)


def build_quality_latency(output_dir: Path) -> None:
    methods = ["Dense K3", "Role K3", "Role+Graph K3", "Full K3", "Dense K4"]
    latency = [839.4, 782.1, 805.5, 531.2, 1092.7]
    f1 = [0.259, 0.372, 0.377, 0.426, 0.287]
    colors = [COLORS["blue"], COLORS["orange"], COLORS["cyan"],
              COLORS["green"], COLORS["gray"]]

    fig, ax = plt.subplots(figsize=(6.2, 3.75), dpi=240)
    for idx, (name, x, y, color) in enumerate(zip(methods, latency, f1, colors)):
        if name == "Dense K4":
            ax.scatter(x, y, s=95, facecolors="white", edgecolors=color,
                       linewidths=1.8, marker="o", zorder=3)
        elif name == "Full K3":
            ax.scatter(x, y, s=145, color=color, edgecolors="white",
                       linewidths=0.8, marker="*", zorder=4)
        else:
            ax.scatter(x, y, s=75, color=color, edgecolors="white",
                       linewidths=0.7, zorder=3)
        offsets = {
            "Dense K3": (8, -15), "Role K3": (-64, 9),
            "Role+Graph K3": (8, 7), "Full K3": (8, 7),
            "Dense K4": (-58, 8),
        }
        ax.annotate(name, (x, y), xytext=offsets[name], textcoords="offset points",
                    fontsize=8.7, fontproperties=FONT, color=COLORS["ink"])

    # Connect only the progressive equal-budget K=3 system variants.
    order = [0, 1, 2, 3]
    ax.plot([latency[i] for i in order], [f1[i] for i in order],
            color="#AAB2BD", lw=1.0, ls="--", zorder=1)
    ax.annotate("更优区域", xy=(535, 0.455), xytext=(680, 0.455),
                arrowprops=dict(arrowstyle="->", color=COLORS["green"], lw=1.2),
                fontsize=9.0, fontproperties=FONT, color=COLORS["green"])

    ax.set_xlabel("平均端到端时延（ms，越低越好）", fontproperties=FONT, fontsize=9.2)
    ax.set_ylabel("Silver 引用 F1（越高越好）", fontproperties=FONT, fontsize=9.2)
    ax.set_xlim(480, 1150)
    ax.set_ylim(0.22, 0.48)
    ax.grid(True, color="#E5E7EB", linewidth=0.7)
    ax.set_axisbelow(True)
    for tick in ax.get_xticklabels() + ax.get_yticklabels():
        tick.set_fontproperties(FONT)
        tick.set_fontsize(8.2)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout(pad=0.7)
    for suffix in ("png", "svg"):
        fig.savefig(output_dir / f"rp2_v6_quality_latency.{suffix}",
                    dpi=320 if suffix == "png" else None,
                    bbox_inches="tight", facecolor="white")
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    build_pipeline_example(output_dir)
    build_quality_latency(output_dir)
    print(f"Created RP2 paper figures in {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
