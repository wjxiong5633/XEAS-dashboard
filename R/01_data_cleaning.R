# 读取人口学数据并建立年龄分组。
data_DM_raw <- read_excel(data_file, sheet = "DM", skip = 1)

if (ncol(data_DM_raw) < 12) {
  stop("DM工作表结构异常：预期至少12列。")
}

dm_names <- names(data_DM_raw)
data_DM <- data_DM_raw %>%
  transmute(
    subject_id = as.character(.data[[dm_names[3]]]),
    sex = as.character(.data[[dm_names[10]]]),
    birth_date = as.character(.data[[dm_names[11]]]),
    age = suppressWarnings(as.numeric(.data[[dm_names[12]]])),
    age_group = case_when(
      age >= 4 & age <= 6 ~ "A组（4–6岁）",
      age > 6 & age <= 10 ~ "B组（>6–10岁）",
      age > 10 & age < 17 ~ "C组（>10–16岁）",
      TRUE ~ NA_character_
    ),
    age_group_status = case_when(
      is.na(age) ~ "年龄缺失",
      age < 4 ~ "低于4岁",
      age >= 17 ~ "高于16岁",
      TRUE ~ "已分组"
    )
  ) %>%
  distinct(subject_id, .keep_all = TRUE)

# 读取YGTSS页。按用户要求，原data_toS01049更名为data_QS_YGTSS。
data_QS_YGTSS <- read_excel(data_file, sheet = "QS_YGTSS", skip = 1)

if (ncol(data_QS_YGTSS) < 27) {
  stop("QS_YGTSS工作表结构异常：预期至少27列。")
}

ygtss_names <- names(data_QS_YGTSS)
ygtss_long_all <- data_QS_YGTSS %>%
  transmute(
    subject_id = as.character(.data[[ygtss_names[3]]]),
    visit = as.character(.data[[ygtss_names[5]]]),
    visit_label = as.character(.data[[ygtss_names[6]]]),
    motor_tic_score = suppressWarnings(as.numeric(.data[[ygtss_names[18]]])),
    vocal_tic_score = suppressWarnings(as.numeric(.data[[ygtss_names[25]]])),
    impairment_score = suppressWarnings(as.numeric(.data[[ygtss_names[26]]])),
    global_severity_score = suppressWarnings(as.numeric(.data[[ygtss_names[27]]]))
  ) %>%
  filter(visit %in% paste0("V", 1:6)) %>%
  mutate(
    week = recode(visit, V1 = 0, V2 = 2, V3 = 4, V4 = 6, V5 = 8, V6 = 12),
    ygtss_tts = if_else(
      is.na(motor_tic_score) | is.na(vocal_tic_score),
      NA_real_,
      motor_tic_score + vocal_tic_score
    )
  ) %>%
  left_join(data_DM, by = "subject_id") %>%
  arrange(subject_id, week)

duplicate_visits <- ygtss_long_all %>%
  count(subject_id, visit) %>%
  filter(n > 1)

if (nrow(duplicate_visits) > 0) {
  stop(
    "发现同一试验参与者同一访视的重复记录：\n",
    paste(capture.output(print(duplicate_visits)), collapse = "\n")
  )
}

saveRDS(data_DM, file.path(intermediate_dir, "data_DM.rds"))
saveRDS(data_QS_YGTSS, file.path(intermediate_dir, "data_QS_YGTSS_raw.rds"))
saveRDS(ygtss_long_all, file.path(intermediate_dir, "ygtss_long_all.rds"))

dm_export <- data_DM %>%
  transmute(
    试验参与者编号 = subject_id,
    性别 = sex,
    出生日期 = birth_date,
    年龄 = age,
    年龄分组 = age_group,
    分组状态 = age_group_status
  )
write_excel_csv_cn(
  dm_export,
  file.path(intermediate_dir, "人口学年龄分组.csv")
)

ygtss_export <- ygtss_long_all %>%
  transmute(
    试验参与者编号 = subject_id,
    年龄 = age,
    年龄分组 = age_group,
    访视 = visit,
    研究周 = week,
    运动抽动总分 = motor_tic_score,
    发声抽动总分 = vocal_tic_score,
    `YGTSS-TTS` = ygtss_tts,
    总损害分 = impairment_score,
    `YGTSS总分（GSS）` = global_severity_score
  )
write_excel_csv_cn(
  ygtss_export,
  file.path(intermediate_dir, "YGTSS清理后纵向数据.csv")
)

cat(
  "数据清理完成：\n",
  "- DM试验参与者：", n_distinct(data_DM$subject_id), "\n",
  "- YGTSS试验参与者：", n_distinct(ygtss_long_all$subject_id), "\n",
  "- A组：", sum(data_DM$age_group == age_group_levels[1], na.rm = TRUE), "\n",
  "- B组：", sum(data_DM$age_group == age_group_levels[2], na.rm = TRUE), "\n",
  "- C组：", sum(data_DM$age_group == age_group_levels[3], na.rm = TRUE), "\n",
  "- 年龄范围外或缺失：", sum(is.na(data_DM$age_group)), "\n",
  sep = ""
)
