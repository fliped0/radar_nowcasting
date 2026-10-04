import csv
from pathlib import Path

import matplotlib.pyplot as plt


PROJECT_ROOT = Path(__file__).resolve().parents[1]

CSV_PATH = (
    PROJECT_ROOT
    / "outputs"
    / "metrics"
    / "steps_brier_score.csv"
)

OUTPUT_DIR = (
    PROJECT_ROOT
    / "outputs"
    / "evaluation"
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


thresholds = [
    0.1,
    1.0,
    5.0,
]


rows = []

with open(
    CSV_PATH,
    "r",
    encoding="utf-8",
) as f:

    reader = csv.DictReader(f)

    for row in reader:
        rows.append({
            "lead_time_min": int(
                row["lead_time_min"]
            ),
            "threshold": float(
                row["threshold"]
            ),
            "brier_score": float(
                row["brier_score"]
            ),
        })


plt.figure(figsize=(8, 5))

for threshold in thresholds:

    threshold_rows = [
        row
        for row in rows
        if abs(
            row["threshold"] - threshold
        ) < 1e-8
    ]

    threshold_rows.sort(
        key=lambda row:
        row["lead_time_min"]
    )

    lead_times = [
        row["lead_time_min"]
        for row in threshold_rows
    ]

    scores = [
        row["brier_score"]
        for row in threshold_rows
    ]

    plt.plot(
        lead_times,
        scores,
        marker="o",
        label=f"{threshold} mm/h",
    )


plt.xlabel("Lead Time (min)")
plt.ylabel("Brier Score")
plt.title("STEPS Brier Score")
plt.grid(True)
plt.legend()
plt.tight_layout()

output_path = (
    OUTPUT_DIR
    / "steps_brier_score.png"
)

plt.savefig(
    output_path,
    dpi=150,
)

plt.close()

print("Brier Score 曲线已保存：")
print(output_path)