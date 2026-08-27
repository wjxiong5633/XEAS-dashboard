save_plot_png <- function(plot, file_path, width, height, dpi = 220) {
  temp_file <- tempfile(fileext = ".png")
  ggsave(
    temp_file, plot,
    width = width, height = height, units = "in",
    dpi = dpi, device = ragg::agg_png,
    bg = "white", limitsize = FALSE
  )
  invisible(file.copy(temp_file, file_path, overwrite = TRUE))
  unlink(temp_file)
}

make_group_plots <- function(result) {
  data <- result$data
  output_dir <- file.path(group_results_dir, result$group_code, "图形")
  dir.create(output_dir, recursive = TRUE, showWarnings = FALSE)
  n_subjects <- n_distinct(data$subject_id)
  plot_height <- max(5.5, ceiling(n_subjects / 5) * 2.2)

  plot_long <- data %>%
    mutate(visit_ordered = factor(visit, levels = paste0("V", 1:6))) %>%
    select(
      subject_id, visit_ordered,
      ygtss_tts, motor_tic_score, vocal_tic_score, impairment_score
    ) %>%
    pivot_longer(
      cols = c(ygtss_tts, motor_tic_score, vocal_tic_score, impairment_score),
      names_to = "metric",
      values_to = "score"
    ) %>%
    mutate(
      metric = factor(
        metric,
        levels = c(
          "ygtss_tts", "motor_tic_score",
          "vocal_tic_score", "impairment_score"
        ),
        labels = c(
          "YGTSS-TTS", "运动抽动总分",
          "发声抽动总分", "总损害分"
        )
      )
    )

  tts_data <- plot_long %>%
    filter(metric != "总损害分") %>%
    left_join(
      result$v5_change_by_subject %>%
        select(
          subject_id, baseline_v1, week8_v5,
          responder_30pct
        ),
      by = "subject_id"
    ) %>%
    mutate(
      facet_subject = if_else(
        !is.na(responder_30pct) & !responder_30pct,
        paste0(subject_id, "（未达30%）"),
        subject_id
      )
    )

  tts_lines <- tts_data %>%
    group_by(facet_subject, metric) %>%
    filter(sum(!is.na(score)) >= 2) %>%
    ungroup()

  nonresponse_labels <- tts_data %>%
    filter(!is.na(responder_30pct) & !responder_30pct) %>%
    distinct(facet_subject) %>%
    mutate(
      visit_ordered = factor("V6", levels = paste0("V", 1:6)),
      label_y = 47
    )

  tts_point_labels <- tts_data %>%
    filter(
      metric == "YGTSS-TTS",
      visit_ordered %in% c("V1", "V5"),
      !is.na(score)
    ) %>%
    mutate(
      score_label = format(score, trim = TRUE, scientific = FALSE)
    )

  facet_levels <- unique(tts_data$facet_subject)
  facet_is_nonresponder <- grepl("未达30%", facet_levels, fixed = TRUE)
  tts_strip <- ggh4x::strip_themed(
    background_x = ggh4x::elem_list_rect(
      fill = ifelse(facet_is_nonresponder, "#C00000", "#F2F2F2"),
      colour = ifelse(facet_is_nonresponder, "#8B0000", "#9E9E9E"),
      linewidth = 0.55
    ),
    text_x = ggh4x::elem_list_text(
      colour = ifelse(facet_is_nonresponder, "#FFFFFF", "#333333"),
      face = "bold",
      size = 7.5
    )
  )

  tts_plot <- ggplot(
    tts_data,
    aes(
      x = visit_ordered, y = score,
      group = metric, colour = metric
    )
  ) +
    geom_line(data = tts_lines, linewidth = 0.55, na.rm = TRUE) +
    geom_point(size = 1.05, na.rm = TRUE) +
    geom_text(
      data = tts_point_labels,
      aes(
        x = visit_ordered,
        y = score,
        label = score_label
      ),
      inherit.aes = FALSE,
      colour = "#1B7837",
      size = 2.5,
      fontface = "bold",
      vjust = -0.75,
      na.rm = TRUE
    ) +
    geom_label(
      data = nonresponse_labels,
      aes(x = visit_ordered, y = label_y, label = "未达30%"),
      inherit.aes = FALSE,
      colour = "#C00000", fill = "#FDE9E7",
      label.size = 0.2, size = 2.2, hjust = 1, fontface = "bold"
    ) +
    ggh4x::facet_wrap2(
      vars(facet_subject), ncol = 5,
      axes = "x", remove_labels = "none", strip = tts_strip
    ) +
    scale_x_discrete(drop = FALSE) +
    scale_colour_manual(
      values = c(
        "YGTSS-TTS" = "#2CA25F",
        "运动抽动总分" = "#3B6FC4",
        "发声抽动总分" = "#E67E22"
      ),
      drop = FALSE
    ) +
    scale_y_continuous(
      limits = c(0, 55),
      breaks = seq(0, 50, 10),
      expand = expansion(mult = c(0.02, 0.02))
    ) +
    labs(
      title = paste0(result$group_label, "：各受试者YGTSS-TTS评分变化趋势"),
      subtitle = paste0(
        "V1=基线，V2=第2周，V3=第4周，V4=第6周，V5=第8周，V6=第12周；",
        "红色标题表示V5较V1降幅不足30%"
      ),
      x = "访视", y = "评分（分）", colour = NULL
    ) +
    theme_minimal(base_size = 10, base_family = "PingFang SC") +
    theme(
      panel.grid.minor = element_blank(),
      panel.border = element_rect(
        colour = "#9E9E9E", fill = NA, linewidth = 0.45
      ),
      panel.spacing = grid::unit(1.0, "lines"),
      axis.text.x = element_text(size = 7),
      plot.title = element_text(face = "bold"),
      legend.position = "top",
      legend.justification = "left"
    )

  save_plot_png(
    tts_plot,
    file.path(output_dir, "YGTSS_TTS_个体趋势图.png"),
    width = 14, height = plot_height
  )

  impairment_data <- plot_long %>% filter(metric == "总损害分")
  impairment_lines <- impairment_data %>%
    group_by(subject_id, metric) %>%
    filter(sum(!is.na(score)) >= 2) %>%
    ungroup()

  impairment_plot <- ggplot(
    impairment_data,
    aes(x = visit_ordered, y = score, group = subject_id)
  ) +
    geom_line(
      data = impairment_lines,
      linewidth = 0.65, colour = "#E6AB02", na.rm = TRUE
    ) +
    geom_point(size = 1.15, colour = "#E6AB02", na.rm = TRUE) +
    facet_wrap(
      vars(subject_id), ncol = 5,
      axes = "all_x", axis.labels = "all_x"
    ) +
    scale_x_discrete(drop = FALSE) +
    scale_y_continuous(limits = c(0, 50), breaks = seq(0, 50, 10)) +
    labs(
      title = paste0(result$group_label, "：各受试者YGTSS总损害分变化趋势"),
      subtitle = "V1=基线，V2=第2周，V3=第4周，V4=第6周，V5=第8周，V6=第12周",
      x = "访视", y = "总损害分（0–50分）"
    ) +
    theme_minimal(base_size = 10, base_family = "PingFang SC") +
    theme(
      panel.grid.minor = element_blank(),
      panel.border = element_rect(
        colour = "#9E9E9E", fill = NA, linewidth = 0.45
      ),
      panel.spacing = grid::unit(1.0, "lines"),
      strip.background = element_rect(
        fill = "#F2F2F2", colour = "#9E9E9E", linewidth = 0.45
      ),
      strip.text = element_text(face = "bold", size = 8),
      axis.text.x = element_text(size = 7),
      plot.title = element_text(face = "bold")
    )

  save_plot_png(
    impairment_plot,
    file.path(output_dir, "YGTSS_总损害分_个体趋势图.png"),
    width = 14, height = plot_height
  )

  line_data <- data %>%
    group_by(subject_id) %>%
    filter(sum(!is.na(ygtss_tts)) >= 2) %>%
    ungroup()

  overall_plot <- ggplot() +
    geom_line(
      data = line_data,
      aes(x = week, y = ygtss_tts, group = subject_id),
      colour = "#BDBDBD", linewidth = 0.35, alpha = 0.45, na.rm = TRUE
    ) +
    geom_errorbar(
      data = result$visit_summary,
      aes(x = week, ymin = mean - se, ymax = mean + se),
      width = 0.35, linewidth = 0.6, colour = "#08519C", na.rm = TRUE
    ) +
    geom_line(
      data = result$visit_summary,
      aes(x = week, y = mean),
      linewidth = 1.1, colour = "#08519C", na.rm = TRUE
    ) +
    geom_point(
      data = result$visit_summary,
      aes(x = week, y = mean),
      size = 2.6, colour = "#D95F0E", na.rm = TRUE
    ) +
    scale_x_continuous(
      breaks = c(0, 2, 4, 6, 8, 12),
      labels = paste0("V", 1:6)
    ) +
    scale_y_continuous(limits = c(0, 50), breaks = seq(0, 50, 5)) +
    labs(
      title = paste0(result$group_label, "：YGTSS-TTS各访视时间点变化趋势"),
      subtitle = paste0(
        "V1=基线，V2=第2周，V3=第4周，V4=第6周，V5=第8周，V6=第12周\n",
        "蓝线为观察均值，误差线为标准误，灰线为各受试者变化趋势"
      ),
      x = "访视时间", y = "YGTSS-TTS（0–50分）"
    ) +
    theme_minimal(base_size = 12, base_family = "PingFang SC") +
    theme(
      panel.grid.minor = element_blank(),
      plot.title = element_text(face = "bold")
    )

  save_plot_png(
    overall_plot,
    file.path(output_dir, "YGTSS_TTS_总体趋势图.png"),
    width = 9, height = 6, dpi = 300
  )

  impairment_line_data <- data %>%
    group_by(subject_id) %>%
    filter(sum(!is.na(impairment_score)) >= 2) %>%
    ungroup()

  impairment_visit_summary <- data %>%
    group_by(visit, week) %>%
    summarise(
      n = sum(!is.na(impairment_score)),
      mean = mean(impairment_score, na.rm = TRUE),
      sd = sd(impairment_score, na.rm = TRUE),
      se = sd / sqrt(n),
      .groups = "drop"
    ) %>%
    mutate(
      mean = if_else(n > 0, mean, NA_real_),
      se = if_else(n > 1, se, NA_real_)
    ) %>%
    arrange(week)

  impairment_overall_plot <- ggplot() +
    geom_line(
      data = impairment_line_data,
      aes(x = week, y = impairment_score, group = subject_id),
      colour = "#BDBDBD", linewidth = 0.35, alpha = 0.45, na.rm = TRUE
    ) +
    geom_errorbar(
      data = impairment_visit_summary,
      aes(x = week, ymin = mean - se, ymax = mean + se),
      width = 0.35, linewidth = 0.6, colour = "#A6761D", na.rm = TRUE
    ) +
    geom_line(
      data = impairment_visit_summary,
      aes(x = week, y = mean),
      linewidth = 1.1, colour = "#A6761D", na.rm = TRUE
    ) +
    geom_point(
      data = impairment_visit_summary,
      aes(x = week, y = mean),
      size = 2.6, colour = "#E6AB02", na.rm = TRUE
    ) +
    scale_x_continuous(
      breaks = c(0, 2, 4, 6, 8, 12),
      labels = paste0("V", 1:6)
    ) +
    scale_y_continuous(limits = c(0, 50), breaks = seq(0, 50, 5)) +
    labs(
      title = paste0(result$group_label, "：YGTSS总损害分各访视时间点变化趋势"),
      subtitle = paste0(
        "V1=基线，V2=第2周，V3=第4周，V4=第6周，V5=第8周，V6=第12周\n",
        "棕色线为观察均值，误差线为标准误，灰线为各受试者变化趋势"
      ),
      x = "访视时间", y = "YGTSS总损害分（0–50分）"
    ) +
    theme_minimal(base_size = 12, base_family = "PingFang SC") +
    theme(
      panel.grid.minor = element_blank(),
      plot.title = element_text(face = "bold")
    )

  save_plot_png(
    impairment_overall_plot,
    file.path(output_dir, "YGTSS_总损害分_总体趋势图.png"),
    width = 9, height = 6, dpi = 300
  )
}
