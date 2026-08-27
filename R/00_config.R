library(readxl)
library(dplyr)
library(tidyr)
library(ggplot2)

invisible(try(Sys.setlocale("LC_CTYPE", "zh_CN.UTF-8"), silent = TRUE))

data_file <- Sys.getenv(
  "XEAS_DATA_FILE",
  unset = "DATA/Excel_DATA-1.0-2026_07_30_16_33_35.xlsx"
)

intermediate_dir <- "intermediate"
group_results_dir <- "results_by_age"

dir.create(intermediate_dir, recursive = TRUE, showWarnings = FALSE)
dir.create(group_results_dir, recursive = TRUE, showWarnings = FALSE)

age_group_levels <- c(
  "A组（4–6岁）",
  "B组（>6–10岁）",
  "C组（>10–16岁）"
)

analysis_groups <- list(
  list(code = "全年龄组", label = "全年龄组", age_group = NA_character_),
  list(code = "A组_4至6岁", label = "A组（4–6岁）", age_group = "A组（4–6岁）"),
  list(code = "B组_大于6至10岁", label = "B组（>6–10岁）", age_group = "B组（>6–10岁）"),
  list(code = "C组_大于10至16岁", label = "C组（>10–16岁）", age_group = "C组（>10–16岁）")
)

write_excel_csv_cn <- function(data, file_path) {
  dir.create(dirname(file_path), recursive = TRUE, showWarnings = FALSE)
  connection <- file(file_path, open = "wb")
  writeBin(as.raw(c(0xEF, 0xBB, 0xBF)), connection)
  close(connection)
  suppressWarnings(write.table(
    data,
    file = file_path,
    append = TRUE,
    sep = ",",
    row.names = FALSE,
    col.names = TRUE,
    quote = TRUE,
    qmethod = "double",
    na = "",
    fileEncoding = "UTF-8"
  ))
}
