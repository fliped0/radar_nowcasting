from experiment_context import get_context

CONTEXT = get_context()

from datetime import datetime
from pathlib import Path
import numpy as np
from pysteps import io, rcparams, motion, nowcasts
from pysteps.utils import conversion, transformation


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
    zerovalue=-15.0,
)

print("STEPS 输入 shape:", R.shape)

print("\n输入时间：")
for timestamp in metadata["timestamps"]:
    print(timestamp)

oflow_method = motion.get_method("LK")

V = oflow_method(R)

print("\nSTEPS 运动场 shape:", V.shape)

n_leadtimes = 12
n_ens_members = 10

steps_method = nowcasts.get_method("steps")

R_steps = steps_method(
    R,
    V,
    n_leadtimes,
    n_ens_members=n_ens_members,
    n_cascade_levels=6,
    precip_thr=-10.0,
    kmperpixel=metadata["xpixelsize"] / 1000.0,
    timestep=timestep,
    noise_method="nonparametric",
    vel_pert_method="bps",
    mask_method="incremental",
    seed=42,
    num_workers=1,
)

print("\nSTEPS 预报 shape:", R_steps.shape)

output_dir = CONTEXT.output_root / "steps"
output_dir.mkdir(parents=True, exist_ok=True)

np.save(output_dir / "steps_forecast.npy", R_steps)

print("\nSTEPS 原始预报已保存：")
print(output_dir / "steps_forecast.npy")

# 将所有 STEPS 成员从 dB 转回 rain rate
R_steps_rain, _ = transformation.dB_transform(
    R_steps,
    metadata,
    inverse=True,
)

# 对集合成员求平均
R_steps_mean = np.nanmean(
    R_steps_rain,
    axis=0,
)

print("\nSTEPS rain rate shape:", R_steps_rain.shape)
print("Ensemble Mean shape:", R_steps_mean.shape)
