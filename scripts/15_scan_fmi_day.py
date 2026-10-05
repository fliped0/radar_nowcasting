import sys
from pathlib import Path

import numpy as np

from pysteps import io, rcparams
from pysteps.utils import conversion


PROJECT_ROOT = Path(__file__).resolve().parents[1]

date = sys.argv[1]

data_source = rcparams.data_sources["fmi"]

data_dir = (
    PROJECT_ROOT
    / "data"
    / "sample"
    / "pysteps-data"
    / "radar"
    / "fmi"
    / "pgm"
    / date
)

importer = io.get_method(
    data_source["importer"],
    "importer",
)

files = sorted(data_dir.glob("*.pgm.gz"))

print(
    "time,max_mm_h,mean_mm_h,"
    "area_ge_1,area_ge_5"
)

for filename in files:

    R, _, metadata = importer(
        str(filename),
        **data_source["importer_kwargs"],
    )

    R, metadata = conversion.to_rainrate(
        R,
        metadata,
    )

    valid = np.isfinite(R)

    max_rain = np.nanmax(R)
    mean_rain = np.nanmean(R)

    area_ge_1 = np.sum(
        valid & (R >= 1.0)
    )

    area_ge_5 = np.sum(
        valid & (R >= 5.0)
    )

    timestamp = filename.name[:12]

    print(
        f"{timestamp},"
        f"{max_rain:.2f},"
        f"{mean_rain:.4f},"
        f"{area_ge_1},"
        f"{area_ge_5}"
    )