calculate_visit_response <- function(
  data, score_column, thresholds, outcome_label
) {
  baseline <- data %>%
    filter(visit == "V1") %>%
    transmute(subject_id, baseline_score = .data[[score_column]])

  followup <- data %>%
    filter(visit %in% paste0("V", 2:6)) %>%
    transmute(
      subject_id, visit, week,
      followup_score = .data[[score_column]]
    ) %>%
    left_join(baseline, by = "subject_id")

  individual <- tidyr::crossing(
    followup,
    threshold_pct = thresholds
  ) %>%
    mutate(
      outcome = outcome_label,
      evaluable = !is.na(baseline_score) &
        baseline_score != 0 &
        !is.na(followup_score),
      percent_reduction = if_else(
        evaluable,
        100 * (baseline_score - followup_score) / baseline_score,
        NA_real_
      ),
      responder = case_when(
        evaluable ~ percent_reduction >= threshold_pct,
        TRUE ~ NA
      )
    ) %>%
    arrange(threshold_pct, week, subject_id)

  summary <- individual %>%
    filter(evaluable) %>%
    group_by(outcome, visit, week, threshold_pct) %>%
    summarise(
      denominator_n = n(),
      responder_n = sum(responder),
      responder_percent = 100 * responder_n / denominator_n,
      .groups = "drop"
    ) %>%
    rowwise() %>%
    mutate(
      exact_95ci_lower_percent =
        100 * binom.test(responder_n, denominator_n)$conf.int[1],
      exact_95ci_upper_percent =
        100 * binom.test(responder_n, denominator_n)$conf.int[2]
    ) %>%
    ungroup() %>%
    mutate(across(
      c(responder_percent, exact_95ci_lower_percent, exact_95ci_upper_percent),
      \(x) round(x, 2)
    )) %>%
    arrange(threshold_pct, week)

  list(individual = individual, summary = summary)
}

