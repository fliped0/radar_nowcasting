import csv
from datetime import datetime
from pathlib import Path

import numpy as np

from pysteps import io, rcparams
from pysteps.utils import conversion, transformation


# ============================================================
# 1. 项目路径
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

STEPS_PATH = (
    PROJECT_ROOT
    / "outputs"
    / "steps"
    / "steps_forecast.npy"
)

METRICS_DIR = (
    PROJECT_ROOT
    / "outputs"
    / "metrics"
)

METRICS_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


# ============================================================
# 2. 读取 STEPS ensemble
# ============================================================

R_steps = np.load(STEPS_PATH)

print("STEPS ensemble shape:", R_steps.shape)


# ============================================================
# 3. 从 dB 转回 rain rate
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

date = datetime.strptime(
    "201609281600",
    "%Y%m%d%H%M",
)

data_source = rcparams.data_sources["fmi"]

root_path = str(
    PROJECT_ROOT
    / "data"
    / "sample"
    / "pysteps-data"
    / "radar"
    / "fmi"
    / "pgm"
)

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
# 5. Brier Score
# ============================================================

thresholds = [
    0.1,
    1.0,
    5.0,
]

results = []


for threshold in thresholds:

    print(
        f"\nBrier Score "
        f"(threshold = {threshold} mm/h)"
    )

    for i in range(12):

        # shape:
        # (10, 1226, 760)
        members = R_steps_rain[:, i]

        obs = R_future[i + 1]

        # 每个 ensemble member 是否超过阈值
        valid_members = np.isfinite(members)

        member_events = np.where(
            valid_members,
            members >= threshold,
            np.nan,
        )

        # 10 个成员中有多少比例预测事件发生
        probability = np.nanmean(
            member_events,
            axis=0,
        )

        obs_event = (
            obs >= threshold
        ).astype(float)

        valid_mask = (
            np.isfinite(probability)
            & np.isfinite(obs)
        )

        brier_score = np.mean(
            (
                probability[valid_mask]
                - obs_event[valid_mask]
            ) ** 2
        )

        lead_time = (i + 1) * 5

        results.append({
            "lead_time_min": lead_time,
            "threshold": threshold,
            "brier_score": brier_score,
        })

        print(
            f"+{lead_time:02d} min: "
            f"{brier_score:.4f}"
        )


# ============================================================
# 6. 保存 CSV
# ============================================================

csv_path = (
    METRICS_DIR
    / "steps_brier_score.csv"
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
            "threshold",
            "brier_score",
        ],
    )

    writer.writeheader()
    writer.writerows(results)


print("\nBrier Score 已保存：")
print(csv_path)