from datetime import datetime
from pathlib import Path

from pysteps import io, rcparams, motion, nowcasts
from pysteps.utils import conversion, transformation

import numpy as np

from pysteps.cascade.bandpass_filters import filter_gaussian
from pysteps.cascade.decomposition import decomposition_fft


PROJECT_ROOT = Path(__file__).resolve().parents[1]

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