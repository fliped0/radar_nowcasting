from pathlib import Path
import csv
import numpy as np
from datetime import datetime

from pysteps import io, rcparams
from pysteps.utils import conversion

PROJECT_ROOT = Path(__file__).resolve().parents[1]

FORECAST_DIR = PROJECT_ROOT / "outputs" / "forecasts"


persistence = np.load(
    FORECAST_DIR / "persistence.npy"
)

optical_flow = np.load(
    FORECAST_DIR / "optical_flow.npy"
)

sprog = np.load(
    FORECAST_DIR / "sprog.npy"
)

steps_mean = np.load(
    FORECAST_DIR / "steps_mean.npy"
)


print("Persistence shape:", persistence.shape)
print("Optical Flow shape:", optical_flow.shape)
print("S-PROG shape:", sprog.shape)
print("STEPS Mean shape:", steps_mean.shape)

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

print("\n真实观测 shape:", R_future.shape)
print("起报时间:", future_metadata["timestamps"][0])
print("最后时间:", future_metadata["timestamps"][-1])

threshold = 1.0


def compute_csi(pred, obs, threshold):
    mask = np.isfinite(pred) & np.isfinite(obs)

    pred_event = pred[mask] >= threshold
    obs_event = obs[mask] >= threshold

    tp = np.sum(pred_event & obs_event)
    fp = np.sum(pred_event & ~obs_event)
    fn = np.sum(~pred_event & obs_event)

    denominator = tp + fp + fn

    if denominator == 0:
        return np.nan

    return tp / denominator

def compute_pod(pred, obs, threshold):
    mask = np.isfinite(pred) & np.isfinite(obs)

    pred_event = pred[mask] >= threshold
    obs_event = obs[mask] >= threshold

    tp = np.sum(pred_event & obs_event)
    fn = np.sum(~pred_event & obs_event)

    denominator = tp + fn

    if denominator == 0:
        return np.nan

    return tp / denominator


def compute_far(pred, obs, threshold):
    mask = np.isfinite(pred) & np.isfinite(obs)

    pred_event = pred[mask] >= threshold
    obs_event = obs[mask] >= threshold

    tp = np.sum(pred_event & obs_event)
    fp = np.sum(pred_event & ~obs_event)

    denominator = tp + fp

    if denominator == 0:
        return np.nan

    return fp / denominator

methods = {
    "Persistence": persistence,
    "Optical Flow": optical_flow,
    "S-PROG": sprog,
    "STEPS Mean": steps_mean,
}

print(f"\nCSI（threshold = {threshold} mm/h）：")

for method_name, forecast in methods.items():

    print(f"\n{method_name}")

    for i in range(12):
        pred = forecast[i]
        obs = R_future[i + 1]

        csi = compute_csi(
            pred,
            obs,
            threshold,
        )

        print(
            f"+{(i + 1) * 5:02d} min: "
            f"{csi:.4f}"
        )

print(f"\nPOD / FAR（threshold = {threshold} mm/h）：")

for method_name, forecast in methods.items():

    print(f"\n{method_name}")

    for i in range(12):
        pred = forecast[i]
        obs = R_future[i + 1]

        pod = compute_pod(pred, obs, threshold)
        far = compute_far(pred, obs, threshold)

        print(
            f"+{(i + 1) * 5:02d} min: "
            f"POD={pod:.4f}, FAR={far:.4f}"
        )

metrics_dir = PROJECT_ROOT / "outputs" / "metrics"
metrics_dir.mkdir(parents=True, exist_ok=True)

csv_path = metrics_dir / "unified_metrics_threshold_1.0.csv"

with open(csv_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)

    writer.writerow([
        "method",
        "lead_time_min",
        "threshold",
        "csi",
        "pod",
        "far",
    ])

    for method_name, forecast in methods.items():
        for i in range(12):
            pred = forecast[i]
            obs = R_future[i + 1]

            csi = compute_csi(pred, obs, threshold)
            pod = compute_pod(pred, obs, threshold)
            far = compute_far(pred, obs, threshold)

            writer.writerow([
                method_name,
                (i + 1) * 5,
                threshold,
                csi,
                pod,
                far,
            ])

print("\n统一分类指标已保存：")
print(csv_path)

thresholds = [0.1, 1.0, 5.0]

multi_csv_path = (
    metrics_dir
    / "unified_metrics_all_thresholds.csv"
)

with open(
    multi_csv_path,
    "w",
    newline="",
    encoding="utf-8",
) as f:

    writer = csv.writer(f)

    writer.writerow([
        "method",
        "lead_time_min",
        "threshold",
        "csi",
        "pod",
        "far",
    ])

    for threshold_value in thresholds:

        for method_name, forecast in methods.items():

            for i in range(12):

                pred = forecast[i]
                obs = R_future[i + 1]

                csi = compute_csi(
                    pred,
                    obs,
                    threshold_value,
                )

                pod = compute_pod(
                    pred,
                    obs,
                    threshold_value,
                )

                far = compute_far(
                    pred,
                    obs,
                    threshold_value,
                )

                writer.writerow([
                    method_name,
                    (i + 1) * 5,
                    threshold_value,
                    csi,
                    pod,
                    far,
                ])

print("\n多阈值统一指标已保存：")
print(multi_csv_path)