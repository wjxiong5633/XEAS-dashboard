# XEAS YGTSS分析总入口
#
# 运行顺序：
# 1. 配置
# 2. 数据读取与年龄分组
# 3. 评分和应答分析
# 4. 全年龄及A/B/C年龄组绘图
#
# 中间数据保存在 intermediate/，各组结果保存在 results_by_age/。

invisible(try(Sys.setlocale("LC_CTYPE", "zh_CN.UTF-8"), silent = TRUE))

source("R/00_config.R", encoding = "UTF-8")
source("R/01_data_cleaning.R", encoding = "UTF-8")
source("R/02_analysis_functions.R", encoding = "UTF-8")
source("R/03_run_analysis.R", encoding = "UTF-8")
source("R/04_plot_functions.R", encoding = "UTF-8")
source("R/05_make_plots.R", encoding = "UTF-8")

cat(
  "\n全部分析完成。\n",
  "- 中间数据目录：", normalizePath(intermediate_dir), "\n",
  "- 分年龄组结果目录：", normalizePath(group_results_dir), "\n",
  sep = ""
)
