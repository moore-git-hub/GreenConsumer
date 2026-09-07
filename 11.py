import os
import numpy as np
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.ticker import FormatStrFormatter


# ==================================================
# 1. 字体设置：中文宋体，英文和数字 Times New Roman
# ==================================================
def configure_fonts():
    font_files = [
        r"C:\Windows\Fonts\times.ttf",
        r"C:\Windows\Fonts\timesbd.ttf",
        r"C:\Windows\Fonts\simsun.ttc",
    ]

    for font_file in font_files:
        if os.path.exists(font_file):
            font_manager.fontManager.addfont(font_file)
        else:
            print(f"警告：未找到字体文件 {font_file}")

    # 英文和数字优先 Times New Roman，中文回退到宋体
    plt.rcParams["font.family"] = [
        "Times New Roman",
        "SimSun",
    ]

    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["pdf.fonttype"] = 42
    plt.rcParams["ps.fonttype"] = 42


configure_fonts()


# ==================================================
# 2. 数据
# ==================================================
network_types = [
    "无标度网络（BA）",
    "小世界网络（WS）",
    "社群网络（SBM）",
]

# 柱子的平均值
mean_values = np.array([
    0.40,
    0.12,
    0.17,
])

# 上下对称误差
error_values = np.array([
    0.15,
    0.03,
    0.13,
])

x = np.arange(len(network_types))


# ==================================================
# 3. 创建画布
# ==================================================
fig, ax = plt.subplots(
    figsize=(7.20, 4.38),
    dpi=100,
)


# ==================================================
# 4. 绘制带误差棒的柱状图
# ==================================================
bars = ax.bar(
    x,
    mean_values,
    width=0.80,
    color="#1f77b4",
    edgecolor="#1f77b4",

    # 误差棒
    yerr=error_values,
    capsize=5,
    error_kw={
        "ecolor": "#202020",
        "elinewidth": 1.6,
        "capthick": 1.6,
    },
)


# ==================================================
# 5. 坐标轴标签
# ==================================================
ax.set_ylabel(
    "核心节点被“随机节点激活”的直接触达差值",
    fontsize=12,
)

ax.set_xticks(x)
ax.set_xticklabels(
    network_types,
    fontsize=11,
)


# ==================================================
# 6. 坐标范围与刻度
# ==================================================
ax.set_ylim(0, 0.575)

ax.set_yticks(
    np.arange(0.0, 0.51, 0.1)
)

ax.yaxis.set_major_formatter(
    FormatStrFormatter("%.1f")
)


# ==================================================
# 7. 图形外观
# ==================================================
ax.grid(False)

# 隐藏上边框和右边框
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)

ax.spines["left"].set_color("#404040")
ax.spines["bottom"].set_color("#404040")

ax.spines["left"].set_linewidth(1.0)
ax.spines["bottom"].set_linewidth(1.0)

ax.tick_params(
    axis="both",
    which="major",
    direction="out",
    length=3.5,
    width=1,
    colors="#303030",
)


# ==================================================
# 8. 字体细分
# ==================================================
# 纵轴数字使用 Times New Roman
for label in ax.get_yticklabels():
    label.set_fontfamily("Times New Roman")
    label.set_fontsize(11)

# 横轴标签中：
# 中文自动回退到宋体，BA、WS、SBM 和括号内英文优先 TNR
for label in ax.get_xticklabels():
    label.set_fontfamily([
        "Times New Roman",
        "SimSun",
    ])


# ==================================================
# 9. 调整布局并导出
# ==================================================
plt.tight_layout()

plt.savefig(
    "network_type_bar_chart.png",
    dpi=300,
    bbox_inches="tight",
    facecolor="white",
)

plt.savefig(
    "network_type_bar_chart.pdf",
    bbox_inches="tight",
    facecolor="white",
)

plt.show()