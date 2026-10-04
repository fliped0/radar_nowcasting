from experiment_context import get_context

CONTEXT = get_context()

import csv
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from pysteps import io, rcparams
from pysteps.utils import conversion, transformation


# ============================================================
# 1. 项目路径
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

STEPS_PATH = (
    CONTEXT.output_root
    / "steps"
    / "steps_forecast.npy"
)

METRICS_DIR = (
    CONTEXT.output_root
    / "metrics"
)

OUTPUT_DIR = (
    CONTEXT.output_root
    / "evaluation"
)

METRICS_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


# ============================================================
# 2. 读取 STEPS ensemble
# ============================================================

R_steps = np.load(STEPS_PATH)

print(
    "STEPS ensemble shape:",
    R_steps.shape,
)


# ============================================================
# 3. dB -> rain rate
# ============================================================

metadata = {
    "transform": "dB",
    "threshold": -10.0,
    "zerovalue": -15.0,
}

R_steps_rain, _ = transformation.dB_transform(
    R_steps,
    metadata,
    inverse=True,
)

print(
    "STEPS rain rate shape:",
    R_steps_rain.shape,
)


# ============================================================
# 4. 读取真实未来观测
# ============================================================

date = CONTEXT.date

data_source = rcparams.data_sources["fmi"]

root_path = str(CONTEXT.data_root)

fns_future = io.archive.find_by_date(
    date,
    root_path,
    data_source["path_fmt"],
    data_source["fn_pattern"],
    data_source["fn_ext"],
    data_source["timestep"],
    num_prev_files=0,
    num_next_files=12,
)

importer = io.get_method(
    data_source["importer"],
    "importer",
)

R_future, _, future_metadata = (
    io.read_timeseries(
        fns_future,
        importer,
        **data_source["importer_kwargs"],
    )
)

R_future, future_metadata = (
    conversion.to_rainrate(
        R_future,
        future_metadata,
    )
)

print(
    "真实观测 shape:",
    R_future.shape,
)


# ============================================================
# 5. Spread-Skill
# ============================================================

results = []

lead_times = []
spread_values = []
rmse_values = []
ratio_values = []

print("\nSTEPS Spread-Skill：")


for i in range(12):

    # 当前时效所有 ensemble members
    # shape = (10, H, W)
    members = R_steps_rain[:, i]

    # 对应真实观测
    obs = R_future[i + 1]

    # 保证观测和全部成员均有效
    valid_mask = (
        np.isfinite(obs)
        & np.all(
            np.isfinite(members),
            axis=0,
        )
    )

    members_valid = (
        members[:, valid_mask]
    )

    obs_valid = (
        obs[valid_mask]
    )


    # --------------------------------------------------------
    # ensemble mean
    # --------------------------------------------------------

    ensemble_mean = np.mean(
        members_valid,
        axis=0,
    )


    # --------------------------------------------------------
    # Skill:
    # ensemble mean 与真实观测之间的 RMSE
    # --------------------------------------------------------

    rmse = np.sqrt(
        np.mean(
            (
                ensemble_mean
                - obs_valid
            ) ** 2
        )
    )


    # --------------------------------------------------------
    # Spread:
    # 每个像素上计算 10 个成员的标准差
    #
    # ddof=1:
    # 使用样本标准差
    # --------------------------------------------------------

    ensemble_std = np.std(
        members_valid,
        axis=0,
        ddof=1,
    )


    # 使用 RMS Spread
    #
    # sqrt(mean(std^2))
    #
    # 这样与 RMSE 保持相同量纲和形式
    spread = np.sqrt(
        np.mean(
            ensemble_std ** 2
        )
    )


    # --------------------------------------------------------
    # Spread-Skill Ratio
    # --------------------------------------------------------

    if rmse > 0:
        spread_skill_ratio = (
            spread / rmse
        )
    else:
        spread_skill_ratio = np.nan


    lead_time = (i + 1) * 5


    lead_times.append(
        lead_time
    )

    spread_values.append(
        spread
    )

    rmse_values.append(
        rmse
    )

    ratio_values.append(
        spread_skill_ratio
    )


    results.append({
        "lead_time_min": lead_time,
        "spread": spread,
        "rmse": rmse,
        "spread_skill_ratio": (
            spread_skill_ratio
        ),
    })


    print(
        f"+{lead_time:02d} min: "
        f"Spread={spread:.4f}, "
        f"RMSE={rmse:.4f}, "
        f"Ratio={spread_skill_ratio:.4f}"
    )


# ============================================================
# 6. 保存 CSV
# ============================================================

csv_path = (
    METRICS_DIR
    / "steps_spread_skill.csv"
)

with open(
    csv_path,
    "w",
    newline="",
    encoding="utf-8",
) as f:

    writer = csv.DictWriter(
        f,
        fieldnames=[
            "lead_time_min",
            "spread",
            "rmse",
            "spread_skill_ratio",
        ],
    )

    writer.writeheader()

    writer.writerows(
        results
    )


print(
    "\nSpread-Skill 数据已保存："
)

print(
    csv_path
)


# ============================================================
# 7. Spread 与 RMSE 对比图
# ============================================================

plt.figure(
    figsize=(8, 5)
)

plt.plot(
    lead_times,
    spread_values,
    marker="o",
    label="Ensemble Spread",
)

plt.plot(
    lead_times,
    rmse_values,
    marker="o",
    label="Ensemble Mean RMSE",
)

plt.xlabel(
    "Lead Time (min)"
)

plt.ylabel(
    "Rain Rate (mm/h)"
)

plt.title(
    "STEPS Spread-Skill"
)

plt.xticks(
    range(5, 65, 5)
)

plt.grid(
    True
)

plt.legend()

plt.tight_layout()

spread_skill_path = (
    OUTPUT_DIR
    / "steps_spread_skill.png"
)

plt.savefig(
    spread_skill_path,
    dpi=150,
)

plt.close()


print(
    "Spread-Skill 图已保存："
)

print(
    spread_skill_path
)


# ============================================================
# 8. Spread-Skill Ratio 图
# ============================================================

plt.figure(
    figsize=(8, 5)
)

plt.plot(
    lead_times,
    ratio_values,
    marker="o",
)

n_members = R_steps_rain.shape[0]

ideal_ratio = np.sqrt(
    n_members / (n_members + 1)
)

plt.axhline(
    y=ideal_ratio,
    linestyle="--",
    label=f"Ideal Ratio = {ideal_ratio:.3f}",
)

plt.xlabel(
    "Lead Time (min)"
)

plt.ylabel(
    "Spread / RMSE"
)

plt.title(
    "STEPS Spread-Skill Ratio"
)

plt.xticks(
    range(5, 65, 5)
)

plt.grid(
    True
)

plt.legend()

plt.tight_layout()

ratio_path = (
    OUTPUT_DIR
    / "steps_spread_skill_ratio.png"
)

plt.savefig(
    ratio_path,
    dpi=150,
)

plt.close()


print(
    "Spread-Skill Ratio 图已保存："
)

print(
    ratio_path
)
