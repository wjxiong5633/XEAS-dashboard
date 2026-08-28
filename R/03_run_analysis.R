ygtss_long_all <- readRDS(file.path(intermediate_dir, "ygtss_long_all.rds"))

all_group_results <- list()

for (group_spec in analysis_groups) {
  group_data <- if (is.na(group_spec$age_group)) {
    ygtss_long_all
  } else {
    ygtss_long_all %>% filter(age_group == group_spec$age_group)
  }

  all_group_results[[group_spec$code]] <- analyse_age_group(
    group_data,
    group_code = group_spec$code,
    group_label = group_spec$label
  )
}

saveRDS(
  all_group_results,
  file.path(intermediate_dir, "all_group_results.rds")
)

group_counts <- bind_rows(lapply(
  all_group_results,
  \(result) tibble(
    年龄分析组 = result$group_label,
    YGTSS试验参与者数 = n_distinct(result$data$subject_id),
    正式访视记录数 = nrow(result$data),
    V1和V5可评价人数 =
      sum(!is.na(result$v5_change_by_subject$responder_30pct)),
    `V5降低至少30%人数` =
      sum(result$v5_change_by_subject$responder_30pct, na.rm = TRUE)
  )
))

write_excel_csv_cn(
  group_counts,
  file.path(group_results_dir, "各年龄组样本量汇总.csv")
)
