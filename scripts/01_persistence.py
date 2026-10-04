from experiment_context import get_context

CONTEXT = get_context()

from datetime import datetime
import csv
import numpy as np
from pysteps import io, rcparams
from pysteps.utils import conversion
from pathlib import Path


date = CONTEXT.date
n_leadtimes = 12

data_source = rcparams.data_sources["fmi"]

PROJECT_ROOT = Path(__file__).resolve().parents[1]

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
    num_prev_files=0,
    num_next_files=n_leadtimes,
)

importer = io.get_method(importer_name, "importer")

R_obs, _, metadata = io.read_timeseries(
    fns,
    importer,
    **importer_kwargs
)

R_obs, metadata = conversion.to_rainrate(R_obs, metadata)

R0 = R_obs[0]

R_persistence = np.repeat(
    R0[np.newaxis, :, :],
    n_leadtimes,
    axis=0
)

forecast_dir = CONTEXT.output_root / "forecasts"
forecast_dir.mkdir(parents=True, exist_ok=True)

np.save(
    forecast_dir / "persistence.npy",
    R_persistence
)

print("\nPersistence 预测场已保存：")
print(forecast_dir / "persistence.npy")

print("timestep:", timestep, "min")
print("观测数据 shape:", R_obs.shape)
print("Persistence shape:", R_persistence.shape)

print("\n起报时间:", metadata["timestamps"][0])

print("\n未来观测时间：")
for timestamp in metadata["timestamps"][1:]:
    print(timestamp)
import os
import matplotlib.pyplot as plt

os.makedirs(CONTEXT.legacy_path("outputs/persistence"), exist_ok=True)

lead_idx = 11

fig, axes = plt.subplots(1, 2, figsize=(12, 6))

axes[0].imshow(R_persistence[lead_idx])
axes[0].set_title("Persistence +60 min")
axes[0].axis("off")

axes[1].imshow(R_obs[lead_idx + 1])
axes[1].set_title("Observation +60 min")
axes[1].axis("off")

plt.tight_layout()

plt.savefig(
    CONTEXT.legacy_path("outputs/persistence/persistence_vs_obs_60min.png"),
    dpi=150
)

plt.close()

print("\n对比图已保存：")
print(CONTEXT.legacy_path("outputs/persistence/persistence_vs_obs_60min.png"))

rmse_list = []

for i in range(n_leadtimes):
    pred = R_persistence[i]
    obs = R_obs[i + 1]

    mask = np.isfinite(pred) & np.isfinite(obs)
    rmse = np.sqrt(np.mean((pred[mask] - obs[mask]) ** 2))
    rmse_list.append(rmse)

print("\n各预报时效的 RMSE：")
for i, rmse in enumerate(rmse_list, start=1):
    print(f"+{i*5:02d} min: {rmse:.4f}")

metrics_dir = CONTEXT.output_root / "metrics"
metrics_dir.mkdir(parents=True, exist_ok=True)

csv_path = metrics_dir / "persistence_rmse.csv"

with open(csv_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)

    writer.writerow(["lead_time_min", "rmse"])

    for i, rmse in enumerate(rmse_list, start=1):
        writer.writerow([i * 5, rmse])

print("\nRMSE 已保存：")
print(csv_path)

lead_minutes = np.arange(5, 65, 5)

plt.figure(figsize=(8, 5))
plt.plot(lead_minutes, rmse_list, marker="o")

plt.xlabel("Lead time (min)")
plt.ylabel("RMSE (mm/h)")
plt.title("Persistence Nowcast RMSE")
plt.grid(True)

plt.tight_layout()
plt.savefig(
    CONTEXT.legacy_path("outputs/persistence/persistence_rmse.png"),
    dpi=150
)
plt.close()

print("\nRMSE 曲线已保存：")
print(CONTEXT.legacy_path("outputs/persistence/persistence_rmse.png"))
