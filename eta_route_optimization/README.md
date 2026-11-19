# ETA and last-mile route optimization

Đây là source độc lập cho hướng nghiên cứu dự đoán thời gian hoàn tất giao hàng
và tối ưu thứ tự phục vụ các điểm giao. Dự án không nhập source của nghiên cứu
station-held-out trước đây. Chỉ những hàm dùng lại sau khi được kiểm tra hợp đồng
dữ liệu và rò rỉ mới được sao chép vào đây, kèm nguồn trong nhật ký quyết định.

## Phạm vi đã chốt

- LaDe-D là dữ liệu chính cho dự đoán ETA và dự đoán thứ tự các nhiệm vụ còn lại.
- Amazon là dữ liệu chính cho đánh giá tối ưu tuyến tĩnh bằng ma trận thời gian.
- Không tuyên bố có dữ liệu giao thông thời gian thực.
- Không gọi kích thước kiện Amazon là trọng lượng. Chỉ sử dụng thể tích tính từ
  ba kích thước và dung tích xe.
- Không tuyên bố tuyến thay thế trên LaDe-D tiết kiệm thời gian thực tế vì dữ liệu
  chỉ ghi nhận kết quả của tuyến đã thực hiện, không có thời gian phản thực cho
  tuyến chưa chạy.
- GNN không được triển khai trong phiên bản hiện tại vì ablation quan hệ không
  vượt cổng validation.

## Tài liệu điều khiển nghiên cứu

- [Mô tả và giao thức nghiên cứu](docs/RESEARCH_PROTOCOL.md)
- [Đánh giá tính khả thi của dữ liệu](docs/DATA_FEASIBILITY.md)
- [Cơ sở tài liệu và nhật ký quyết định](docs/LITERATURE_AND_DECISIONS.md)
- [Đánh giá phần source cũ có thể sử dụng lại](docs/REUSE_ASSESSMENT.md)
- [Danh sách công việc và tiêu chí hoàn thành](TASKS.md)
- [Tài liệu tham khảo có thể kiểm tra](references.bib)
- [Kết quả và kết luận](docs/FINAL_RESULTS.md)
- [Data card](docs/DATA_CARD.md)
- [Model card](docs/MODEL_CARD.md)
- [Quyết định GNN](docs/GNN_DECISION.md)
- [Đánh giá overfitting và mất cân bằng](docs/ROBUSTNESS_ASSESSMENT.md)
- [Bảng claim-evidence](docs/CLAIM_EVIDENCE.md)
- [Hướng dẫn tái lập](docs/REPRODUCIBILITY.md)

## Cấu trúc

```text
eta_route_optimization/
├── configs/
├── docs/
├── src/eta_route_optimization/
├── tests/
├── artifacts/
├── TASKS.md
├── pyproject.toml
└── references.bib
```

## Trạng thái

Dự án dùng giao thức phiên bản 2 và artifact ETA hậu tố `v3`. Cohort giữ mọi ETA
dương quan sát được, không lọc bằng nhãn tương lai; mô hình được chọn trên
validation và test chỉ dùng để xác nhận. Quy trình gồm baseline ETA, suy luận
theo cụm courier, lát cắt đuôi dài, xếp hạng, rolling-origin, city weighting,
ablation quan hệ, deadline mềm Amazon chạy lặp, benchmark và manifest. Baseline
Amazon v2 được tái sử dụng vì phần đó không đổi; ETA v1/v2 và soft-window v2
không được dùng cho kết luận cuối. Lệnh tái lập chuẩn là
`scripts/reproduce_v3.sh`.

## Phạm vi bản phát hành GitHub

Repository công khai lưu source, cấu hình, test, tài liệu và các artifact tổng
hợp dùng trực tiếp cho kết luận. Dữ liệu thô,
virtualenv, cache, dataset/prediction cấp dòng và model nhị phân có thể tái tạo
không được commit nhằm tránh nhân bản dữ liệu và làm repository quá lớn. Hai
script ở thư mục `../scripts/` tải dữ liệu công khai về đúng cấu trúc
`data/raw/`; `scripts/reproduce_v3.sh` tái tạo đầy đủ artifact cấp dòng tại máy
người dùng. Baseline Amazon mang hậu tố `v2` được giữ vì đây là baseline hiện
hành không thay đổi; các artifact ETA và soft-window v2 cũ không thuộc bản phát
hành.
