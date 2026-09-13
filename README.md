![lk_dmc — Sri Lanka disaster report archive. Situation reports, weather forecasts, river and flood warnings, and landslide warnings.](docs/assets/dashboard.svg)

# Sri Lanka disaster report archive

Browse reports collected from Sri Lanka's **Disaster Management Centre (DMC)**, with original PDFs, extracted text and tables, and structured exports.

**[Browse data](#archive-coverage)** · **[Workflow runs](https://github.com/Gajarthan/lk_dmc/actions)** · **[Setup guide](docs/guide.md)** · **[Source: DMC](https://www.dmc.gov.lk/)**

[![Collection pipeline](https://github.com/Gajarthan/lk_dmc/actions/workflows/pipeline.yml/badge.svg)](https://github.com/Gajarthan/lk_dmc/actions/workflows/pipeline.yml)
[![Tests](https://github.com/Gajarthan/lk_dmc/actions/workflows/tests.yml/badge.svg)](https://github.com/Gajarthan/lk_dmc/actions/workflows/tests.yml)
[![Dashboard refresh](https://github.com/Gajarthan/lk_dmc/actions/workflows/build_global_readme.yml/badge.svg)](https://github.com/Gajarthan/lk_dmc/actions/workflows/build_global_readme.yml)
Last OpenCode check: [![OpenCode check](https://github.com/Gajarthan/lk_dmc/actions/workflows/opencode-check.yml/badge.svg)](https://github.com/Gajarthan/lk_dmc/actions/workflows/opencode-check.yml)

> This dashboard describes **archived report coverage**, not a live public warning service. Check [DMC](https://www.dmc.gov.lk/) for official information. Workflow badges show run results; the OpenCode check is manual.

## Archive coverage

<!-- DATASETS:START -->

### Coverage

| Reports | Original PDFs | Extracted text | AI analyzed | With tables |
|:---:|:---:|:---:|:---:|:---:|
| **0** | **0** | **0** | **0** | **0** |

**Report files:** 0 B · **Latest summary:** 2026-09-13 06:02 UTC · **Sources reporting:** 4/4

**No reports have been published yet.** [Start collection](https://github.com/Gajarthan/lk_dmc/actions/workflows/pipeline.yml) to populate the archive.

### Dataset monitor

| Dataset | Reports | PDFs | Text | AI | Newest report | Collection |
|---|---:|---:|---:|---:|---|---|
| [Situation reports](https://github.com/Gajarthan/lk_dmc/tree/data_lk_dmc_situation_reports/data/lk_dmc_situation_reports) | 0 | 0 | 0 | 0 | — | Waiting for reports |
| [Weather forecasts](https://github.com/Gajarthan/lk_dmc/tree/data_lk_dmc_weather_forecasts/data/lk_dmc_weather_forecasts) | 0 | 0 | 0 | 0 | — | Waiting for reports |
| [River and flood warnings](https://github.com/Gajarthan/lk_dmc/tree/data_lk_dmc_river_water_level_and_flood_warnings/data/lk_dmc_river_water_level_and_flood_warnings) | 0 | 0 | 0 | 0 | — | Waiting for reports |
| [Landslide warnings](https://github.com/Gajarthan/lk_dmc/tree/data_lk_dmc_landslide_warnings/data/lk_dmc_landslide_warnings) | 0 | 0 | 0 | 0 | — | Waiting for reports |

Counts describe archived files. AI counts include only validated results matching the current source text. **Bounded run** means a collection limit was reached; it does not mean the full source history is archived.

### Recent source reports

Recent report links will appear after a collection run publishes them.

This section refreshes after pipeline completion and on the scheduled dashboard refresh. Workflow badges show the latest workflow result, not real-time service health.

<!-- DATASETS:END -->

## From source to archive

**DMC listings → metadata & original PDFs → extracted text & tables → dataset branches & JSONL exports**

Optional OpenCode analysis adds structured summaries. These are **AI interpretations**; consult the original source reports to verify them. Records retain source links and analysis provenance.

For collection commands, storage layout, analysis configuration, publishing and migration, see the **[setup and pipeline guide](docs/guide.md)**.
