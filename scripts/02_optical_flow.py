from datetime import datetime
import numpy as np
import matplotlib.pyplot as plt
import os
import csv
from pysteps import io, rcparams, motion, nowcasts
from pysteps.utils import conversion , transformation

from pathlib import Path


# 起报时间
date = datetime.strptime("201609281600", "%Y%m%d%H%M")

# FMI 数据配置
data_source = rcparams.data_sources["fmi"]

PROJECT_ROOT = Path(__file__).resolve().parents[1]

root_path = str(
    PROJECT_ROOT / "data" / "sample" / "pysteps-data" / "radar" / "fmi" / "pgm"
)
path_fmt = data_source["path_fmt"]
fn_pattern = data_source["fn_pattern"]
fn_ext = data_source["fn_ext"]
timestep = data_source["timestep"]

importer_name = data_source["importer"]
importer_kwargs = data_source["importer_kwargs"]


# 读取起报时刻之前2帧 + 当前帧
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

print("\ndB转换后：")
print("shape:", R.shape)

print("min:", np.nanmin(R))
print("max:", np.nanmax(R))
print("NaN数量:", np.isnan(R).sum())
print("雷达数据 shape:", R.shape)

print("\n输入时间：")
for timestamp in metadata["timestamps"]:
    print(timestamp)

oflow_method = motion.get_method("LK")

V = oflow_method(R)

print("\n运动场 shape:", V.shape)

print("x方向最小速度:", np.nanmin(V[0]))
print("x方向最大速度:", np.nanmax(V[0]))

print("y方向最小速度:", np.nanmin(V[1]))
print("y方向最大速度:", np.nanmax(V[1]))

os.makedirs("outputs/optical_flow", exist_ok=True)

plt.figure(figsize=(8, 10))

plt.imshow(R[-1])

step = 40

y, x = np.mgrid[
    0:R.shape[1]:step,
    0:R.shape[2]:step
]

plt.quiver(
    x,
    y,
    V[0, ::step, ::step],
    V[1, ::step, ::step],
    color="red"
)

plt.title("Lucas-Kanade Motion Field")
plt.axis("off")
plt.tight_layout()

plt.savefig(
    "outputs/optical_flow/motion_field.png",
    dpi=150
)

plt.close()

print("\n运动场图片已保存：")
print("outputs/optical_flow/motion_field.png")

n_leadtimes = 12

extrapolate = nowcasts.get_method("extrapolation")

R_f = extrapolate(
    R[-1],
    V,
    n_leadtimes
)

print("\n外推预报 shape:", R_f.shape)

R_future, _, future_metadata = io.read_timeseries(
    io.archive.find_by_date(
        date,
        root_path,
        path_fmt,
        fn_pattern,
        fn_ext,
        timestep,
        num_prev_files=0,
        num_next_files=n_leadtimes,
    ),
    importer,
    **importer_kwargs
)

R_future, future_metadata = conversion.to_rainrate(
    R_future, future_metadata
)
R_future_rain = R_future.copy()
R_future, future_metadata = transformation.dB_transform(
    R_future,
    future_metadata,
    threshold=0.1,
    zerovalue=-15.0
)

lead_idx = 11

plt.figure(figsize=(12, 6))

plt.subplot(1, 2, 1)
plt.imshow(R_f[lead_idx])
plt.title("Optical Flow +60 min")
plt.axis("off")

plt.subplot(1, 2, 2)
plt.imshow(R_future[lead_idx + 1])
plt.title("Observation +60 min")
plt.axis("off")

plt.tight_layout()
plt.savefig("outputs/optical_flow/oflow_vs_obs_60min.png", dpi=150)
plt.close()

print("\n+60 min 对比图已保存：")
print("outputs/optical_flow/oflow_vs_obs_60min.png")

rmse_list = []

for i in range(n_leadtimes):
    pred = R_f[i]
    obs = R_future[i + 1]

    mask = np.isfinite(pred) & np.isfinite(obs)
    rmse = np.sqrt(np.mean((pred[mask] - obs[mask]) ** 2))
    rmse_list.append(rmse)

print("\n各预报时效的 RMSE（dB尺度）：")
for i, rmse in enumerate(rmse_list, start=1):
    print(f"+{i*5:02d} min: {rmse:.4f}")



R_f_rain, _ = transformation.dB_transform(
    R_f,
    metadata,
    inverse=True
)

print("\n外推结果转回 rain rate 后：")
print("shape:", R_f_rain.shape)
print("min:", np.nanmin(R_f_rain))
print("max:", np.nanmax(R_f_rain))

rmse_rain_list = []

for i in range(n_leadtimes):
    pred = R_f_rain[i]
    obs = R_future_rain[i + 1]

    mask = np.isfinite(pred) & np.isfinite(obs)
    rmse = np.sqrt(np.mean((pred[mask] - obs[mask]) ** 2))
    rmse_rain_list.append(rmse)

print("\nOptical Flow RMSE（mm/h）：")
for i, rmse in enumerate(rmse_rain_list, start=1):
    print(f"+{i*5:02d} min: {rmse:.4f}")

metrics_dir = PROJECT_ROOT / "outputs" / "metrics"
metrics_dir.mkdir(parents=True, exist_ok=True)

csv_path = metrics_dir / "optical_flow_rmse.csv"

with open(csv_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)

    writer.writerow(["lead_time_min", "rmse"])

    for i, rmse in enumerate(rmse_rain_list, start=1):
        writer.writerow([i * 5, rmse])

print("\nRMSE 已保存：")
print(csv_path)