analyse_age_group <- function(data, group_code, group_label) {
  output_dir <- file.path(group_results_dir, group_code)
  dir.create(output_dir, recursive = TRUE, showWarnings = FALSE)

  v5_change_by_subject <- data %>%
    filter(visit %in% c("V1", "V5")) %>%
    select(subject_id, age, age_group, visit, ygtss_tts) %>%
    pivot_wider(names_from = visit, values_from = ygtss_tts) %>%
    rename(baseline_v1 = V1, week8_v5 = V5) %>%
    mutate(
      change_v5_minus_v1 = week8_v5 - baseline_v1,
      reduction_v1_minus_v5 = baseline_v1 - week8_v5,
      percent_reduction = if_else(
        !is.na(baseline_v1) & baseline_v1 != 0 & !is.na(week8_v5),
        100 * reduction_v1_minus_v5 / baseline_v1,
        NA_real_
      ),
      analysis_status = case_when(
        is.na(baseline_v1) & is.na(week8_v5) ~ "V1和V5均缺失",
        is.na(baseline_v1) ~ "V1缺失",
        is.na(week8_v5) ~ "V5缺失",
        baseline_v1 == 0 ~ "V1为0，无法计算降低比例",
        TRUE ~ "可计算"
      ),
      responder_30pct = case_when(
        analysis_status == "可计算" ~ percent_reduction >= 30,
        TRUE ~ NA
      )
    ) %>%
    arrange(subject_id)

  evaluable <- v5_change_by_subject %>%
    filter(!is.na(responder_30pct))
  response_n <- nrow(evaluable)
  response_count <- sum(evaluable$responder_30pct)

  if (response_n > 0) {
    response_ci <- binom.test(response_count, response_n)$conf.int
    response_30pct_summary <- tibble(
      年龄分析组 = group_label,
      应答标准 = "YGTSS-TTS较基线降低至少30%",
      分析人群 = "V1与V5均有评分且V1不为0",
      可评价人数 = response_n,
      应答人数 = response_count,
      `应答比例（%）` = round(100 * response_count / response_n, 2),
      `精确95%CI下限（%）` = round(100 * response_ci[1], 2),
      `精确95%CI上限（%）` = round(100 * response_ci[2], 2)
    )
  } else {
    response_30pct_summary <- tibble(
      年龄分析组 = group_label,
      应答标准 = "YGTSS-TTS较基线降低至少30%",
      分析人群 = "V1与V5均有评分且V1不为0",
      可评价人数 = 0,
      应答人数 = 0,
      `应答比例（%）` = NA_real_,
      `精确95%CI下限（%）` = NA_real_,
      `精确95%CI上限（%）` = NA_real_
    )
  }

  visit_summary <- data %>%
    group_by(visit, week) %>%
    summarise(
      n = sum(!is.na(ygtss_tts)),
      mean = mean(ygtss_tts, na.rm = TRUE),
      sd = sd(ygtss_tts, na.rm = TRUE),
      se = sd / sqrt(n),
      .groups = "drop"
    ) %>%
    mutate(
      mean = if_else(n == 0, NA_real_, mean),
      sd = if_else(n <= 1, NA_real_, sd),
      se = if_else(n <= 1, NA_real_, se),
      across(c(mean, sd, se), \(x) round(x, 2))
    ) %>%
    arrange(week)

  tts_50 <- calculate_visit_response(
    data, "ygtss_tts", 50, "YGTSS-TTS"
  )
  gss_30_50 <- calculate_visit_response(
    data, "global_severity_score", c(30, 50), "YGTSS总分（GSS）"
  )

  v5_export <- v5_change_by_subject %>%
    transmute(
      受试者编号 = subject_id,
      年龄 = age,
      年龄分组 = age_group,
      基线V1评分 = baseline_v1,
      第8周V5评分 = week8_v5,
      V5较V1变化值 = change_v5_minus_v1,
      V1至V5降低值 = reduction_v1_minus_v5,
      `较基线降低百分比（%）` = round(percent_reduction, 2),
      分析状态 = analysis_status,
      `是否降低至少30%` = case_when(
        responder_30pct ~ "是",
        !responder_30pct ~ "否",
        TRUE ~ NA_character_
      )
    )

  visit_export <- visit_summary %>%
    transmute(
      访视 = visit, 研究周 = week, 例数 = n,
      均值 = sprintf("%.2f", mean),
      标准差 = sprintf("%.2f", sd),
      标准误 = sprintf("%.2f", se)
    )

  response_subject_export <- bind_rows(
    tts_50$individual,
    gss_30_50$individual
  ) %>%
    transmute(
      受试者编号 = subject_id,
      访视 = visit,
      研究周 = week,
      结局指标 = outcome,
      降低阈值 = threshold_pct,
      基线评分 = baseline_score,
      随访评分 = followup_score,
      是否可评价 = if_else(evaluable, "是", "否"),
      `较基线降低百分比（%）` = round(percent_reduction, 2),
      是否应答 = case_when(
        responder ~ "是",
        !responder ~ "否",
        TRUE ~ NA_character_
      )
    )

  write_excel_csv_cn(v5_export, file.path(output_dir, "个体V5较V1变化.csv"))
  write_excel_csv_cn(response_30pct_summary, file.path(output_dir, "V5降低30%比例.csv"))
  write_excel_csv_cn(visit_export, file.path(output_dir, "各访视描述统计.csv"))
  write_excel_csv_cn(tts_50$summary, file.path(output_dir, "TTS降低50%比例.csv"))
  write_excel_csv_cn(gss_30_50$summary, file.path(output_dir, "总分降低30和50比例.csv"))
  write_excel_csv_cn(response_subject_export, file.path(output_dir, "逐访视应答明细.csv"))

  result <- list(
    group_code = group_code,
    group_label = group_label,
    data = data,
    v5_change_by_subject = v5_change_by_subject,
    response_30pct_summary = response_30pct_summary,
    visit_summary = visit_summary,
    tts_50 = tts_50,
    gss_30_50 = gss_30_50
  )
  saveRDS(result, file.path(output_dir, "分析结果.rds"))
  result
}

