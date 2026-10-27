# Screenshot Cleanup Manifest

**Date:** 2026-10-26 (Phase 12A Regeneration)  
**Status:** Complete Inventory and Canonical Classification  
**Total Existing Files in `screenshot/`:** 226

This manifest inventories every image and metric artifact in `screenshot/`, classifies its purpose, records image dimensions, lists references across the repository, and determines whether it should be kept, archived, or deleted.

## Classification Rules & Criteria

1. **Current Approved Screenshots**: Canonical evidence for student chat, course library, profile, reader, and authentication. Strictly preserved.
2. **Current Baseline Screenshots**: Captured baselines for Part 8 & Part 9 administrator redesigns (Desktop 1440x900 and Mobile 390x844). Strictly preserved.
3. **Presentation & Report Evidence**: Images referenced in `report and ppt/` and `scripts/build_major_presentation.py` (e.g. `ppt_evidence/`). Strictly preserved.
4. **Automated Test / QA Targets**: Screenshots generated and verified by active verification scripts (`verify_auth_layout.py`, `verify_course_library_qa.py`, `verify_part6c_qa.py`, `capture_part10a_final.py`, `capture_part10b2_final.py`). Preserved.
5. **Obsolete / Disposable Inspection Captures**: Temporary debugging screenshots with zero references. Deleted.
6. **Historical Baselines**: Earlier redesign captures archived in `screenshot/archive/`.

## Inventory & Classification Table

