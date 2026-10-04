import csv
from datetime import datetime
from pathlib import Path

import numpy as np

from pysteps import io, rcparams
from pysteps.utils import conversion, transformation
from pysteps.verification.probscores import CRPS


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
# 5. 计算 CRPS
# ============================================================

results = []

print("\nSTEPS CRPS（mm/h）：")

for i in range(12):

    # 当前预报时效的全部 ensemble members
    # shape = (10, 1226, 760)
    members = R_steps_rain[:, i]

    # 对应真实观测
    obs = R_future[i + 1]

    # 只评价：
    # 观测有效，并且所有 ensemble members 都有效的位置
    valid_mask = (
        np.isfinite(obs)
        & np.all(
            np.isfinite(members),
            axis=0,
        )
    )

    members_valid = members[:, valid_mask]
    obs_valid = obs[valid_mask]

    crps_value = CRPS(
        members_valid,
        obs_valid,
    )

    lead_time = (i + 1) * 5

    results.append({
        "lead_time_min": lead_time,
        "crps": crps_value,
    })

    print(
        f"+{lead_time:02d} min: "
        f"{crps_value:.4f}"
    )


# ============================================================
# 6. 保存 CSV
# ============================================================

csv_path = (
    METRICS_DIR
    / "steps_crps.csv"
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
            "crps",
        ],
    )

    writer.writeheader()
    writer.writerows(results)


print("\nCRPS 已保存：")
print(csv_path)