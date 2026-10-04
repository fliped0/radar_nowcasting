from experiment_context import get_context

CONTEXT = get_context()

from datetime import datetime
from pathlib import Path
import csv
from pysteps import io, rcparams, motion, nowcasts
from pysteps.utils import conversion, transformation

import numpy as np

from pysteps.cascade.bandpass_filters import filter_gaussian
from pysteps.cascade.decomposition import decomposition_fft


PROJECT_ROOT = Path(__file__).resolve().parents[1]

date = CONTEXT.date

data_source = rcparams.data_sources["fmi"]

root_path = str(CONTEXT.data_root)

path_fmt = data_source["path_fmt"]
fn_pattern = data_source["fn_pattern"]
fn_ext = data_source["fn_ext"]
timestep = data_source["timestep"]

importer_name = data_source["importer"]
importer_kwargs = data_source["importer_kwargs"]

fns = io.archive.find_by_date(
    date,
    root_path,
    path_fmt,
    fn_pattern,
    fn_ext,
    timestep,
    num_prev_files=2,
    num_next_files=0,
)

importer = io.get_method(importer_name, "importer")

R, _, metadata = io.read_timeseries(
    fns,
    importer,
    **importer_kwargs
)

R, metadata = conversion.to_rainrate(R, metadata)

R, metadata = transformation.dB_transform(
    R,
    metadata,
    threshold=0.1,
    zerovalue=-15.0
)

oflow_method = motion.get_method("LK")
V = oflow_method(R)

# 取起报时刻 16:00 的雷达场
R0 = R[-1].copy()

# FFT 不能直接处理 NaN，因此用无雨背景值填充
R0[~np.isfinite(R0)] = metadata["zerovalue"]

# 将雷达场分成 6 个空间尺度
n_cascade_levels = 6

bandpass_filter = filter_gaussian(
    R0.shape,
    n_cascade_levels
)

decomp = decomposition_fft(
    R0,
    bandpass_filter,
    compute_stats=True
)

print("\n级联分解 shape:", decomp["cascade_levels"].shape)
for i in range(n_cascade_levels):
    level = decomp["cascade_levels"][i]

    print(
        f"Level {i}: "
        f"min={np.min(level):.4f}, "
        f"max={np.max(level):.4f}, "
        f"std={np.std(level):.4f}"
    )

print("\n运动场 shape:", V.shape)

print("S-PROG 输入数据 shape:", R.shape)

print("\n输入时间：")
for timestamp in metadata["timestamps"]:
    print(timestamp)

n_leadtimes = 12

sprog_method = nowcasts.get_method("sprog")

R_sprog = sprog_method(
    R,
    V,
    n_leadtimes,
    n_cascade_levels=6,
    precip_thr=-10.0,
)

print("\nS-PROG 预报 shape:", R_sprog.shape)

import matplotlib.pyplot as plt
import os

# 读取真实未来观测（16:00 到 17:00）
fns_future = io.archive.find_by_date(
    date,
    root_path,
    path_fmt,
    fn_pattern,
    fn_ext,
    timestep,
    num_prev_files=0,
    num_next_files=n_leadtimes,
)

R_future, _, future_metadata = io.read_timeseries(
    fns_future,
    importer,
    **importer_kwargs
)

R_future, future_metadata = conversion.to_rainrate(R_future, future_metadata)
R_future_rain = R_future.copy()

# 把 S-PROG 结果从 dB 转回 rain rate
R_sprog_rain, _ = transformation.dB_transform(
    R_sprog,
    metadata,
    inverse=True
)

forecast_dir = CONTEXT.output_root / "forecasts"
forecast_dir.mkdir(parents=True, exist_ok=True)

np.save(
    forecast_dir / "sprog.npy",
    R_sprog_rain
)

print("\nS-PROG 预测场已保存：")
print(forecast_dir / "sprog.npy")

os.makedirs(CONTEXT.legacy_path("outputs/sprog"), exist_ok=True)

lead_idx = 11

plt.figure(figsize=(12, 6))

plt.subplot(1, 2, 1)
plt.imshow(R_sprog_rain[lead_idx])
plt.title("S-PROG +60 min")
plt.axis("off")

plt.subplot(1, 2, 2)
plt.imshow(R_future_rain[lead_idx + 1])
plt.title("Observation +60 min")
plt.axis("off")

plt.tight_layout()
plt.savefig(CONTEXT.legacy_path("outputs/sprog/sprog_vs_obs_60min.png"), dpi=150)
plt.close()

print("\n+60 min 对比图已保存：")
print(CONTEXT.legacy_path("outputs/sprog/sprog_vs_obs_60min.png"))

rmse_sprog = []

for i in range(n_leadtimes):
    pred = R_sprog_rain[i]
    obs = R_future_rain[i + 1]

    mask = np.isfinite(pred) & np.isfinite(obs)

    rmse = np.sqrt(
        np.mean((pred[mask] - obs[mask]) ** 2)
    )

    rmse_sprog.append(rmse)

print("\nS-PROG RMSE（mm/h）：")

for i, rmse in enumerate(rmse_sprog, start=1):
    print(f"+{i*5:02d} min: {rmse:.4f}")

metrics_dir = CONTEXT.output_root / "metrics"
metrics_dir.mkdir(parents=True, exist_ok=True)

csv_path = metrics_dir / "sprog_rmse.csv"

with open(csv_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)

    writer.writerow(["lead_time_min", "rmse"])

    for i, rmse in enumerate(rmse_sprog, start=1):
        writer.writerow([i * 5, rmse])

print("\nRMSE 已保存：")
print(csv_path)