| # | Screenshot Path | Size (KB) | Dimensions | SHA256 (Prefix) | Classification | References | Action |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | `screenshot/admin/final/activity_desktop.png` | 140 | 1440x900 | `664a30b3` | Current Final Administrator Screenshot | test_archive_safety_contracts.py | **Keep** |
| 2 | `screenshot/admin/final/activity_mobile.png` | 54 | 390x844 | `5d00caf8` | Current Final Administrator Screenshot | None | **Keep** |
| 3 | `screenshot/admin/final/administrators_desktop.png` | 124 | 1440x900 | `38a52b82` | Current Final Administrator Screenshot | None | **Keep** |
| 4 | `screenshot/admin/final/administrators_mobile.png` | 53 | 390x844 | `261633c3` | Current Final Administrator Screenshot | None | **Keep** |
| 5 | `screenshot/admin/final/courses_desktop.png` | 101 | 1440x900 | `2f21e96e` | Current Final Administrator Screenshot | None | **Keep** |
| 6 | `screenshot/admin/final/courses_mobile.png` | 51 | 390x844 | `fb50b39e` | Current Final Administrator Screenshot | None | **Keep** |
| 7 | `screenshot/admin/final/documents_desktop.png` | 119 | 1440x900 | `d142ccc9` | Current Final Administrator Screenshot | None | **Keep** |
| 8 | `screenshot/admin/final/documents_mobile.png` | 43 | 390x844 | `757113b6` | Current Final Administrator Screenshot | None | **Keep** |
| 9 | `screenshot/admin/final/indexing_desktop.png` | 165 | 1440x900 | `4b48e51e` | Current Final Administrator Screenshot | None | **Keep** |
| 10 | `screenshot/admin/final/indexing_mobile.png` | 48 | 390x844 | `ee967231` | Current Final Administrator Screenshot | None | **Keep** |
| 11 | `screenshot/admin/final/overview_desktop.png` | 125 | 1440x900 | `f98ef3cc` | Current Final Administrator Screenshot | None | **Keep** |
| 12 | `screenshot/admin/final/overview_mobile.png` | 59 | 390x844 | `c000b755` | Current Final Administrator Screenshot | None | **Keep** |
| 13 | `screenshot/admin/final/profile_desktop.png` | 100 | 1440x900 | `30752c32` | Current Final Administrator Screenshot | FRONTEND_CHANGELOG.md, TASK_STATE.md, capture_part7b_qa.py (+1 more) | **Keep** |
| 14 | `screenshot/admin/final/profile_mobile.png` | 50 | 390x844 | `f16cfd93` | Current Final Administrator Screenshot | FRONTEND_CHANGELOG.md, TASK_STATE.md, capture_part7b_qa.py (+1 more) | **Keep** |
| 15 | `screenshot/admin/final/system_health_desktop.png` | 141 | 1440x900 | `9ed1725d` | Current Final Administrator Screenshot | FRONTEND_CHANGELOG.md, SYSTEM_DIAGNOSTICS_REDESIGN_CHECKPOINT.md, TASK_STATE.md (+1 more) | **Keep** |
| 16 | `screenshot/admin/final/system_health_mobile.png` | 62 | 390x844 | `4bd7fbfc` | Current Final Administrator Screenshot | FRONTEND_CHANGELOG.md, SYSTEM_DIAGNOSTICS_REDESIGN_CHECKPOINT.md, TASK_STATE.md (+1 more) | **Keep** |
| 17 | `screenshot/admin/final/test_assistant_desktop.png` | 77 | 1440x900 | `1c5c06f6` | Current Final Administrator Screenshot | None | **Keep** |
| 18 | `screenshot/admin/final/test_assistant_mobile.png` | 32 | 390x844 | `100d0b62` | Current Final Administrator Screenshot | None | **Keep** |
| 19 | `screenshot/admin/final/upload_progress_completed.png` | 145 | 1440x900 | `cd3771f2` | Current Final Administrator Screenshot | TASK_STATE.md, capture_upload_progress_qa.py | **Keep** |
| 20 | `screenshot/admin/final/upload_progress_embedding.png` | 139 | 1440x900 | `d528def2` | Current Final Administrator Screenshot | TASK_STATE.md, capture_upload_progress_qa.py | **Keep** |
| 21 | `screenshot/admin/final/upload_progress_extracting.png` | 138 | 1440x900 | `1e06d9d9` | Current Final Administrator Screenshot | TASK_STATE.md, capture_upload_progress_qa.py | **Keep** |
| 22 | `screenshot/admin/final/upload_progress_failed.png` | 145 | 1440x900 | `e3240212` | Current Final Administrator Screenshot | TASK_STATE.md, capture_upload_progress_qa.py | **Keep** |
| 23 | `screenshot/admin/final/upload_progress_indexing_center.png` | 166 | 1440x900 | `feaf3f09` | Current Final Administrator Screenshot | TASK_STATE.md, capture_upload_progress_qa.py | **Keep** |
| 24 | `screenshot/admin/final/upload_progress_uploading.png` | 133 | 1440x900 | `6be57ee4` | Current Final Administrator Screenshot | TASK_STATE.md, capture_upload_progress_qa.py | **Keep** |
| 25 | `screenshot/admin/part10a/01_documents_view_desktop.png` | 120 | 1440x900 | `64f3ac06` | Current Administrator Workflow Evidence | TASK_STATE.md, capture_part10a_final.py | **Keep** |
| 26 | `screenshot/admin/part10a/02_documents_expanded_row_desktop.png` | 123 | 1440x900 | `f0aa220f` | Current Administrator Workflow Evidence | TASK_STATE.md, capture_part10a_final.py | **Keep** |
| 27 | `screenshot/admin/part10a/03_processing_view_desktop.png` | 160 | 1440x900 | `caaca81b` | Current Administrator Workflow Evidence | TASK_STATE.md, capture_part10a_final.py | **Keep** |
| 28 | `screenshot/admin/part10a/04_processing_view_failed_job_desktop.png` | 119 | 1440x900 | `14719342` | Current Administrator Workflow Evidence | TASK_STATE.md, capture_part10a_final.py | **Keep** |
| 29 | `screenshot/admin/part10a/05_courses_page_streamlined_desktop.png` | 78 | 1440x900 | `46f520b9` | Current Administrator Workflow Evidence | TASK_STATE.md, capture_part10a_final.py | **Keep** |
| 30 | `screenshot/admin/part10a/06_updated_sidebar_desktop.png` | 120 | 1440x900 | `64f3ac06` | Current Administrator Workflow Evidence | TASK_STATE.md, capture_part10a_final.py | **Keep** |
| 31 | `screenshot/admin/part10a/07_documents_mobile_390x844.png` | 129 | 780x1688 | `14ecaa32` | Current Administrator Workflow Evidence | TASK_STATE.md, capture_part10a_final.py | **Keep** |
| 32 | `screenshot/admin/part10a/08_student_course_library_regression.png` | 65 | 1440x900 | `ee38c605` | Current Administrator Workflow Evidence | TASK_STATE.md, capture_part10a_final.py | **Keep** |
| 33 | `screenshot/admin/part10a/09_processing_mobile_390x844.png` | 142 | 780x1688 | `69f27e4b` | Current Administrator Workflow Evidence | TASK_STATE.md, capture_part10a_final.py | **Keep** |
| 34 | `screenshot/admin/part10b/01_overview_desktop_live.png` | 136 | 1440x900 | `99d7b571` | Current Administrator Workflow Evidence | FRONTEND_CHANGELOG.md, TASK_STATE.md, capture_part10b_final.py | **Keep** |
| 35 | `screenshot/admin/part10b/02_overview_mobile_390x844.png` | 135 | 780x1688 | `d3b0b65a` | Current Administrator Workflow Evidence | FRONTEND_CHANGELOG.md, TASK_STATE.md, capture_part10b_final.py | **Keep** |
| 36 | `screenshot/admin/part10b/03_system_health_live.png` | 149 | 1440x900 | `db32b886` | Current Administrator Workflow Evidence | FRONTEND_CHANGELOG.md, TASK_STATE.md, capture_part10b_final.py | **Keep** |
| 37 | `screenshot/admin/part10b/04_administrators_readable_courses.png` | 112 | 1440x900 | `8f64c499` | Current Administrator Workflow Evidence | FRONTEND_CHANGELOG.md, TASK_STATE.md, capture_part10b_final.py (+1 more) | **Keep** |
| 38 | `screenshot/admin/part10b/05_administrators_rbac_modal.png` | 104 | 1440x900 | `66a78904` | Current Administrator Workflow Evidence | FRONTEND_CHANGELOG.md, TASK_STATE.md, capture_part10b_final.py (+1 more) | **Keep** |
| 39 | `screenshot/admin/part10b/06_administrators_catalog_error.png` | 124 | 1440x900 | `f67ab6a4` | Current Administrator Workflow Evidence | FRONTEND_CHANGELOG.md, TASK_STATE.md, capture_part10b_final.py (+1 more) | **Keep** |
| 40 | `screenshot/admin/part10b1/system_diagnostics_desktop.png` | 147 | 1440x900 | `496e706e` | Current Administrator Workflow Evidence | FRONTEND_CHANGELOG.md, TASK_STATE.md, capture_part10b1_final.py | **Keep** |
| 41 | `screenshot/admin/part10b1/system_diagnostics_mobile.png` | 155 | 780x1688 | `d70e4e16` | Current Administrator Workflow Evidence | FRONTEND_CHANGELOG.md, TASK_STATE.md, capture_part10b1_final.py | **Keep** |
| 42 | `screenshot/admin/part10b2/system_health_desktop.png` | 133 | 1440x900 | `e4fb6c97` | Current Administrator Workflow Evidence | FRONTEND_CHANGELOG.md, SYSTEM_DIAGNOSTICS_REDESIGN_CHECKPOINT.md, TASK_STATE.md (+1 more) | **Keep** |
| 43 | `screenshot/admin/part10b2/system_health_mobile.png` | 140 | 780x1688 | `9bae40e0` | Current Administrator Workflow Evidence | FRONTEND_CHANGELOG.md, SYSTEM_DIAGNOSTICS_REDESIGN_CHECKPOINT.md, TASK_STATE.md (+1 more) | **Keep** |
| 44 | `screenshot/admin/part9a/delete_dialog_open.png` | 110 | 1440x900 | `ccd00716` | Current Administrator Workflow Evidence | TASK_STATE.md, capture_part9a_final.py | **Keep** |
| 45 | `screenshot/admin/part9a/documents_before_desktop.png` | 92 | 1440x900 | `a73ae12c` | Current Administrator Workflow Evidence | TASK_STATE.md, capture_part9a_baseline.py | **Keep** |
| 46 | `screenshot/admin/part9a/documents_before_mobile.png` | 42 | 390x844 | `3737b589` | Current Administrator Workflow Evidence | TASK_STATE.md, capture_part9a_baseline.py | **Keep** |
| 47 | `screenshot/admin/part9a/documents_final_desktop.png` | 91 | 1440x900 | `af401816` | Current Administrator Workflow Evidence | TASK_STATE.md, capture_part9a_final.py | **Keep** |
| 48 | `screenshot/admin/part9a/documents_final_mobile.png` | 42 | 390x844 | `5baeec54` | Current Administrator Workflow Evidence | TASK_STATE.md, capture_part9a_final.py | **Keep** |
| 49 | `screenshot/admin/part9a/upload_dialog_before.png` | 107 | 1440x900 | `bfdc9e69` | Current Administrator Workflow Evidence | TASK_STATE.md, capture_part9a_baseline.py | **Keep** |
| 50 | `screenshot/admin/part9a/upload_dialog_final.png` | 113 | 1440x900 | `ff3ec574` | Current Administrator Workflow Evidence | TASK_STATE.md, capture_part9a_final.py | **Keep** |
| 51 | `screenshot/admin/part9a/upload_progress_final.png` | 116 | 1440x900 | `b6d7b409` | Current Administrator Workflow Evidence | TASK_STATE.md, capture_part9a_final.py | **Keep** |
| 52 | `screenshot/admin/part9b/01_documents_desktop_collapsed.png` | 98 | 1440x900 | `31901121` | Current Administrator Workflow Evidence | capture_part9b_final.py | **Keep** |
| 53 | `screenshot/admin/part9b/02_documents_desktop_expanded.png` | 109 | 1440x900 | `8331543c` | Current Administrator Workflow Evidence | capture_part9b_final.py | **Keep** |
| 54 | `screenshot/admin/part9b/03_dropzone_clean.png` | 109 | 1440x900 | `8331543c` | Current Administrator Workflow Evidence | capture_part9b_final.py | **Keep** |
| 55 | `screenshot/admin/part9b/04_dropzone_file_selected.png` | 112 | 1440x900 | `cbc4845f` | Current Administrator Workflow Evidence | capture_part9b_final.py | **Keep** |
| 56 | `screenshot/admin/part9b/05_upload_active_processing.png` | 112 | 1440x900 | `6b201f8a` | Current Administrator Workflow Evidence | capture_part9b_final.py | **Keep** |
| 57 | `screenshot/admin/part9b/06_upload_completed_state.png` | 112 | 1440x900 | `6b201f8a` | Current Administrator Workflow Evidence | capture_part9b_final.py | **Keep** |
| 58 | `screenshot/admin/part9b/07_documents_table_persistent_progress.png` | 108 | 1440x900 | `820fe02d` | Current Administrator Workflow Evidence | capture_part9b_final.py | **Keep** |
| 59 | `screenshot/admin/part9b/08_indexing_center_view.png` | 133 | 1440x900 | `269a3203` | Current Administrator Workflow Evidence | capture_part9b_final.py | **Keep** |
| 60 | `screenshot/admin/part9b/09_documents_laptop_1366x768.png` | 95 | 1366x768 | `a936c51a` | Current Administrator Workflow Evidence | capture_part9b_final.py | **Keep** |
| 61 | `screenshot/admin/part9b/10_documents_tablet_768x1024.png` | 74 | 768x1024 | `4093b4f4` | Current Administrator Workflow Evidence | capture_part9b_final.py | **Keep** |
| 62 | `screenshot/admin/part9b/11_documents_mobile_390x844.png` | 44 | 390x844 | `e5a98985` | Current Administrator Workflow Evidence | capture_part9b_final.py | **Keep** |
| 63 | `screenshot/admin/part9b/12_documents_compact_mobile_375x667.png` | 38 | 375x667 | `73fc3e36` | Current Administrator Workflow Evidence | capture_part9b_final.py | **Keep** |
| 64 | `screenshot/admin/part9c/01_documents_desktop_idle.png` | 112 | 1440x900 | `8eba0519` | Current Administrator Workflow Evidence | FRONTEND_CHANGELOG.md, TASK_STATE.md, UPLOAD_REDESIGN_CHECKPOINT.md (+4 more) | **Keep** |
| 65 | `screenshot/admin/part9c/02_documents_desktop_target_selected.png` | 113 | 1440x900 | `87d79351` | Current Administrator Workflow Evidence | FRONTEND_CHANGELOG.md, TASK_STATE.md, UPLOAD_REDESIGN_CHECKPOINT.md (+4 more) | **Keep** |
| 66 | `screenshot/admin/part9c/03_documents_desktop_file_selected.png` | 117 | 1440x900 | `99e82fe3` | Current Administrator Workflow Evidence | FRONTEND_CHANGELOG.md, TASK_STATE.md, UPLOAD_REDESIGN_CHECKPOINT.md (+4 more) | **Keep** |
| 67 | `screenshot/admin/part9c/04_documents_desktop_processing.png` | 116 | 1440x900 | `2986ce42` | Current Administrator Workflow Evidence | FRONTEND_CHANGELOG.md, TASK_STATE.md, UPLOAD_REDESIGN_CHECKPOINT.md (+4 more) | **Keep** |
| 68 | `screenshot/admin/part9c/05_documents_desktop_completed.png` | 114 | 1440x900 | `9ee00f22` | Current Administrator Workflow Evidence | FRONTEND_CHANGELOG.md, TASK_STATE.md, UPLOAD_REDESIGN_CHECKPOINT.md (+4 more) | **Keep** |
| 69 | `screenshot/admin/part9c/06_documents_desktop_search_filtered.png` | 102 | 1440x900 | `c7491c0d` | Current Administrator Workflow Evidence | FRONTEND_CHANGELOG.md, TASK_STATE.md, capture_part9c_final.py (+1 more) | **Keep** |
| 70 | `screenshot/admin/part9c/07_indexing_center_view.png` | 146 | 1440x900 | `8dad3f06` | Current Administrator Workflow Evidence | FRONTEND_CHANGELOG.md, TASK_STATE.md, capture_part9c_final.py (+1 more) | **Keep** |
| 71 | `screenshot/admin/part9c/08_documents_mobile_390x844.png` | 108 | 780x1688 | `589f7f7d` | Current Administrator Workflow Evidence | FRONTEND_CHANGELOG.md, TASK_STATE.md, UPLOAD_REDESIGN_CHECKPOINT.md (+4 more) | **Keep** |
| 72 | `screenshot/admin/part9c/09_documents_compact_mobile_375x667.png` | 83 | 750x1334 | `d79d268d` | Current Administrator Workflow Evidence | FRONTEND_CHANGELOG.md, TASK_STATE.md, UPLOAD_REDESIGN_CHECKPOINT.md (+4 more) | **Keep** |
| 73 | `screenshot/admin/part9d/01_documents_desktop_idle.png` | 122 | 1440x900 | `5bdc2c35` | Current Administrator Workflow Evidence | FRONTEND_CHANGELOG.md, TASK_STATE.md, UPLOAD_REDESIGN_CHECKPOINT.md (+4 more) | **Keep** |
| 74 | `screenshot/admin/part9d/02_documents_desktop_target_selected.png` | 121 | 1440x900 | `b3c21c6d` | Current Administrator Workflow Evidence | FRONTEND_CHANGELOG.md, TASK_STATE.md, UPLOAD_REDESIGN_CHECKPOINT.md (+4 more) | **Keep** |
| 75 | `screenshot/admin/part9d/03_documents_desktop_file_selected.png` | 121 | 1440x900 | `337fd534` | Current Administrator Workflow Evidence | FRONTEND_CHANGELOG.md, TASK_STATE.md, UPLOAD_REDESIGN_CHECKPOINT.md (+4 more) | **Keep** |
| 76 | `screenshot/admin/part9d/04_documents_desktop_processing.png` | 121 | 1440x900 | `ac7695a8` | Current Administrator Workflow Evidence | FRONTEND_CHANGELOG.md, TASK_STATE.md, UPLOAD_REDESIGN_CHECKPOINT.md (+4 more) | **Keep** |
| 77 | `screenshot/admin/part9d/05_documents_desktop_completed.png` | 117 | 1440x900 | `f3e8b3de` | Current Administrator Workflow Evidence | FRONTEND_CHANGELOG.md, TASK_STATE.md, UPLOAD_REDESIGN_CHECKPOINT.md (+4 more) | **Keep** |
| 78 | `screenshot/admin/part9d/06_documents_desktop_search_filtered.png` | 107 | 1440x900 | `8bd36e14` | Current Administrator Workflow Evidence | FRONTEND_CHANGELOG.md, TASK_STATE.md, capture_part9c_final.py (+1 more) | **Keep** |
| 79 | `screenshot/admin/part9d/07_indexing_center_view.png` | 146 | 1440x900 | `e48406cd` | Current Administrator Workflow Evidence | FRONTEND_CHANGELOG.md, TASK_STATE.md, capture_part9c_final.py (+1 more) | **Keep** |
| 80 | `screenshot/admin/part9d/08_documents_mobile_390x844.png` | 111 | 780x1688 | `5c6b56a5` | Current Administrator Workflow Evidence | FRONTEND_CHANGELOG.md, TASK_STATE.md, UPLOAD_REDESIGN_CHECKPOINT.md (+4 more) | **Keep** |
| 81 | `screenshot/admin/part9d/09_documents_compact_mobile_375x667.png` | 101 | 750x1334 | `81f94e3c` | Current Administrator Workflow Evidence | FRONTEND_CHANGELOG.md, TASK_STATE.md, UPLOAD_REDESIGN_CHECKPOINT.md (+4 more) | **Keep** |
| 82 | `screenshot/admin/part9e/01_documents_desktop_idle.png` | 122 | 1440x900 | `7debca1b` | Current Administrator Workflow Evidence | FRONTEND_CHANGELOG.md, TASK_STATE.md, UPLOAD_REDESIGN_CHECKPOINT.md (+4 more) | **Keep** |
| 83 | `screenshot/admin/part9e/02_documents_desktop_target_selected.png` | 121 | 1440x900 | `3f1a965f` | Current Administrator Workflow Evidence | FRONTEND_CHANGELOG.md, TASK_STATE.md, UPLOAD_REDESIGN_CHECKPOINT.md (+4 more) | **Keep** |
| 84 | `screenshot/admin/part9e/03_documents_desktop_file_selected.png` | 121 | 1440x900 | `646f8d6f` | Current Administrator Workflow Evidence | FRONTEND_CHANGELOG.md, TASK_STATE.md, UPLOAD_REDESIGN_CHECKPOINT.md (+4 more) | **Keep** |
| 85 | `screenshot/admin/part9e/04_documents_desktop_processing.png` | 121 | 1440x900 | `f3d2936f` | Current Administrator Workflow Evidence | FRONTEND_CHANGELOG.md, TASK_STATE.md, UPLOAD_REDESIGN_CHECKPOINT.md (+4 more) | **Keep** |
| 86 | `screenshot/admin/part9e/05_documents_desktop_completed.png` | 121 | 1440x900 | `4a3ed6f8` | Current Administrator Workflow Evidence | FRONTEND_CHANGELOG.md, TASK_STATE.md, UPLOAD_REDESIGN_CHECKPOINT.md (+4 more) | **Keep** |
| 87 | `screenshot/admin/part9e/06_documents_laptop_1366x768.png` | 102 | 1366x768 | `a39e0174` | Current Administrator Workflow Evidence | TASK_STATE.md, UPLOAD_REDESIGN_CHECKPOINT.md, capture_part9e_final.py (+1 more) | **Keep** |
| 88 | `screenshot/admin/part9e/07_documents_tablet_768x1024.png` | 207 | 1536x2048 | `05b131d2` | Current Administrator Workflow Evidence | TASK_STATE.md, UPLOAD_REDESIGN_CHECKPOINT.md, capture_part9e_final.py (+1 more) | **Keep** |
| 89 | `screenshot/admin/part9e/08_documents_mobile_390x844.png` | 179 | 1170x2532 | `5ff71641` | Current Administrator Workflow Evidence | FRONTEND_CHANGELOG.md, TASK_STATE.md, UPLOAD_REDESIGN_CHECKPOINT.md (+4 more) | **Keep** |
| 90 | `screenshot/admin/part9e/09_documents_compact_mobile_375x667.png` | 91 | 750x1334 | `ca55f196` | Current Administrator Workflow Evidence | FRONTEND_CHANGELOG.md, TASK_STATE.md, UPLOAD_REDESIGN_CHECKPOINT.md (+4 more) | **Keep** |
| 91 | `screenshot/admin/part9e/geometry_metrics.json` | 4 | N/A | `19522ee5` | Current Administrator Workflow Evidence | FRONTEND_CHANGELOG.md, TASK_STATE.md, UPLOAD_REDESIGN_CHECKPOINT.md (+2 more) | **Keep** |
| 92 | `screenshot/admin/part9e_baseline/01_baseline_desktop_1440x900.png` | 123 | 1440x900 | `89505e0c` | Baseline Administrator Evidence | capture_part9e_baseline.py | **Keep** |
| 93 | `screenshot/admin/part9e_baseline/02_baseline_laptop_1366x768.png` | 107 | 1366x768 | `4cfd1b60` | Baseline Administrator Evidence | capture_part9e_baseline.py | **Keep** |
| 94 | `screenshot/admin/part9e_baseline/03_baseline_mobile_390x844.png` | 174 | 1170x2532 | `692ca998` | Baseline Administrator Evidence | capture_part9e_baseline.py | **Keep** |
| 95 | `screenshot/admin/part9e_baseline/04_baseline_compact_mobile_375x667.png` | 101 | 750x1334 | `81f94e3c` | Baseline Administrator Evidence | capture_part9e_baseline.py | **Keep** |
| 96 | `screenshot/admin/part9f/00_baseline_desktop_1440x900.png` | 124 | 1440x900 | `4895b5b4` | Baseline Administrator Evidence | capture_part9f_baseline.py | **Keep** |
| 97 | `screenshot/admin/part9f/00_baseline_mobile_390x844.png` | 104 | 780x1688 | `fb451b10` | Baseline Administrator Evidence | capture_part9f_baseline.py | **Keep** |
| 98 | `screenshot/admin/part9f/01_documents_desktop_idle.png` | 113 | 1440x900 | `3ff339aa` | Current Administrator Workflow Evidence | FRONTEND_CHANGELOG.md, TASK_STATE.md, UPLOAD_REDESIGN_CHECKPOINT.md (+4 more) | **Keep** |
| 99 | `screenshot/admin/part9f/02_documents_desktop_target_selected.png` | 112 | 1440x900 | `d4708d5c` | Current Administrator Workflow Evidence | FRONTEND_CHANGELOG.md, TASK_STATE.md, UPLOAD_REDESIGN_CHECKPOINT.md (+4 more) | **Keep** |
| 100 | `screenshot/admin/part9f/03_documents_desktop_file_selected.png` | 118 | 1440x900 | `85de79d9` | Current Administrator Workflow Evidence | FRONTEND_CHANGELOG.md, TASK_STATE.md, UPLOAD_REDESIGN_CHECKPOINT.md (+4 more) | **Keep** |
| 101 | `screenshot/admin/part9f/04_documents_desktop_processing.png` | 118 | 1440x900 | `2e3d052b` | Current Administrator Workflow Evidence | FRONTEND_CHANGELOG.md, TASK_STATE.md, UPLOAD_REDESIGN_CHECKPOINT.md (+4 more) | **Keep** |
| 102 | `screenshot/admin/part9f/05_documents_desktop_completed.png` | 115 | 1440x900 | `af17b702` | Current Administrator Workflow Evidence | FRONTEND_CHANGELOG.md, TASK_STATE.md, UPLOAD_REDESIGN_CHECKPOINT.md (+4 more) | **Keep** |
| 103 | `screenshot/admin/part9f/06_documents_laptop_1366x768.png` | 98 | 1366x768 | `87de75e1` | Current Administrator Workflow Evidence | TASK_STATE.md, UPLOAD_REDESIGN_CHECKPOINT.md, capture_part9e_final.py (+1 more) | **Keep** |
| 104 | `screenshot/admin/part9f/07_documents_tablet_768x1024.png` | 87 | 768x1024 | `70e18779` | Current Administrator Workflow Evidence | TASK_STATE.md, UPLOAD_REDESIGN_CHECKPOINT.md, capture_part9e_final.py (+1 more) | **Keep** |
| 105 | `screenshot/admin/part9f/08_documents_mobile_390x844.png` | 109 | 780x1688 | `289bae55` | Current Administrator Workflow Evidence | FRONTEND_CHANGELOG.md, TASK_STATE.md, UPLOAD_REDESIGN_CHECKPOINT.md (+4 more) | **Keep** |
| 106 | `screenshot/admin/part9f/09_documents_compact_mobile_375x667.png` | 96 | 750x1334 | `e951512b` | Current Administrator Workflow Evidence | FRONTEND_CHANGELOG.md, TASK_STATE.md, UPLOAD_REDESIGN_CHECKPOINT.md (+4 more) | **Keep** |
| 107 | `screenshot/admin/part9f/geometry_metrics.json` | 1 | N/A | `9380f170` | Current Administrator Workflow Evidence | FRONTEND_CHANGELOG.md, TASK_STATE.md, UPLOAD_REDESIGN_CHECKPOINT.md (+2 more) | **Keep** |
| 108 | `screenshot/admin_baseline_part8_activity_desktop.png` | 137 | 1440x900 | `80d700f7` | Part 8 Administrator Baseline | None | **Keep** |
| 109 | `screenshot/admin_baseline_part8_activity_mobile.png` | 40 | 390x844 | `806dd713` | Part 8 Administrator Baseline | None | **Keep** |
| 110 | `screenshot/admin_baseline_part8_administrators_desktop.png` | 99 | 1440x900 | `7b3618e8` | Part 8 Administrator Baseline | None | **Keep** |
| 111 | `screenshot/admin_baseline_part8_administrators_mobile.png` | 38 | 390x844 | `fa71b9cd` | Part 8 Administrator Baseline | None | **Keep** |
| 112 | `screenshot/admin_baseline_part8_courses_desktop.png` | 80 | 1440x900 | `c5a0ccf5` | Part 8 Administrator Baseline | None | **Keep** |
| 113 | `screenshot/admin_baseline_part8_courses_mobile.png` | 38 | 390x844 | `cf279444` | Part 8 Administrator Baseline | None | **Keep** |
| 114 | `screenshot/admin_baseline_part8_documents_desktop.png` | 77 | 1440x900 | `a81c402a` | Part 8 Administrator Baseline | None | **Keep** |
| 115 | `screenshot/admin_baseline_part8_documents_mobile.png` | 37 | 390x844 | `c7d237c3` | Part 8 Administrator Baseline | None | **Keep** |
| 116 | `screenshot/admin_baseline_part8_indexing_desktop.png` | 83 | 1440x900 | `811754c3` | Part 8 Administrator Baseline | None | **Keep** |
| 117 | `screenshot/admin_baseline_part8_indexing_mobile.png` | 35 | 390x844 | `2d349c74` | Part 8 Administrator Baseline | None | **Keep** |
| 118 | `screenshot/admin_baseline_part8_overview_desktop.png` | 136 | 1440x900 | `71702f08` | Part 8 Administrator Baseline | None | **Keep** |
| 119 | `screenshot/admin_baseline_part8_overview_mobile.png` | 39 | 390x844 | `6715f421` | Part 8 Administrator Baseline | None | **Keep** |
| 120 | `screenshot/admin_baseline_part8_profile_desktop.png` | 102 | 1440x900 | `be2fcc3b` | Part 8 Administrator Baseline | None | **Keep** |
| 121 | `screenshot/admin_baseline_part8_profile_mobile.png` | 38 | 390x844 | `8cbf03e6` | Part 8 Administrator Baseline | None | **Keep** |
| 122 | `screenshot/admin_baseline_part8_system_health_desktop.png` | 118 | 1440x900 | `ba15696d` | Part 8 Administrator Baseline | None | **Keep** |
| 123 | `screenshot/admin_baseline_part8_system_health_mobile.png` | 36 | 390x844 | `db39d492` | Part 8 Administrator Baseline | None | **Keep** |
| 124 | `screenshot/admin_baseline_part8_test_assistant_desktop.png` | 78 | 1440x900 | `22877d2f` | Part 8 Administrator Baseline | None | **Keep** |
| 125 | `screenshot/admin_baseline_part8_test_assistant_mobile.png` | 38 | 390x844 | `f39cbbc2` | Part 8 Administrator Baseline | None | **Keep** |
| 126 | `screenshot/admin_dashboard_preserved.png` | 70 | 1440x900 | `b6c781b9` | Referenced QA Asset | FRONTEND_CHANGELOG.md, verify_part6b_qa.py | **Keep** |
| 127 | `screenshot/admin_knowledge_bases_no_breadcrumbs.png` | 77 | 1440x900 | `ccb895ce` | Referenced QA Asset | TASK_STATE.md, capture_part7b_qa.py | **Keep** |
| 128 | `screenshot/admin_navigation_baseline_desktop.png` | 70 | 1440x900 | `8099ab36` | Referenced QA Asset | capture_admin_baseline.py | **Keep** |
| 129 | `screenshot/admin_navigation_baseline_mobile.png` | 72 | 780x1688 | `7094e4be` | Referenced QA Asset | capture_admin_baseline.py | **Keep** |
| 130 | `screenshot/admin_overview_baseline_desktop.png` | 70 | 1440x900 | `8099ab36` | Referenced QA Asset | capture_admin_baseline.py | **Keep** |
| 131 | `screenshot/admin_overview_baseline_mobile.png` | 77 | 780x1688 | `ce967252` | Referenced QA Asset | capture_admin_baseline.py | **Keep** |
| 132 | `screenshot/admin_profile_baseline.png` | 120 | 1440x900 | `97df8e0b` | Referenced QA Asset | FRONTEND_CHANGELOG.md, TASK_STATE.md, capture_profile_baseline.py | **Keep** |
| 133 | `screenshot/admin_profile_desktop.png` | 99 | 1440x900 | `06965620` | Referenced QA Asset | FRONTEND_CHANGELOG.md, TASK_STATE.md, capture_part7b_qa.py (+1 more) | **Keep** |
| 134 | `screenshot/archive/admin_navigation_part8a_desktop.png` | 136 | 1440x900 | `4825d8b1` | Archived Part 8A Intermediate Baseline | FRONTEND_CHANGELOG.md, TASK_STATE.md, capture_admin_part8a.py (+1 more) | **Archived** |
| 135 | `screenshot/archive/admin_navigation_part8a_mobile.png` | 86 | 780x1688 | `62d7e1d5` | Archived Part 8A Intermediate Baseline | FRONTEND_CHANGELOG.md, TASK_STATE.md, capture_admin_part8a.py | **Archived** |
| 136 | `screenshot/archive/admin_overview_part8a_compact.png` | 103 | 750x1334 | `6b08e11e` | Archived Part 8A Intermediate Baseline | FRONTEND_CHANGELOG.md, TASK_STATE.md, capture_admin_part8a.py | **Archived** |
| 137 | `screenshot/archive/admin_overview_part8a_desktop.png` | 136 | 1440x900 | `4825d8b1` | Archived Part 8A Intermediate Baseline | FRONTEND_CHANGELOG.md, TASK_STATE.md, capture_admin_part8a.py | **Archived** |
| 138 | `screenshot/archive/admin_overview_part8a_mobile.png` | 137 | 780x1688 | `c6738333` | Archived Part 8A Intermediate Baseline | FRONTEND_CHANGELOG.md, TASK_STATE.md, capture_admin_part8a.py | **Archived** |
| 139 | `screenshot/archive/admin_overview_part8a_tablet.png` | 102 | 768x1024 | `dedb1575` | Archived Part 8A Intermediate Baseline | FRONTEND_CHANGELOG.md, TASK_STATE.md, capture_admin_part8a.py | **Archived** |
| 140 | `screenshot/auth_admin_login_desktop_direct.png` | 81 | 1503x1000 | `11fa4db3` | Auth Workflow Evidence | TASK_STATE.md, build_chapters_4_to_6.py, verify_auth_layout.py | **Keep** |
| 141 | `screenshot/auth_admin_login_from_nav.png` | 81 | 1503x1000 | `11fa4db3` | Auth Workflow Evidence | TASK_STATE.md, verify_auth_layout.py | **Keep** |
| 142 | `screenshot/auth_admin_login_mobile_390.png` | 52 | 390x844 | `0a364a1f` | Auth Workflow Evidence | TASK_STATE.md, verify_auth_layout.py | **Keep** |
| 143 | `screenshot/auth_landing_desktop.png` | 107 | 1503x1000 | `a84bcf23` | Auth Workflow Evidence | TASK_STATE.md, build_chapters_4_to_6.py, verify_auth_layout.py | **Keep** |
| 144 | `screenshot/auth_layout_metrics.json` | 4 | N/A | `1846d5ff` | Auth Workflow Evidence | verify_auth_layout.py | **Keep** |
| 145 | `screenshot/auth_register_desktop.png` | 85 | 1503x1000 | `4d217259` | Auth Workflow Evidence | TASK_STATE.md, verify_auth_layout.py | **Keep** |
| 146 | `screenshot/auth_register_mobile_390.png` | 50 | 390x844 | `fcf7fb52` | Auth Workflow Evidence | TASK_STATE.md, verify_auth_layout.py | **Keep** |
| 147 | `screenshot/auth_student_login_compact_375.png` | 41 | 375x667 | `deea9aa8` | Auth Workflow Evidence | TASK_STATE.md, verify_auth_layout.py | **Keep** |
| 148 | `screenshot/auth_student_login_desktop.png` | 79 | 1503x1000 | `ad8149e0` | Auth Workflow Evidence | TASK_STATE.md, build_chapters_4_to_6.py, verify_auth_layout.py | **Keep** |
| 149 | `screenshot/auth_student_login_laptop_1366.png` | 68 | 1366x768 | `0a76db4e` | Auth Workflow Evidence | TASK_STATE.md, verify_auth_layout.py | **Keep** |
| 150 | `screenshot/auth_student_login_mobile_390.png` | 49 | 390x844 | `b3a7dc4a` | Auth Workflow Evidence | TASK_STATE.md, verify_auth_layout.py | **Keep** |
| 151 | `screenshot/auth_student_login_tablet_768.png` | 60 | 768x1024 | `9ca214a6` | Auth Workflow Evidence | TASK_STATE.md, verify_auth_layout.py | **Keep** |
| 152 | `screenshot/chat_composer_scope_menu_open.png` | 88 | 1440x900 | `e6b084e4` | Referenced QA Asset | FRONTEND_CHANGELOG.md, TASK_STATE.md, build_chapters_4_to_6.py (+1 more) | **Keep** |
| 153 | `screenshot/chat_concise_grouped_citations.png` | 85 | 1440x900 | `0c09733f` | Presentation / Report Evidence | FRONTEND_CHANGELOG.md, PPT_COMPLETION_NOTES.md, REPORT_FACTS_FOR_PPT.md (+6 more) | **Keep** |
| 154 | `screenshot/chat_desktop_history.png` | 85 | 1440x900 | `0c09733f` | Referenced QA Asset | FRONTEND_CHANGELOG.md, TASK_STATE.md, build_chapters_4_to_6.py (+1 more) | **Keep** |
| 155 | `screenshot/chat_evidence_drawer.png` | 143 | 1434x900 | `cec87a61` | Referenced QA Asset | FRONTEND_CHANGELOG.md, TASK_STATE.md | **Keep** |
| 156 | `screenshot/chat_mobile_composer.png` | 26 | 390x844 | `54e50e7f` | Referenced QA Asset | FRONTEND_CHANGELOG.md, REPORT_FACTS_FOR_PPT.md, TASK_STATE.md (+1 more) | **Keep** |
| 157 | `screenshot/chat_mobile_composer_scope.png` | 50 | 390x844 | `2d75f641` | Referenced QA Asset | FRONTEND_CHANGELOG.md, TASK_STATE.md, capture_chat_part2e.py | **Keep** |
| 158 | `screenshot/chat_new_chat_clean.png` | 65 | 1440x900 | `efa0e159` | Referenced QA Asset | FRONTEND_CHANGELOG.md, TASK_STATE.md, capture_chat_part2e.py | **Keep** |
| 159 | `screenshot/chat_sidebar_desktop.png` | 65 | 1440x900 | `19c07980` | Referenced QA Asset | FRONTEND_CHANGELOG.md, TASK_STATE.md, build_chapters_4_to_6.py (+1 more) | **Keep** |
| 160 | `screenshot/chat_sidebar_mobile.png` | 33 | 390x875 | `ef8c3483` | Referenced QA Asset | FRONTEND_CHANGELOG.md, TASK_STATE.md | **Keep** |
| 161 | `screenshot/chat_specific_course_selected.png` | 67 | 1440x900 | `9d8577d1` | Referenced QA Asset | FRONTEND_CHANGELOG.md, TASK_STATE.md, capture_chat.py (+1 more) | **Keep** |
| 162 | `screenshot/chat_stop_generating.png` | 50 | 1440x900 | `4ccac1c2` | Referenced QA Asset | FRONTEND_CHANGELOG.md, TASK_STATE.md, build_chapters_4_to_6.py (+1 more) | **Keep** |
| 163 | `screenshot/course_library_admin_view.png` | 82 | 1440x900 | `a4d545ca` | Current Approved Student / Reader | FRONTEND_CHANGELOG.md, TASK_STATE.md, verify_course_library_qa.py | **Keep** |
| 164 | `screenshot/course_library_baseline_desktop.png` | 74 | 1440x900 | `ef85b978` | Current Approved Student / Reader | capture_course_baseline.py | **Keep** |
| 165 | `screenshot/course_library_baseline_mobile.png` | 50 | 390x844 | `04f77508` | Current Approved Student / Reader | capture_course_baseline.py | **Keep** |
| 166 | `screenshot/course_library_materials_modal.png` | 73 | 1440x900 | `74da1d19` | Current Approved Student / Reader | FRONTEND_CHANGELOG.md, TASK_STATE.md, verify_course_library_qa.py | **Keep** |
| 167 | `screenshot/course_library_no_breadcrumbs.png` | 62 | 1440x900 | `665b4abf` | Current Approved Student / Reader | TASK_STATE.md, capture_part7b_qa.py | **Keep** |
| 168 | `screenshot/course_library_reader_opened.png` | 117 | 1440x900 | `0f36d769` | Current Approved Student / Reader | FRONTEND_CHANGELOG.md, TASK_STATE.md, verify_course_library_qa.py | **Keep** |
| 169 | `screenshot/course_library_reader_return.png` | 66 | 1440x900 | `ff7d6f66` | Current Approved Student / Reader | FRONTEND_CHANGELOG.md, TASK_STATE.md, verify_course_library_qa.py | **Keep** |
| 170 | `screenshot/course_library_search_empty.png` | 64 | 1440x900 | `a71ec328` | Current Approved Student / Reader | FRONTEND_CHANGELOG.md, TASK_STATE.md, verify_course_library_qa.py | **Keep** |
| 171 | `screenshot/course_library_search_results.png` | 56 | 1440x900 | `88bc4a9d` | Current Approved Student / Reader | FRONTEND_CHANGELOG.md, TASK_STATE.md, verify_course_library_qa.py | **Keep** |
| 172 | `screenshot/course_library_student_desktop.png` | 66 | 1440x900 | `ff7d6f66` | Current Approved Student / Reader | FRONTEND_CHANGELOG.md, TASK_STATE.md, verify_course_library_qa.py | **Keep** |
| 173 | `screenshot/course_library_student_mobile.png` | 44 | 390x844 | `88fc0aa1` | Current Approved Student / Reader | FRONTEND_CHANGELOG.md, TASK_STATE.md, verify_course_library_qa.py | **Keep** |
| 174 | `screenshot/desktop_assistant_empty_chat.png` | 71 | 1440x900 | `ca97e052` | Current Approved Student / Reader | FRONTEND_CHANGELOG.md, TASK_STATE.md, verify_part6c_qa.py | **Keep** |
| 175 | `screenshot/desktop_assistant_new_chat_cleared.png` | 71 | 1440x900 | `b360e533` | Current Approved Student / Reader | FRONTEND_CHANGELOG.md, TASK_STATE.md, verify_part6c_qa.py | **Keep** |
| 176 | `screenshot/desktop_assistant_return_from_courses.png` | 61 | 1440x900 | `fc17d09e` | Current Approved Student / Reader | FRONTEND_CHANGELOG.md, TASK_STATE.md, verify_part6c_qa.py | **Keep** |
| 177 | `screenshot/desktop_assistant_saved_conversation.png` | 55 | 1440x900 | `d49561bb` | Current Approved Student / Reader | FRONTEND_CHANGELOG.md, TASK_STATE.md, verify_part6c_qa.py | **Keep** |
| 178 | `screenshot/landing_desktop_footer_review.png` | 276 | 1434x2440 | `488163d9` | Referenced QA Asset | FRONTEND_CHANGELOG.md, TASK_STATE.md | **Keep** |
| 179 | `screenshot/landing_desktop_redesign.png` | 276 | 1434x2496 | `c29d82bd` | Referenced QA Asset | FRONTEND_CHANGELOG.md, TASK_STATE.md | **Keep** |
| 180 | `screenshot/landing_mobile_footer_review.png` | 247 | 384x4119 | `d2050134` | Referenced QA Asset | FRONTEND_CHANGELOG.md, TASK_STATE.md | **Keep** |
| 181 | `screenshot/landing_mobile_redesign.png` | 249 | 384x4227 | `279db900` | Referenced QA Asset | FRONTEND_CHANGELOG.md, TASK_STATE.md | **Keep** |
| 182 | `screenshot/mobile_assistant_workspace.png` | 83 | 780x1688 | `e228267c` | Referenced QA Asset | FRONTEND_CHANGELOG.md, TASK_STATE.md, verify_part6c_qa.py | **Keep** |
| 183 | `screenshot/mobile_header_corrected_initials.png` | 57 | 780x1688 | `b721344e` | Referenced QA Asset | TASK_STATE.md, capture_part7b_qa.py | **Keep** |
| 184 | `screenshot/mobile_unified_drawer_history.png` | 67 | 780x1688 | `d9a4497b` | Referenced QA Asset | FRONTEND_CHANGELOG.md, TASK_STATE.md, verify_part6c_qa.py | **Keep** |
| 185 | `screenshot/part7c_baseline_admin_desktop_1440.png` | 119 | 1440x900 | `9ae26c83` | Referenced QA Asset | capture_part7c_baseline.py | **Keep** |
| 186 | `screenshot/part7c_baseline_student_compact_375.png` | 75 | 750x1334 | `1de6795d` | Referenced QA Asset | capture_part7c_baseline.py | **Keep** |
| 187 | `screenshot/part7c_baseline_student_desktop_1440.png` | 107 | 1440x900 | `62cf44d3` | Referenced QA Asset | capture_part7c_baseline.py | **Keep** |
| 188 | `screenshot/part7c_baseline_student_laptop_1366.png` | 103 | 1366x768 | `dccb361d` | Referenced QA Asset | capture_part7c_baseline.py | **Keep** |
| 189 | `screenshot/part7c_baseline_student_mobile_390.png` | 102 | 780x1688 | `f95d884a` | Referenced QA Asset | capture_part7c_baseline.py | **Keep** |
| 190 | `screenshot/ppt_evidence/unsupported_question_all_courses_live.png` | 59 | 1440x900 | `276e5fbb` | Presentation / Report Evidence | PPT_COMPLETION_NOTES.md, RAG_Assistant_Presentation_Speaker_Notes.md, TASK_STATE.md (+3 more) | **Keep** |
| 191 | `screenshot/reader_desktop_fullpage.png` | 141 | 1440x900 | `3cdcad18` | Current Approved Student / Reader | FRONTEND_CHANGELOG.md, TASK_STATE.md, capture_reader_page_qa.py | **Keep** |
| 192 | `screenshot/reader_missing_document.png` | 41 | 1440x900 | `ae3a8e7e` | Current Approved Student / Reader | FRONTEND_CHANGELOG.md, TASK_STATE.md, capture_reader_page_qa.py | **Keep** |
| 193 | `screenshot/reader_mobile.png` | 195 | 780x1688 | `ff06a8b3` | Current Approved Student / Reader | FRONTEND_CHANGELOG.md, TASK_STATE.md, capture_reader_page_qa.py | **Keep** |
| 194 | `screenshot/reader_non_pdf_docx.png` | 76 | 1440x900 | `2e895aef` | Current Approved Student / Reader | FRONTEND_CHANGELOG.md, TASK_STATE.md, build_chapters_4_to_6.py (+1 more) | **Keep** |
| 195 | `screenshot/reader_pdf_evidence_collapsed.png` | 140 | 1440x900 | `525359b8` | Current Approved Student / Reader | FRONTEND_CHANGELOG.md, TASK_STATE.md, capture_reader_page_qa.py | **Keep** |
| 196 | `screenshot/reader_pdf_evidence_expanded.png` | 141 | 1440x900 | `3cdcad18` | Current Approved Student / Reader | FRONTEND_CHANGELOG.md, TASK_STATE.md, capture_reader_page_qa.py | **Keep** |
| 197 | `screenshot/reader_pdf_page2_desktop.png` | 141 | 1440x900 | `3cdcad18` | Presentation / Report Evidence | FRONTEND_CHANGELOG.md, PPT_COMPLETION_NOTES.md, REPORT_FACTS_FOR_PPT.md (+5 more) | **Keep** |
| 198 | `screenshot/reader_pdf_page5_desktop.png` | 136 | 1440x900 | `fa7567bd` | Current Approved Student / Reader | FRONTEND_CHANGELOG.md, TASK_STATE.md, capture_reader_page_qa.py | **Keep** |
| 199 | `screenshot/source_viewer_desktop_reader.png` | 125 | 1440x900 | `853d033f` | Historical Source Viewer Evidence | FRONTEND_CHANGELOG.md, TASK_STATE.md, capture_source_viewer_qa.py | **Keep** |
| 200 | `screenshot/source_viewer_evidence_context.png` | 125 | 1440x900 | `853d033f` | Historical Source Viewer Evidence | FRONTEND_CHANGELOG.md, TASK_STATE.md, capture_source_viewer_qa.py | **Keep** |
| 201 | `screenshot/source_viewer_mobile_reader.png` | 80 | 390x844 | `c4aa54e0` | Historical Source Viewer Evidence | FRONTEND_CHANGELOG.md, TASK_STATE.md, capture_source_viewer_qa.py | **Keep** |
| 202 | `screenshot/source_viewer_new_tab_fallback.png` | 151 | 1440x900 | `08a757b6` | Historical Source Viewer Evidence | FRONTEND_CHANGELOG.md, TASK_STATE.md, capture_source_viewer_qa.py | **Keep** |
| 203 | `screenshot/source_viewer_non_pdf_docx.png` | 77 | 1440x900 | `ac6ac6dd` | Historical Source Viewer Evidence | FRONTEND_CHANGELOG.md, TASK_STATE.md, capture_source_viewer_qa.py | **Keep** |
| 204 | `screenshot/source_viewer_pdf_page2_desktop.png` | 125 | 1440x900 | `853d033f` | Historical Source Viewer Evidence | FRONTEND_CHANGELOG.md, TASK_STATE.md, capture_source_viewer_qa.py | **Keep** |
| 205 | `screenshot/source_viewer_pdf_page5_desktop.png` | 120 | 1440x900 | `b4033b1e` | Historical Source Viewer Evidence | FRONTEND_CHANGELOG.md, TASK_STATE.md, capture_source_viewer_qa.py | **Keep** |
| 206 | `screenshot/source_viewer_unavailable_doc.png` | 40 | 1440x900 | `e3a45bff` | Historical Source Viewer Evidence | FRONTEND_CHANGELOG.md, TASK_STATE.md, capture_source_viewer_qa.py | **Keep** |
| 207 | `screenshot/student_dashboard_baseline_desktop.png` | 103 | 1440x900 | `cc3ae09c` | Referenced QA Asset | FRONTEND_CHANGELOG.md, TASK_STATE.md, capture_dashboard_baseline.py | **Keep** |
| 208 | `screenshot/student_dashboard_baseline_mobile.png` | 127 | 780x1688 | `689c5991` | Referenced QA Asset | FRONTEND_CHANGELOG.md, TASK_STATE.md, capture_dashboard_baseline.py | **Keep** |
| 209 | `screenshot/student_dashboard_final_desktop.png` | 115 | 1440x900 | `dd50d150` | Referenced QA Asset | FRONTEND_CHANGELOG.md, TASK_STATE.md, capture_dashboard_final.py | **Keep** |
| 210 | `screenshot/student_dashboard_final_laptop.png` | 113 | 1366x768 | `2abaf5f7` | Referenced QA Asset | FRONTEND_CHANGELOG.md, TASK_STATE.md, capture_dashboard_final.py | **Keep** |
| 211 | `screenshot/student_dashboard_final_mobile.png` | 126 | 780x1688 | `d3b99c1b` | Referenced QA Asset | FRONTEND_CHANGELOG.md, TASK_STATE.md, capture_dashboard_final.py | **Keep** |
| 212 | `screenshot/student_dashboard_recent_conversations.png` | 115 | 1440x900 | `bd792056` | Referenced QA Asset | FRONTEND_CHANGELOG.md, TASK_STATE.md, capture_dashboard_final.py | **Keep** |
| 213 | `screenshot/student_dashboard_redirect.png` | 70 | 1440x900 | `e99a6565` | Referenced QA Asset | FRONTEND_CHANGELOG.md, verify_part6b_qa.py | **Keep** |
| 214 | `screenshot/student_dashboard_redirect_part8a.png` | 67 | 1440x900 | `ee037952` | Referenced QA Asset | FRONTEND_CHANGELOG.md, TASK_STATE.md, capture_admin_part8a.py | **Keep** |
| 215 | `screenshot/student_home_chat_desktop.png` | 70 | 1440x900 | `ffae3e9d` | Current Approved Student / Reader | FRONTEND_CHANGELOG.md, verify_part6b_qa.py | **Keep** |
| 216 | `screenshot/student_home_chat_mobile.png` | 88 | 780x1688 | `63ec0401` | Current Approved Student / Reader | FRONTEND_CHANGELOG.md, verify_part6b_qa.py | **Keep** |
| 217 | `screenshot/student_profile_after_new_chat.png` | 67 | 1440x900 | `cf258ecf` | Current Approved Student / Reader | TASK_STATE.md, capture_part7b_qa.py | **Keep** |
| 218 | `screenshot/student_profile_baseline_desktop.png` | 111 | 1440x900 | `648f52e9` | Current Approved Student / Reader | FRONTEND_CHANGELOG.md, TASK_STATE.md, capture_profile_baseline.py | **Keep** |
| 219 | `screenshot/student_profile_baseline_mobile.png` | 95 | 780x1688 | `0c93a0d6` | Current Approved Student / Reader | FRONTEND_CHANGELOG.md, TASK_STATE.md, capture_profile_baseline.py | **Keep** |
| 220 | `screenshot/student_profile_compact_mobile.png` | 88 | 750x1334 | `655400c7` | Current Approved Student / Reader | FRONTEND_CHANGELOG.md, TASK_STATE.md, capture_profile_final.py | **Keep** |
| 221 | `screenshot/student_profile_course_error.png` | 85 | 1440x900 | `27aa78c9` | Current Approved Student / Reader | FRONTEND_CHANGELOG.md, TASK_STATE.md, capture_profile_final.py | **Keep** |
| 222 | `screenshot/student_profile_courses.png` | 86 | 1440x900 | `7a842f47` | Current Approved Student / Reader | FRONTEND_CHANGELOG.md, TASK_STATE.md, capture_profile_final.py | **Keep** |
| 223 | `screenshot/student_profile_desktop.png` | 86 | 1440x900 | `7a842f47` | Current Approved Student / Reader | FRONTEND_CHANGELOG.md, TASK_STATE.md, capture_part7b_qa.py (+1 more) | **Keep** |
| 224 | `screenshot/student_profile_empty_courses.png` | 85 | 1440x900 | `16aaf41a` | Current Approved Student / Reader | FRONTEND_CHANGELOG.md, TASK_STATE.md, capture_profile_final.py | **Keep** |
| 225 | `screenshot/student_profile_laptop.png` | 82 | 1366x768 | `997960e3` | Current Approved Student / Reader | FRONTEND_CHANGELOG.md, TASK_STATE.md, capture_profile_final.py | **Keep** |
| 226 | `screenshot/student_profile_mobile.png` | 120 | 780x1688 | `d66eb3e8` | Current Approved Student / Reader | FRONTEND_CHANGELOG.md, TASK_STATE.md, capture_part7b_qa.py (+1 more) | **Keep** |

## Summary of Classification

- **Keep (Approved / Active / Baseline Evidence):** 220 files
- **Archived (Historical Part 8A Baselines):** 6 files
- **Deleted (Confirmed Obsolete / Duplicates from Prior Cleanups):** 0 files
- **Unresolved:** 0 files
- **Total Active & Archived Files in `screenshot/`:** 226 files
