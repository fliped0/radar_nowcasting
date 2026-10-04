from experiment_context import get_context

CONTEXT = get_context()

import csv
from pathlib import Path

import matplotlib.pyplot as plt


# ============================================================
# 1. 项目路径
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

CSV_PATH = (
    CONTEXT.output_root
    / "metrics"
    / "unified_metrics_all_thresholds.csv"
)

OUTPUT_DIR = (
    CONTEXT.output_root
    / "evaluation"
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


# ============================================================
# 2. 实验设置
# ============================================================

methods = [
    "Persistence",
    "Optical Flow",
    "S-PROG",
    "STEPS Mean",
]

thresholds = [
    0.1,
    1.0,
    5.0,
]

metrics = {
    "csi": "CSI",
    "pod": "POD",
    "far": "FAR",
}


# ============================================================
# 3. 读取统一评估 CSV
# ============================================================

rows = []

with open(
    CSV_PATH,
    "r",
    encoding="utf-8",
) as f:

    reader = csv.DictReader(f)

    for row in reader:

        rows.append({
            "method": row["method"],
            "lead_time_min": int(
                row["lead_time_min"]
            ),
            "threshold": float(
                row["threshold"]
            ),
            "csi": float(
                row["csi"]
            ),
            "pod": float(
                row["pod"]
            ),
            "far": float(
                row["far"]
            ),
        })


print("统一指标数据读取完成")
print("数据行数:", len(rows))


# ============================================================
# 4. 绘制 CSI / POD / FAR
# ============================================================

for metric_key, metric_label in metrics.items():

    for threshold in thresholds:

        plt.figure(
            figsize=(8, 5)
        )

        for method in methods:

            method_rows = [
                row
                for row in rows
                if (
                    row["method"] == method
                    and abs(
                        row["threshold"] - threshold
                    ) < 1e-8
                )
            ]

            method_rows.sort(
                key=lambda row:
                row["lead_time_min"]
            )

            if len(method_rows) == 0:
                print(
                    f"警告：没有找到 "
                    f"{method} / "
                    f"{threshold} mm/h "
                    f"的数据"
                )
                continue

            lead_times = [
                row["lead_time_min"]
                for row in method_rows
            ]

            metric_values = [
                row[metric_key]
                for row in method_rows
            ]

            plt.plot(
                lead_times,
                metric_values,
                marker="o",
                label=method,
            )


        # ----------------------------------------------------
        # 图形设置
        # ----------------------------------------------------

        plt.xlabel(
            "Lead Time (min)"
        )

        plt.ylabel(
            metric_label
        )

        plt.title(
            f"{metric_label} Comparison "
            f"- Threshold {threshold} mm/h"
        )

        plt.ylim(
            0,
            1,
        )

        plt.xticks(
            range(5, 65, 5)
        )

        plt.grid(
            True
        )

        plt.legend()

        plt.tight_layout()


        # ----------------------------------------------------
        # 保存图片
        # ----------------------------------------------------

        output_path = (
            OUTPUT_DIR
            / (
                f"{metric_key}_"
                f"threshold_{threshold}.png"
            )
        )

        plt.savefig(
            output_path,
            dpi=150,
        )

        plt.close()

        print(
            "已保存：",
            output_path,
        )


# ============================================================
# 5. 完成提示
# ============================================================

print(
    "\n全部阈值指标图生成完成。"
)

print(
    "输出目录：",
    OUTPUT_DIR,
)
