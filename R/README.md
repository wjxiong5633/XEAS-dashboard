# XEAS YGTSS分析脚本

- `00_config.R`：加载依赖、设置路径、定义年龄组和中文CSV导出函数。
- `01_data_cleaning.R`：读取DM及QS_YGTSS，建立年龄分组，生成中间数据。
- `02_analysis_functions.R`：定义评分变化、应答比例和分组分析函数。
- `03_run_analysis.R`：运行全年龄组及A/B/C年龄组分析并保存结果。
- `04_plot_functions.R`：定义个体趋势图、总损害分图和总体趋势图。
- `05_make_plots.R`：为全年龄组及A/B/C年龄组批量绘图。

在RStudio项目根目录运行 `source("test.R")` 即可执行完整流程。

## 年龄分组

- A组：4–6岁（包含4岁和6岁）
- B组：>6–10岁（包含10岁）
- C组：>10且<17岁（即10岁以上至16岁年龄段；包含16.577岁）
- 全年龄组：保留所有具有正式YGTSS访视记录的试验参与者，包括年龄缺失或超出分层范围者

## 输出

- `intermediate/`：清理后的RDS及中文UTF-8 BOM CSV中间数据。
- `results_by_age/`：全年龄组及A/B/C年龄组的分析表、RDS和图形。
