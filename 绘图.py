
import numpy as np
import matplotlib.pyplot as plt
from matplotlib import font_manager
from pathlib import Path


# ============================================================
# 1. 字体设置
#    中文：宋体 SimSun
#    英文/数字：Times New Roman
# ============================================================

# Windows 默认字体路径
SIMSUN_PATH = r"C:\Windows\Fonts\simsun.ttc"
TIMES_PATH = r"C:\Windows\Fonts\times.ttf"

# 检查字体是否存在
if not Path(SIMSUN_PATH).exists():
    raise FileNotFoundError(f"未找到宋体字体：{SIMSUN_PATH}")

if not Path(TIMES_PATH).exists():
    raise FileNotFoundError(f"未找到 Times New Roman：{TIMES_PATH}")

# 字体属性
font_cn = font_manager.FontProperties(
    fname=SIMSUN_PATH,
    size=12
)

font_cn_title = font_manager.FontProperties(
    fname=SIMSUN_PATH,
    size=14
)

font_en = font_manager.FontProperties(
    fname=TIMES_PATH,
    size=11
)

font_legend = font_manager.FontProperties(
    fname=SIMSUN_PATH,
    size=10
)

# 全局字体：
# Times New Roman 优先负责英文和数字，
# SimSun 作为中文字符 fallback
plt.rcParams["font.family"] = ["Times New Roman", "SimSun"]
plt.rcParams["axes.unicode_minus"] = False


# ============================================================
# 2. 数据
# ============================================================

categories = [
    "可信度",
    "证据充分性",
    "共情程度",
    "主题相关性",
    "唤醒程度"
]

# 根据原图反推的近似值
rational = [
    0.90,   # 可信度
    0.94,   # 证据充分性
    0.30,   # 共情程度
    0.88,   # 主题相关性
    0.46    # 唤醒程度
]

emotional = [
    0.72,   # 可信度
    0.35,   # 证据充分性
    0.90,   # 共情程度
    0.89,   # 主题相关性
    0.72    # 唤醒程度
]


# ============================================================
# 3. 雷达图角度
# ============================================================

N = len(categories)

# 5 个维度均匀分布
angles = np.linspace(
    0,
    2 * np.pi,
    N,
    endpoint=False
).tolist()

# 闭合雷达图
angles_closed = angles + angles[:1]

rational_closed = rational + rational[:1]
emotional_closed = emotional + emotional[:1]


# ============================================================
# 4. 创建画布
# ============================================================

# ============================================================
# 4. 创建高分辨率画布
# ============================================================

fig, ax = plt.subplots(
    figsize=(10, 9),          # 增大画布
    dpi=150,                  # 屏幕显示清晰度
    subplot_kw=dict(polar=True)
)

fig.patch.set_facecolor("white")
ax.set_facecolor("white")


# ============================================================
# 5. 雷达图方向
#
# 原图：
#               证据充分性
#
#     共情程度                  可信度
#
#     主题相关性              唤醒程度
# ============================================================

# 0° 从右侧开始
ax.set_theta_offset(0)

# 逆时针方向
ax.set_theta_direction(1)


# ============================================================
# 6. 绘制理性证据型
# ============================================================

line1, = ax.plot(
    angles_closed,
    rational_closed,
    linewidth=2.3,
    marker="o",
    markersize=5.5,
    label="理性证据型"
)

ax.fill(
    angles_closed,
    rational_closed,
    alpha=0.12
)


# ============================================================
# 7. 绘制情感共情型
# ============================================================

line2, = ax.plot(
    angles_closed,
    emotional_closed,
    linewidth=2.3,
    marker="o",
    markersize=5.5,
    label="情感共情型"
)

ax.fill(
    angles_closed,
    emotional_closed,
    alpha=0.10
)


# ============================================================
# 8. 设置五个维度标签
# ============================================================

ax.set_xticks(angles)
ax.set_xticklabels(categories)

# 强制中文标签使用宋体
for label in ax.get_xticklabels():
    label.set_fontproperties(font_cn)
    label.set_fontsize(12)

# 标签和雷达图之间的距离
ax.tick_params(
    axis="x",
    pad=5
)


# ============================================================
# 9. 径向坐标轴
# ============================================================

ax.set_ylim(0, 1.0)

radial_ticks = [
    0.2,
    0.4,
    0.6,
    0.8,
    1.0
]

ax.set_yticks(radial_ticks)

ax.set_yticklabels([
    "0.2",
    "0.4",
    "0.6",
    "0.8",
    "1.0"
])

# 数字使用 Times New Roman
for label in ax.get_yticklabels():
    label.set_fontproperties(font_en)
    label.set_fontsize(10)

# 将刻度数字放在右上区域
ax.set_rlabel_position(22)


# ============================================================
# 10. 网格线
# ============================================================

# 环形网格
ax.yaxis.grid(
    True,
    linewidth=1.0,
    alpha=0.45
)

# 径向网格
ax.xaxis.grid(
    True,
    linewidth=1.0,
    alpha=0.45
)

# 最外圈
ax.spines["polar"].set_linewidth(1.15)


# ============================================================
# 11. 标题
# ============================================================

# 使用字体 fallback：
# 中文 -> 宋体
# 英文 "vs" -> Times New Roman
ax.set_title(
    "消费者对企业澄清信息的语义评价",
    fontsize=16,
    pad=38,
    fontfamily=["Times New Roman", "SimSun"]
)


# ============================================================
# 12. 图例
# ============================================================

legend = ax.legend(
    handles=[line1, line2],
    labels=["理性证据型", "情感共情型"],
    loc="upper left",
    bbox_to_anchor=(1.06, 1.10),
    frameon=True,
    prop=font_legend,
    borderaxespad=0
)

legend.get_frame().set_linewidth(0.8)
legend.get_frame().set_alpha(1.0)


# ============================================================
# 13. 调整布局
# ============================================================

plt.subplots_adjust(
    left=0.08,
    right=0.80,
    top=0.84,
    bottom=0.08
)


# ============================================================
# 14. 保存
# ============================================================

plt.savefig(
    "消费者对企业澄清信息的语义评价_雷达图.png",
    dpi=300,
    bbox_inches="tight",
    facecolor="white"
)

plt.savefig(
    "消费者对企业澄清信息的语义评价_雷达图.pdf",
    bbox_inches="tight",
    facecolor="white"
)


# ============================================================
# 15. 显示
# ============================================================

plt.show()