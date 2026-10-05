# FMI 单案例与批量入口

在项目根目录激活 `radar-nowcasting`。第一版保持所有算法参数、计算顺序和指标定义。
不要求 `configs/pystepsrc`：各任务继续读取 PySTEPS 当前 `rcparams.data_sources["fmi"]`
中的文件规则、时间步长及 importer。数据根目录统一为项目内
`data/sample/pysteps-data/radar/fmi/pgm`，不会修改全局 rcparams 或系统环境。

## 运行

```bash
conda activate radar-nowcasting
python scripts/run_case.py --start-time 201609281600 --dry-run
python scripts/run_case.py --start-time 201609281600
python scripts/run_case.py --start-time 201609281600 --tasks 09,10 --overwrite
python scripts/run_cases.py --cases configs/cases.json --dry-run
```

时间必须是 UTC `YYYYMMDDHHMM`，且位于 5 分钟边界；案例编号自动生成。
`configs/cases.json` 只有 `start_times` 字符串列表，当前包含两个正式验证案例：
`201609281600` 和 `201705091300`。
以后移除批量命令的 `--dry-run` 才会真正运行该清单；本次未执行真实多案例实验。
入口使用当前 Python 解释器启动子进程，工作目录固定为项目根目录，串行运行。

`--dry-run` 只查输入、任务依赖和输出冲突，不创建案例目录、不读取雷达数组或运行算法。
完整流程要求起报前 10 分钟至后 60 分钟共 15 帧；选定任务按其实际需要检查。
缺帧直接失败，不填充、不插值、不缩短时效。绘图任务不要求雷达文件。

## 输出与覆盖

```text
outputs/cases/fmi_20160928T160000Z/
  forecasts/       # persistence / optical_flow / sprog / steps_mean.npy
  steps/           # 原始 dB ensemble 和成员图
  metrics/         # 原有 CSV
  evaluation/      # 原有对比与概率评估图
  persistence/     # 保留原算法图的子目录
  optical_flow/
  sprog/
  logs/            # 每个任务一个编号日志
  run_manifest.json
```

默认拒绝已有案例目录。`--overwrite` 只重跑所选任务、覆盖它们的日志和产物，不删除整个目录。
已有目录必须带有相同 case_id 和 start_time 的有效 manifest。运行记录仅保存案例、任务、
状态、UTC 起止时间和必要错误信息，不包含产物校验和、环境版本追踪或 stale 管理。
记录保留未选任务的上次状态；顶层状态表示本次选定任务的执行结果，不代表所有历史任务一致。
若重跑上游预测，应显式同时选择相关下游任务，或默认重跑全流程；框架不会自动判断旧评估是否过期。
不要同时运行写入同一案例的两个进程。

原脚本无参数时仍使用 `201609281600`、原 `outputs/`，包括原有覆盖行为及部分图表的
cwd 相对路径；应像以前一样从项目根目录运行。可配置运行请使用 `run_case.py`，不要直接使用
旧脚本内部的 `--case-run` 标志。旧 `outputs/` 基准不迁移。

## 任务选择与依赖

`--tasks` 接收不重复的两位任务编号，以固定依赖顺序执行，不以参数输入顺序执行。
默认顺序：`01,02,04,05,06,03,07,08,09,10,11,12,13,14`。

| 任务 | 作用 | 前置任务 |
| --- | --- | --- |
| 01、02、04、05 | 四种预测及脚本自带的诊断/评估 | 无 |
| 06 | STEPS 均值、RMSE、成员图 | 05 |
| 03 | 四方法 RMSE 图 | 01、02、04、06 |
| 07 | CSI / POD / FAR | 01、02、04、06 |
| 08 | 多阈值指标图 | 07 |
| 09、11、13、14 | Brier、CRPS、可靠性、Spread-Skill | 05 |
| 10、12 | Brier、CRPS 曲线 | 09、11（分别） |

