"""
analysis/plot_trial.py — 澄清对照实验专用可视化

读取 results/trial/trial_thoughts_*.csv，生成 6 张图：

  图1  trust_trajectory.png      信任轨迹对比（全员均值 + 按人群 2×2）
  图2  affective_heatmap.png     情绪冲击热力图（人群 × Tick）
  图3  clarification_spotlight.png  澄清窗口放大视图（信任+冲击+虚伪感知）
  图4  action_timeline.png       行为时间线（买/帖/忽视比例 × Tick × 人群）
  图5  delta_recovery_bar.png    各组核心指标对比（ΔRecovery / AUC / Speed）
  图6  thought_scatter.png       情绪冲击 × 信任变化散点（按人群着色）

用法：
    python analysis/plot_trial.py                    # 读取最新 trial，出全部图
    python analysis/plot_trial.py --file <path.csv>  # 指定文件
    python analysis/plot_trial.py --mode trust       # 仅图1
    python analysis/plot_trial.py --mode all         # 全部（默认）
"""
import os, sys, glob, argparse, warnings
warnings.filterwarnings("ignore")

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.gridspec as gridspec
from matplotlib.colors import TwoSlopeNorm

ROOT      = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRIAL_DIR = os.path.join(ROOT, "results", "trial")
# OUT_DIR 可由调用方（run_clarification_trial.py）在 import 后注入带时间戳的路径
# 独立运行时默认读 latest/
OUT_DIR   = os.path.join(TRIAL_DIR, "latest", "figures")

plt.rcParams["font.sans-serif"] = ["SimHei", "Arial Unicode MS", "Arial"]
plt.rcParams["axes.unicode_minus"] = False

# ── 样式 ──────────────────────────────────────────────────────────────
CMETA = {
    "Active_Greens":     {"label": "Active Greens",     "color": "#2166ac", "marker": "o"},
    "Convenient_Greens": {"label": "Convenient Greens", "color": "#4dac26", "marker": "s"},
    "Dormant_Greens":    {"label": "Dormant Greens",    "color": "#f46d43", "marker": "^"},
    "Non_Greens":        {"label": "Non-Greens",        "color": "#999999", "marker": "D"},
}
CORD = ["Active_Greens", "Convenient_Greens", "Dormant_Greens", "Non_Greens"]

def _gc(grp: str) -> str:
    if "No-Clr" in grp:  return "#d62728"
    if "RAT"   in grp:   return "#2166ac"
    if "EMO"   in grp:   return "#e6550d"
    return "#888888"

def _gls(grp: str) -> str:
    return "--" if "No-Clr" in grp else "-"

