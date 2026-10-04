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

print("STEPS ensemble shape:", R_steps.shape)


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

print("STEPS rain rate shape:", R_steps_rain.shape)


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

R_future, _, future_metadata = io.read_timeseries(
    fns_future,
    importer,
    **data_source["importer_kwargs"],
)

R_future, future_metadata = conversion.to_rainrate(
    R_future,
    future_metadata,
)

print("真实观测 shape:", R_future.shape)


# ============================================================
# 5. Reliability Diagram 设置
# ============================================================

thresholds = [
    0.1,
    1.0,
    5.0,
]

lead_times = [
    15,
    30,
    60,
]

# 10 个 ensemble members
# 因此概率取值为 0.0, 0.1, ..., 1.0
probability_levels = np.arange(
    0.0,
    1.01,
    0.1,
)

results = []


# ============================================================
# 6. 计算可靠性
# ============================================================

for threshold in thresholds:

    print(
        f"\nThreshold = {threshold} mm/h"
    )

    plt.figure(figsize=(7, 6))

    # 完美可靠性线
    plt.plot(
        [0, 1],
        [0, 1],
        linestyle="--",
        label="Perfect Reliability",
    )

    for lead_time in lead_times:

        # +5 min -> index 0
        # +15 min -> index 2
        forecast_index = (
            lead_time // 5 - 1
        )

        members = R_steps_rain[
            :,
            forecast_index,
        ]

        obs = R_future[
            forecast_index + 1
        ]

        # 只保留观测有效，
        # 且 10 个 ensemble members 都有效的位置
        valid_mask = (
            np.isfinite(obs)
            & np.all(
                np.isfinite(members),
                axis=0,
            )
        )

        members_valid = members[
            :,
            valid_mask,
        ]

        obs_valid = obs[
            valid_mask
        ]

        # --------------------------------------------
        # ensemble probability
        # --------------------------------------------

        forecast_probability = np.mean(
            members_valid >= threshold,
            axis=0,
        )

        observed_event = (
            obs_valid >= threshold
        ).astype(float)

        observed_frequencies = []
        plotted_probabilities = []

        for probability_level in probability_levels:

            probability_mask = np.isclose(
                forecast_probability,
                probability_level,
            )

            sample_count = np.sum(
                probability_mask
            )

            if sample_count < 50:
                continue

            observed_frequency = np.mean(
                observed_event[
                    probability_mask
                ]
            )

            plotted_probabilities.append(
                probability_level
            )

            observed_frequencies.append(
                observed_frequency
            )

            results.append({
                "threshold": threshold,
                "lead_time_min": lead_time,
                "forecast_probability": probability_level,
                "observed_frequency": observed_frequency,
                "sample_count": int(sample_count),
            })

        plt.plot(
            plotted_probabilities,
            observed_frequencies,
            marker="o",
            label=f"+{lead_time} min",
        )

        print(
            f"+{lead_time:02d} min: "
            f"{len(obs_valid)} valid pixels"
        )


    # ========================================================
    # 7. 图形设置
    # ========================================================

    plt.xlabel(
        "Forecast Probability"
    )

    plt.ylabel(
        "Observed Frequency"
    )

    plt.title(
        f"STEPS Reliability Diagram "
        f"- Threshold {threshold} mm/h"
    )

    plt.xlim(
        0,
        1,
    )

    plt.ylim(
        0,
        1,
    )

    plt.xticks(
        np.arange(
            0,
            1.1,
            0.1,
        )
    )

    plt.yticks(
        np.arange(
            0,
            1.1,
            0.1,
        )
    )

    plt.grid(True)

    plt.legend()

    plt.tight_layout()


    # ========================================================
    # 8. 保存图片
    # ========================================================

    output_path = (
        OUTPUT_DIR
        / (
            f"steps_reliability_"
            f"threshold_{threshold}.png"
        )
    )

    plt.savefig(
        output_path,
        dpi=150,
    )

    plt.close()

    print(
        "已保存：",
        output_path,
    )


# ============================================================
# 9. 保存 Reliability 数据
# ============================================================

csv_path = (
    METRICS_DIR
    / "steps_reliability.csv"
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
            "threshold",
            "lead_time_min",
            "forecast_probability",
            "observed_frequency",
            "sample_count",
        ],
    )

    writer.writeheader()

    writer.writerows(
        results
    )


print(
    "\nReliability 数据已保存："
)

print(
    csv_path
)

print(
    "\nReliability Diagram 全部生成完成。"
)
