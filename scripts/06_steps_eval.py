from pathlib import Path

import numpy as np
import csv
from datetime import datetime

from pysteps import io, rcparams
from pysteps.utils import conversion, transformation
import matplotlib.pyplot as plt


PROJECT_ROOT = Path(__file__).resolve().parents[1]

forecast_path = (
    PROJECT_ROOT
    / "outputs"
    / "steps"
    / "steps_forecast.npy"
)

R_steps = np.load(forecast_path)

print("已读取 STEPS 预测结果")
print("shape:", R_steps.shape)


# 和前面实验保持一致的 dB 元数据
metadata = {
    "transform": "dB",
    "threshold": -10.0,
    "zerovalue": -15.0,
}

# 每个集合成员分别从 dB 转回 mm/h
R_steps_rain, _ = transformation.dB_transform(
    R_steps,
    metadata,
    inverse=True,
)

# 对 10 个集合成员求平均
R_steps_mean = np.nanmean(
    R_steps_rain,
    axis=0,
)

print("\n转换后全部成员 shape:", R_steps_rain.shape)
print("Ensemble Mean shape:", R_steps_mean.shape)

date = datetime.strptime("201609281600", "%Y%m%d%H%M")

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

importer = io.get_method(data_source["importer"], "importer")

R_future, _, future_metadata = io.read_timeseries(
    fns_future,
    importer,
    **data_source["importer_kwargs"]
)

R_future, future_metadata = conversion.to_rainrate(
    R_future,
    future_metadata
)

print("\n真实未来观测 shape:", R_future.shape)
print("起报时间:", future_metadata["timestamps"][0])
print("最后观测时间:", future_metadata["timestamps"][-1])

rmse_steps = []

for i in range(12):
    pred = R_steps_mean[i]
    obs = R_future[i + 1]

    mask = np.isfinite(pred) & np.isfinite(obs)

    rmse = np.sqrt(
        np.mean((pred[mask] - obs[mask]) ** 2)
    )

    rmse_steps.append(rmse)


print("\nSTEPS Ensemble Mean RMSE（mm/h）：")

for i, rmse in enumerate(rmse_steps, start=1):
    print(f"+{i*5:02d} min: {rmse:.4f}")


metrics_dir = PROJECT_ROOT / "outputs" / "metrics"
metrics_dir.mkdir(parents=True, exist_ok=True)

csv_path = metrics_dir / "steps_rmse.csv"

with open(csv_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)

    writer.writerow(["lead_time_min", "rmse"])

    for i, rmse in enumerate(rmse_steps, start=1):
        writer.writerow([i * 5, rmse])


print("\nRMSE 已保存：")
print(csv_path)

output_dir = PROJECT_ROOT / "outputs" / "steps"
output_dir.mkdir(parents=True, exist_ok=True)

lead_idx = 11  # +60 min

fig, axes = plt.subplots(2, 3, figsize=(15, 10))

# 选四个集合成员
for i in range(4):
    ax = axes.flat[i]
    ax.imshow(R_steps_rain[i, lead_idx])
    ax.set_title(f"Member {i + 1} +60 min")
    ax.axis("off")

# 集合平均
axes.flat[4].imshow(R_steps_mean[lead_idx])
axes.flat[4].set_title("Ensemble Mean +60 min")
axes.flat[4].axis("off")

# 真实观测
axes.flat[5].imshow(R_future[lead_idx + 1])
axes.flat[5].set_title("Observation +60 min")
axes.flat[5].axis("off")

plt.tight_layout()

plt.savefig(
    output_dir / "steps_members_60min.png",
    dpi=150,
)

plt.close()

print("\n集合成员对比图已保存：")
print(output_dir / "steps_members_60min.png")