import argparse
import csv
from datetime import datetime
from pathlib import Path

import numpy as np

from pysteps import io, rcparams
from pysteps.utils import conversion, transformation


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def parse_args():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--start-time",
        required=True,
        help="YYYYMMDDHHMM",
    )

    return parser.parse_args()


def main():

    args = parse_args()

    start_time = args.start_time

    date = datetime.strptime(
        start_time,
        "%Y%m%d%H%M",
    )

    case_id = (
        f"fmi_"
        f"{date.strftime('%Y%m%dT%H%M%SZ')}"
    )

    case_dir = (
        PROJECT_ROOT
        / "outputs"
        / "cases"
        / case_id
    )

    steps_path = (
        case_dir
        / "steps"
        / "steps_forecast.npy"
    )

    persistence_path = (
        case_dir
        / "forecasts"
        / "persistence.npy"
    )

    metrics_dir = (
        case_dir
        / "metrics"
    )

    # ========================================================
    # 1. 读取 STEPS ensemble
    # ========================================================

    R_steps = np.load(
        steps_path
    )

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

    print(
        "STEPS shape:",
        R_steps_rain.shape,
    )


    # ========================================================
    # 2. 读取 Persistence
    # ========================================================

    R_persistence = np.load(
        persistence_path
    )

    print(
        "Persistence shape:",
        R_persistence.shape,
    )


    # ========================================================
    # 3. 读取未来真实观测
    # ========================================================

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

    R_future, _, future_metadata = (
        io.read_timeseries(
            fns_future,
            importer,
            **data_source[
                "importer_kwargs"
            ],
        )
    )

    R_future, future_metadata = (
        conversion.to_rainrate(
            R_future,
            future_metadata,
        )
    )


    # ========================================================
    # 4. 计算 Brier Skill Score
    # ========================================================

    thresholds = [
        0.1,
        1.0,
        5.0,
    ]

    results = []

    for threshold in thresholds:

        print(
            f"\nThreshold = "
            f"{threshold} mm/h"
        )

        for i in range(12):

            members = (
                R_steps_rain[:, i]
            )

            persistence = (
                R_persistence[i]
            )

            obs = (
                R_future[i + 1]
            )

            # --------------------------------------------
            # STEPS 概率
            # --------------------------------------------

            valid_members = (
                np.isfinite(members)
            )

            member_events = np.where(
                valid_members,
                members >= threshold,
                np.nan,
            )

            steps_probability = (
                np.nanmean(
                    member_events,
                    axis=0,
                )
            )

            # --------------------------------------------
            # Persistence 作为参考概率
            #
            # deterministic forecast:
            # 发生 = 1
            # 不发生 = 0
            # --------------------------------------------

            persistence_probability = (
                persistence >= threshold
            ).astype(float)

            obs_event = (
                obs >= threshold
            ).astype(float)

            # --------------------------------------------
            # 使用统一有效区域
            # --------------------------------------------

            valid_mask = (
                np.isfinite(
                    steps_probability
                )
                & np.isfinite(
                    persistence
                )
                & np.isfinite(
                    obs
                )
            )

            p_steps = (
                steps_probability[
                    valid_mask
                ]
            )

            p_ref = (
                persistence_probability[
                    valid_mask
                ]
            )

            o = (
                obs_event[
                    valid_mask
                ]
            )

            # --------------------------------------------
            # Brier Score
            # --------------------------------------------

            bs_steps = np.mean(
                (p_steps - o) ** 2
            )

            bs_persistence = np.mean(
                (p_ref - o) ** 2
            )

            # --------------------------------------------
            # Brier Skill Score
            #
            # BSS = 1 - BS_steps / BS_ref
            # --------------------------------------------

            if bs_persistence > 0:

                bss = (
                    1.0
                    - bs_steps
                    / bs_persistence
                )

            else:

                bss = np.nan

            lead_time = (
                (i + 1) * 5
            )

            results.append({
                "lead_time_min":
                    lead_time,
                "threshold":
                    threshold,
                "bs_steps":
                    bs_steps,
                "bs_persistence":
                    bs_persistence,
                "bss":
                    bss,
            })

            print(
                f"+{lead_time:02d} min: "
                f"BS_STEPS="
                f"{bs_steps:.6f}, "
                f"BS_Persistence="
                f"{bs_persistence:.6f}, "
                f"BSS="
                f"{bss:.4f}"
            )


    # ========================================================
    # 5. 保存 CSV
    # ========================================================

    csv_path = (
        metrics_dir
        / "steps_brier_skill_score.csv"
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
                "bs_steps",
                "bs_persistence",
                "bss",
            ],
        )

        writer.writeheader()
        writer.writerows(
            results
        )

    print(
        "\nBrier Skill Score 已保存："
    )

    print(
        csv_path
    )


if __name__ == "__main__":
    main()