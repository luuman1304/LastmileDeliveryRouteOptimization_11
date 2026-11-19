# Bảng liên kết phát biểu và bằng chứng

| Phát biểu | Artifact nguồn |
|---|---|
| Dataset ETA không giao split và không lọc cohort bằng nhãn tương lai | `artifacts/generated/eta_dataset_v3/validation.json` |
| LightGBM được chọn trên validation; MAE test 118,70 phút | `artifacts/generated/eta_baselines_v3/summary.json`, `model_selection.json` |
| Query-MAE giảm 18,11 phút; CI cụm courier không chứa 0 | `artifacts/generated/statistics_v3/eta_paired_inference.json` |
| AOI chưa thấy chiếm 3,84% test và kết quả theo dải ETA | `artifacts/generated/slice_analysis_v3/summary.json`, `eta_slices.csv` |
| HR@3 và KRC của các mô hình xếp thứ tự | `artifacts/generated/eta_integration_v3/summary.json` |
| Đặc trưng quan hệ làm query-MAE validation tăng 11,63 phút | `artifacts/generated/graph_ablation_v3/summary.json` |
| OR-Tools time-window có nghiệm cho 119/204 tuyến | `artifacts/generated/amazon_baselines_v2/summary.json` |
| Soft-window solver có nghiệm 204/204 và đánh giá giữ lại 187 tuyến | `artifacts/generated/amazon_soft_windows_v3/summary.json` |
| Suy luận theo station và ba lần chạy trên toàn bộ 204 tuyến | `artifacts/generated/amazon_soft_windows_v3/summary.json` |
| Checksum và kiểm toán raw data | `artifacts/generated/data_audit_v3.json` |
| Chênh MAE train, validation, test và macro theo thành phố | `artifacts/generated/robustness_v3/summary.json` |
| So sánh inverse-city weighting trên validation | `artifacts/generated/balanced_v3/summary.json` |
| Rolling-origin tháng 7, 8 và 9 | `artifacts/generated/rolling_origin_v3/summary.json` |
| Latency, model size, RSS, PSI và fallback | `artifacts/generated/deployment_v3/summary.json` |
| Phiên bản môi trường và checksum artifact | `artifacts/generated/MANIFEST.json` |

Mọi số làm tròn trong báo cáo phải truy được về các tệp trên. Không dùng kết quả
ETA `v1` hoặc `v2` vì các phiên bản đó còn lọc cohort theo nhãn `ETA <= 120`.
Baseline Amazon v2 được giữ nguyên vì logic và dữ liệu đầu vào không thay đổi;
deadline mềm và phân tích ổn định phải dùng v3.