# ══════════════════════════════════════════════════════════════════════
# 数据加载
# ══════════════════════════════════════════════════════════════════════
def load_data(csv_path: str = None) -> pd.DataFrame:
    if csv_path:
        path = csv_path
    else:
        files = sorted(glob.glob(os.path.join(TRIAL_DIR, "trial_thoughts_*.csv")),
                       key=os.path.getctime, reverse=True)
        if not files:
            print(f"❌ 未找到 trial_thoughts_*.csv in {TRIAL_DIR}")
            sys.exit(1)
        path = files[0]

    print(f"📂 读取: {os.path.basename(path)}")
    df = pd.read_csv(path)

    for col in ["trust_score", "affective_change", "trust_after_decay",
                "shock_anchor", "importance", "quiet_ticks"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    for col in ["is_buying", "is_posting", "hypocrisy_perceived", "is_clarification_tick"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.lower().map(
                {"true": True, "false": False, "1": True, "0": False}
            ).fillna(False)

    print(f"   Groups : {df['group'].unique().tolist()}")
    print(f"   Ticks  : {df['tick'].min()} – {df['tick'].max()}")
    print(f"   Agents : {df['agent_id'].nunique()}")
    return df


def _infer_events(df: pd.DataFrame):
    """从数据中推断丑闻 Tick 和澄清 Tick"""
    clr_ticks = sorted(df.loc[df["is_clarification_tick"] == True, "tick"].unique().tolist())
    # 丑闻是非澄清的第一个负向冲击大 Tick——简单取最大负均值 Tick
    neg = df.groupby("tick")["affective_change"].mean()
    scandal_tick = int(neg.idxmin()) if not neg.empty else 5
    return scandal_tick, clr_ticks


def _save(fig, name: str) -> str:
    os.makedirs(OUT_DIR, exist_ok=True)
    out = os.path.join(OUT_DIR, name)
    fig.savefig(out, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"  ✅ {name}")
    return out


# ══════════════════════════════════════════════════════════════════════
# 图1：信任轨迹对比（全员均值 + 按人群 2×2）
# ══════════════════════════════════════════════════════════════════════
def plot_trust_trajectory(df: pd.DataFrame):
    groups      = df["group"].unique().tolist()
    scandal_tick, clr_ticks = _infer_events(df)
    total_ticks = int(df["tick"].max())

    ctrl  = next((g for g in groups if "No-Clr" in g), groups[0])
    clrs  = [g for g in groups if g != ctrl]

    fig   = plt.figure(figsize=(15, 4.5 + 4.5 * len(clrs)))
    rows  = 1 + len(clrs)
    gs    = gridspec.GridSpec(rows, 2, figure=fig, hspace=0.45, wspace=0.3)

    def _vlines(ax):
        ylim = ax.get_ylim()
        span = ylim[1] - ylim[0]
        ax.axvline(scandal_tick, color="#d62728", ls="--", lw=1.5, alpha=0.7)
        ax.text(scandal_tick + 0.15, ylim[0] + span * 0.04,
                f"Scandal\n(T{scandal_tick})", color="#d62728", fontsize=8, va="bottom")
        for ct in clr_ticks:
            ax.axvspan(ct - 0.45, ct + 0.45, alpha=0.10, color="#2ca02c")
            ax.text(ct + 0.15, ylim[0] + span * 0.55,
                    f"Clr\n(T{ct})", color="#2ca02c", fontsize=8, va="bottom")

    # ── 行0：全员均值 ─────────────────────────────────────────────────
    ax0 = fig.add_subplot(gs[0, :])
    for grp in groups:
        traj = df[df["group"] == grp].groupby("tick")["trust_score"].mean()
        ax0.plot(traj.index, traj.values, color=_gc(grp), ls=_gls(grp),
                 lw=2.5, marker="o", ms=4, label=grp)
    ax0.set_ylim(bottom=0)
    _vlines(ax0)
    ax0.set_title("Average Trust Score — All Groups", fontsize=13, fontweight="bold")
    ax0.set_xlabel("Tick"); ax0.set_ylabel("Avg Trust (0–10)")
    ax0.legend(fontsize=9, loc="lower right"); ax0.grid(True, ls=":", alpha=0.4)
    ax0.set_xticks(range(1, total_ticks + 1, max(1, total_ticks // 15)))

    # ── 行1+：按人群 ──────────────────────────────────────────────────
    for ri, clr_grp in enumerate(clrs):
        for ci, (grp, title) in enumerate([(clr_grp, clr_grp), (ctrl, "Control (No-Clr)")]):
            ax = fig.add_subplot(gs[ri + 1, ci])
            for cluster in CORD:
                meta = CMETA.get(cluster, {"label": cluster, "color": "#888", "marker": "."})
                sub  = df[(df["group"] == grp) & (df["cluster_type"] == cluster)]
                if sub.empty: continue
                traj = sub.groupby("tick")["trust_score"].mean()
                ax.plot(traj.index, traj.values, color=meta["color"],
                        ls="-" if grp == clr_grp else "--", lw=1.8,
                        marker=meta["marker"], ms=3.5, label=meta["label"])
            ax.set_ylim(bottom=0)
            _vlines(ax)
            ax.set_title(f"{title} — by Segment", fontsize=10, fontweight="bold")
            ax.set_xlabel("Tick"); ax.set_ylabel("Trust")
            ax.legend(fontsize=7, loc="lower right", ncol=2)
            ax.grid(True, ls=":", alpha=0.4)

    return _save(fig, "fig1_trust_trajectory.png")


# ══════════════════════════════════════════════════════════════════════
# 图2：情绪冲击热力图（人群 × Tick，每个 group 一行）
# ══════════════════════════════════════════════════════════════════════
def plot_affective_heatmap(df: pd.DataFrame):
    groups = df["group"].unique().tolist()
    ticks  = sorted(df["tick"].unique())
    n_g    = len(groups)

    fig, axes = plt.subplots(n_g, 1, figsize=(max(12, len(ticks) * 0.7), 2.8 * n_g),
                             sharex=True)
    if n_g == 1: axes = [axes]
    fig.suptitle("Affective Impact Heatmap (by Segment × Tick)", fontsize=13, fontweight="bold")

    _, clr_ticks = _infer_events(df)
    scandal_tick, _ = _infer_events(df)

    for ax, grp in zip(axes, groups):
        pivot = df[df["group"] == grp].pivot_table(
            index="cluster_type", columns="tick",
            values="affective_change", aggfunc="mean"
        ).reindex(CORD)

        abs_max = max(abs(pivot.values[~np.isnan(pivot.values)]).max(), 0.1)
        norm = TwoSlopeNorm(vmin=-abs_max, vcenter=0, vmax=abs_max)
        im   = ax.imshow(pivot.values, cmap="RdYlGn", norm=norm, aspect="auto")

        # 数值标注
        for r in range(len(CORD)):
            for c_idx, t in enumerate(pivot.columns):
                val = pivot.values[r, c_idx]
                if not np.isnan(val):
                    ax.text(c_idx, r, f"{val:+.2f}", ha="center", va="center",
                            fontsize=7.5, color="black")

        ax.set_yticks(range(len(CORD)))
        ax.set_yticklabels([CMETA.get(c, {"label": c})["label"] for c in CORD], fontsize=9)
        ax.set_title(grp, fontsize=10, fontweight="bold", pad=4)

        # 事件竖线（转为格子坐标）
        tick_idx = {t: i for i, t in enumerate(pivot.columns)}
        if scandal_tick in tick_idx:
            ax.axvline(tick_idx[scandal_tick] - 0.5, color="#d62728", lw=2)
        for ct in clr_ticks:
            if ct in tick_idx:
                ax.axvline(tick_idx[ct] + 0.5, color="#2ca02c", lw=2, ls="--")

        plt.colorbar(im, ax=ax, shrink=0.8, label="Affective Δ")

    axes[-1].set_xticks(range(len(ticks)))
    axes[-1].set_xticklabels(ticks, fontsize=8)
    axes[-1].set_xlabel("Tick", fontsize=10)
    plt.tight_layout()
    return _save(fig, "fig2_affective_heatmap.png")


# ══════════════════════════════════════════════════════════════════════
# 图3：澄清窗口放大视图（±4 Ticks，3 子图：信任/冲击/虚伪感知比例）
# ══════════════════════════════════════════════════════════════════════
def plot_clarification_spotlight(df: pd.DataFrame):
    scandal_tick, clr_ticks = _infer_events(df)
    if not clr_ticks:
        print("  ⚠️  无澄清 Tick，跳过图3")
        return None

    ct     = clr_ticks[0]
    window = sorted([t for t in df["tick"].unique() if ct - 4 <= t <= ct + 4])
    sub    = df[df["tick"].isin(window)]
    groups = df["group"].unique().tolist()

    fig, axes = plt.subplots(3, 1, figsize=(13, 11), sharex=True)
    fig.suptitle(f"Clarification Spotlight — Window Tick {window[0]}–{window[-1]}",
                 fontsize=13, fontweight="bold")

    # ── 子图1：信任值 ──────────────────────────────────────────────────
    ax = axes[0]
    for grp in groups:
        traj = sub[sub["group"] == grp].groupby("tick")["trust_score"].mean()
        ax.plot(traj.index, traj.values, color=_gc(grp), ls=_gls(grp),
                lw=2, marker="o", ms=5, label=grp)
    ax.axvline(ct, color="#2ca02c", lw=2, ls="-", alpha=0.8, label=f"Clarification (T{ct})")
    ax.axvline(scandal_tick, color="#d62728", lw=1.5, ls="--", alpha=0.6)
    ax.set_ylabel("Avg Trust (0–10)"); ax.set_title("(A) Trust Score", fontsize=11)
    ax.legend(fontsize=8, loc="lower right"); ax.grid(True, ls=":", alpha=0.4)

    # ── 子图2：情绪冲击量 ──────────────────────────────────────────────
    ax = axes[1]
    for grp in groups:
        aff = sub[sub["group"] == grp].groupby("tick")["affective_change"].mean()
        ax.bar(aff.index + (groups.index(grp) - 1) * 0.2, aff.values,
               width=0.18, color=_gc(grp), alpha=0.75, label=grp)
    ax.axhline(0, color="black", lw=0.8, ls="--")
    ax.axvline(ct, color="#2ca02c", lw=2, ls="-", alpha=0.8)
    ax.set_ylabel("Avg Affective Δ"); ax.set_title("(B) Emotional Impact", fontsize=11)
    ax.legend(fontsize=8); ax.grid(True, axis="y", ls=":", alpha=0.4)

    # ── 子图3：虚伪感知比例 ────────────────────────────────────────────
    ax = axes[2]
    for grp in groups:
        hypo = sub[sub["group"] == grp].groupby("tick")["hypocrisy_perceived"].mean() * 100
        ax.plot(hypo.index, hypo.values, color=_gc(grp), ls=_gls(grp),
                lw=2, marker="^", ms=6, label=grp)
    ax.axvline(ct, color="#2ca02c", lw=2, ls="-", alpha=0.8)
    ax.set_ylim(0, 105)
    ax.set_ylabel("Hypocrisy Perceived (%)"); ax.set_title("(C) Hypocrisy Perception Rate", fontsize=11)
    ax.set_xlabel("Simulation Tick")
    ax.legend(fontsize=8); ax.grid(True, ls=":", alpha=0.4)
    ax.set_xticks(window)

    plt.tight_layout()
    return _save(fig, "fig3_clarification_spotlight.png")


# ══════════════════════════════════════════════════════════════════════
# 图4：行为时间线（BUY/POST/IGNORE 比例堆叠 × Tick，每 group 一行）
# ══════════════════════════════════════════════════════════════════════
def plot_action_timeline(df: pd.DataFrame):
    groups = df["group"].unique().tolist()
    scandal_tick, clr_ticks = _infer_events(df)
    n_g = len(groups)

    fig, axes = plt.subplots(n_g, 1, figsize=(14, 3.5 * n_g), sharex=True)
    if n_g == 1: axes = [axes]
    fig.suptitle("Behavior Timeline (BUY / POST / IGNORE Ratio per Tick)", fontsize=13, fontweight="bold")

    ACTION_C = {"BUY": "#2ca02c", "POST": "#d62728", "IGNORE": "#aec7e8"}

    for ax, grp in zip(axes, groups):
        gdf = df[df["group"] == grp].copy()
        gdf["IGNORE"] = (~gdf["is_buying"]) & (~gdf["is_posting"])
        cnt = gdf.groupby("tick").agg(
            BUY=("is_buying", "sum"), POST=("is_posting", "sum"),
            IGNORE=("IGNORE", "sum"), TOTAL=("agent_id", "count")
        )
        pct = cnt[["BUY", "POST", "IGNORE"]].div(cnt["TOTAL"], axis=0) * 100

        bottom = np.zeros(len(pct))
        ticks  = pct.index.values
        for action in ["BUY", "POST", "IGNORE"]:
            vals = pct[action].values
            ax.bar(ticks, vals, bottom=bottom, label=action,
                   color=ACTION_C[action], alpha=0.82, width=0.75)
            for xi, (v, b) in enumerate(zip(vals, bottom)):
                if v > 8:
                    ax.text(ticks[xi], b + v / 2, f"{v:.0f}%",
                            ha="center", va="center", fontsize=7.5, fontweight="bold",
                            color="white" if action != "IGNORE" else "#333")
            bottom += vals

        ax.axvline(scandal_tick, color="#d62728", lw=1.8, ls="--", alpha=0.6)
        for ct in clr_ticks:
            ax.axvline(ct, color="#2ca02c", lw=1.8, ls="-", alpha=0.6)
        ax.set_ylim(0, 102)
        ax.set_ylabel("Proportion (%)"); ax.set_title(grp, fontsize=11, fontweight="bold")
        ax.legend(fontsize=8, loc="upper right", ncol=3); ax.grid(axis="y", ls=":", alpha=0.3)

    axes[-1].set_xlabel("Simulation Tick")
    plt.tight_layout()
    return _save(fig, "fig4_action_timeline.png")


# ══════════════════════════════════════════════════════════════════════
# 图5：核心指标对比条形图（ΔRecovery / AUC / Speed，从轨迹数据计算）
# ══════════════════════════════════════════════════════════════════════
def plot_delta_recovery_bar(df: pd.DataFrame):
    """基于 trust_score 轨迹即时计算三核心指标，不依赖 metrics_calculator"""
    groups = df["group"].unique().tolist()
    scandal_tick, clr_ticks = _infer_events(df)

    results_list = []
    for grp in groups:
        traj = df[df["group"] == grp].groupby("tick")["trust_score"].mean().sort_index()
        vals = traj.values
        ticks_arr = traj.index.values

        # 最低点（丑闻后）
        post_start = np.searchsorted(ticks_arr, scandal_tick)
        if post_start >= len(vals): post_start = 0
        min_idx_local = int(np.argmin(vals[post_start:]))
        min_idx = post_start + min_idx_local
        trust_min = vals[min_idx]
        final_trust = vals[-1]

        delta_recovery = round(float(final_trust - trust_min), 4)

        # AUC（丑闻后梯形积分，归一化）
        post_vals = vals[post_start:]
        if len(post_vals) > 1:
            # np.trapz 在 NumPy ≥ 2.0 中被移除，改用 np.trapezoid；兼容旧版回退
            _trapz = getattr(np, "trapezoid", None) or getattr(np, "trapz")
            auc_raw = _trapz(post_vals) / (10.0 * (len(post_vals) - 1))
        else:
            auc_raw = 0.0

        # 恢复速度
        days = max(1, (len(vals) - 1) - min_idx)
        speed = round(delta_recovery / days, 4)

        results_list.append({
            "group": grp,
            "delta_recovery": delta_recovery,
            "auc_post_scandal": round(float(auc_raw), 4),
            "recovery_speed": speed,
        })

    rdf = pd.DataFrame(results_list).set_index("group")

    metrics_cols = [
        ("delta_recovery",   "Δ Recovery\n(final − min trust, ↑)",  True),
        ("auc_post_scandal", "AUC Post-Scandal\n(normalized, ↑)",   True),
        ("recovery_speed",   "Recovery Speed\n(trust/day, ↑)",      True),
    ]

    fig, axes = plt.subplots(1, 3, figsize=(15, 5.5))
    fig.suptitle("Core Metrics: Clarification Groups vs Control", fontsize=13, fontweight="bold")

    for ax, (col, ylabel, _) in zip(axes, metrics_cols):
        vals  = rdf[col].values
        x     = np.arange(len(groups))
        colors = [_gc(g) for g in rdf.index]

        bars = ax.bar(x, vals, color=colors, alpha=0.82, edgecolor="white", width=0.55)
        for bar, val in zip(bars, vals):
            ax.text(bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + abs(max(vals) - min(vals)) * 0.03,
                    f"{val:.4f}", ha="center", va="bottom", fontsize=9, fontweight="bold")

        ax.set_xticks(x)
        ax.set_xticklabels(rdf.index.tolist(), rotation=20, ha="right", fontsize=8)
        ax.set_ylabel(ylabel, fontsize=9)
        ax.grid(axis="y", ls=":", alpha=0.4)

        # 高亮最优
        best_idx = int(np.argmax(vals))
        bars[best_idx].set_edgecolor("#333"); bars[best_idx].set_linewidth(2.5)

        # Y轴放大差异
        rng = max(vals) - min(vals)
        margin = rng * 0.3 if rng > 0 else 0.01
        ax.set_ylim(min(vals) - margin * 2, max(vals) + margin * 4)

    # 图例
    handles = [mpatches.Patch(color=_gc(g), label=g) for g in groups]
    fig.legend(handles=handles, loc="lower center", ncol=min(4, len(groups)),
               fontsize=8, bbox_to_anchor=(0.5, -0.01))
    plt.tight_layout(rect=[0, 0.06, 1, 1])
    return _save(fig, "fig5_delta_recovery_bar.png")


# ══════════════════════════════════════════════════════════════════════
# 图6：情绪冲击 × 信任变化 散点图（按人群着色，按 group 区分形状）
# ══════════════════════════════════════════════════════════════════════
def plot_thought_scatter(df: pd.DataFrame):
    """x = affective_change (System 1 输出), y = 实际信任变化量 = trust_score - trust_after_decay"""
    df = df.copy()
    df["trust_delta"] = df["trust_score"] - df["trust_after_decay"]
    # 过滤极端噪声
    df = df[(df["affective_change"].abs() < 3) & (df["trust_delta"].abs() < 5)]

    groups = df["group"].unique().tolist()
    markers = ["o", "s", "^", "D", "P"]

    fig, axes = plt.subplots(1, len(groups), figsize=(5.5 * len(groups), 5.5), sharey=True)
    if len(groups) == 1: axes = [axes]
    fig.suptitle("System 1 Affective Impact vs Actual Trust Δ\n(x = LLM emotional output, y = realized trust change)",
                 fontsize=12, fontweight="bold")

    for ax, grp, mk in zip(axes, groups, markers):
        gdf = df[df["group"] == grp]
        for cluster in CORD:
            sub = gdf[gdf["cluster_type"] == cluster]
            if sub.empty: continue
            meta = CMETA.get(cluster, {"label": cluster, "color": "#888"})
            ax.scatter(sub["affective_change"], sub["trust_delta"],
                       color=meta["color"], alpha=0.45, s=30, marker=mk,
                       label=meta["label"])

        # 参考线
        ax.axhline(0, color="gray", lw=0.8, ls="--")
        ax.axvline(0, color="gray", lw=0.8, ls="--")

        # 线性拟合
        x, y = gdf["affective_change"].values, gdf["trust_delta"].values
        valid = (~np.isnan(x)) & (~np.isnan(y))
        if valid.sum() > 5:
            z  = np.polyfit(x[valid], y[valid], 1)
            xr = np.linspace(x[valid].min(), x[valid].max(), 50)
            ax.plot(xr, np.polyval(z, xr), color="black", lw=1.5, ls="-",
                    label=f"Linear fit (slope={z[0]:.2f})")

        ax.set_xlabel("Affective Change (System 1 LLM output)", fontsize=9)
        ax.set_title(grp, fontsize=10, fontweight="bold")
        ax.grid(True, ls=":", alpha=0.4)
        ax.legend(fontsize=7, loc="upper left")

    axes[0].set_ylabel("Realized Trust Δ = trust − decay_value", fontsize=9)
    plt.tight_layout()
    return _save(fig, "fig6_thought_scatter.png")


# ══════════════════════════════════════════════════════════════════════
# 主入口
# ══════════════════════════════════════════════════════════════════════
def main():
    parser = argparse.ArgumentParser(description="对照实验可视化")
    parser.add_argument("--file", default=None, help="指定 trial_thoughts_*.csv 路径")
    parser.add_argument("--mode", default="all",
                        choices=["all", "trust", "heatmap", "spotlight",
                                 "actions", "metrics", "scatter"])
    args = parser.parse_args()

    df = load_data(args.file)
    os.makedirs(OUT_DIR, exist_ok=True)

    print("\n🎨 生成图表...")
    if args.mode in ("trust",    "all"): plot_trust_trajectory(df)
    if args.mode in ("heatmap",  "all"): plot_affective_heatmap(df)
    if args.mode in ("spotlight","all"): plot_clarification_spotlight(df)
    if args.mode in ("actions",  "all"): plot_action_timeline(df)
    if args.mode in ("metrics",  "all"): plot_delta_recovery_bar(df)
    if args.mode in ("scatter",  "all"): plot_thought_scatter(df)

    print(f"\n✅ 全部图表已保存至: {OUT_DIR}")
    print("  fig1_trust_trajectory.png      — 信任轨迹对比")
    print("  fig2_affective_heatmap.png     — 情绪冲击热力图")
    print("  fig3_clarification_spotlight.png — 澄清窗口放大")
    print("  fig4_action_timeline.png       — 行为时间线")
    print("  fig5_delta_recovery_bar.png    — 核心指标对比")
    print("  fig6_thought_scatter.png       — 情绪冲击散点")


if __name__ == "__main__":
    main()
