all_group_results <- readRDS(
  file.path(intermediate_dir, "all_group_results.rds")
)

for (result in all_group_results) {
  make_group_plots(result)
}