未选中的前置任务必须在同一案例 manifest 中成功，且所需文件存在且非空。
否则停止该案例并报告缺少的依赖；不自动补跑模型。
13、14 的计算与绘图仍是同一任务，保留不同指标的有效值掩码和统计方式。
任务失败后保留日志与部分产物，后续任务不执行；批量入口继续其他案例并输出 JSON 汇总，
有任一失败时返回非零退出码。人工 Ctrl+C 中断则停止整个批次。

## 验证

```bash
python -m unittest discover -s tests -v
python -m compileall -q scripts tests
```

单元测试使用临时目录和模拟任务，不调用模型。
重构回归只运行参考案例，逐元素比较预测数组与原结果，比较 CSV 数值与图表。
旧基准仅做只读检查。`configs/pystepsrc`、数据、结果、日志不加入 Git。

首次重构验收（2026-10-04）：17 项模拟任务测试通过，14 个原脚本的计算 AST
在排除时间/路径接入后保持一致。只对 `201609281600` 完成一次真实全流程回归：
5 个预测数组逐元素一致（含 NaN），10 份 CSV 字节一致，23 张 PNG 像素一致；
旧 outputs 的全部文件校验值未变化。新案例约占 1.2 GB，14 项任务均成功。
批量入口仅预检了单条参考清单，未运行真实多案例。

## 跨案例 CSV 汇总

`scripts/16_steps_bss.py` 用于单案例计算 BSS relative to Persistence，读取已有
STEPS ensemble、Persistence 预测及未来观测，输出
`metrics/steps_brier_skill_score.csv`；不会重新运行预测方法。它是独立脚本，
不属于当前 `run_case.py --tasks` 的任务编号范围。使用方法：

```bash
python scripts/16_steps_bss.py --start-time 201609281600
```

`scripts/17_case_summary.py` 用于跨案例汇总，读取已有指标 CSV，不重算预测或评价指标。

激活 `radar-nowcasting` 后，在项目根目录运行：

```bash
python scripts/17_case_summary.py --start-times 201609281600 201705091300
python scripts/17_case_summary.py --cases configs/cases.json
```

不传参数时默认读取项目内 `configs/cases.json`；命令行时间列表优先由
`--start-times` 明确指定，不能与 `--cases` 同时使用。当前 `configs/cases.json`
包含 `201609281600` 和 `201705091300` 两个正式验证案例，因此默认运行会汇总这两个案例。

脚本只读取各案例 metrics 中四方法 RMSE、unified_metrics_all_thresholds、
steps_brier_skill_score 和 steps_crps 的现有 CSV。不会重新计算预测、Brier Score
或指标；BSS 汇总的是各案例已经计算的相对 Persistence 的 BSS，而非重新合并 BS 后计算比值。
所有数据验证通过后写入 `outputs/summary/` 的四个文件（同名汇总文件会被覆盖）：

- `rmse_summary.csv`：method、lead_time_min、mean、std、case_count。
- `categorical_summary.csv`：另含 threshold 和 metric（csi/pod/far）。
- `bss_summary.csv`：method=STEPS，reference_method=Persistence，另含 threshold。
- `crps_summary.csv`：method=STEPS，lead_time_min、mean、std、case_count。

各案例等权，std 为样本标准差（ddof=1）。三个阈值 0.1、1.0、5.0 mm/h 分别统计。
case_count 为该分组中有限数值的案例数；源 CSV 的 NaN 会明确警告，均值仅使用有限值。
没有有效案例时 mean/std 为 NaN，只有一个有效案例时 std 为 NaN。
缺文件、空列表、重复案例、错误字段、重复行、缺少阈值或案例间指标行不一致均报错并返回非零状态，
不静默跳过、不补跑任务；输入验证失败时不写入或覆盖 summary 文件。

基础测试：`python -m unittest discover -s tests -p test_case_summary.py -v`。
