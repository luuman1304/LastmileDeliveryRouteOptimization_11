# Last-mile ETA and Route Optimization

Repository này chứa bản nghiên cứu hiện hành về dự đoán thời gian hoàn tất đơn
giao hàng (ETA) và hỗ trợ sắp xếp thứ tự giao hàng chặng cuối. Phiên bản công
bố dùng giao thức v2 và artifact ETA hậu tố `v3`; các thử nghiệm ETA v1/v2 và
soft-window v2 cũ không thuộc release.

## Nội dung chính

- `eta_route_optimization/`: source, cấu hình, test, tài liệu và artifact tổng
  hợp dùng trực tiếp trong báo cáo.
- `scripts/`: script tải LaDe-D và Amazon từ nguồn công khai.
- `data/raw/`: vị trí dữ liệu đầu vào; dữ liệu thô không được commit.

Thư mục `paper/` và các bản DOCX/PDF kết xuất không thuộc repository. Generator
và template sạch vẫn được lưu để tái tạo báo cáo cục bộ. Baseline
`amazon_baselines_v2` được giữ vì đây là baseline hiện hành không thay đổi và
được tài liệu nghiên cứu dẫn chiếu.

## Kết quả đã khóa

- LightGBM được chọn trên validation, không dùng test để chọn mô hình.
- MAE test của LightGBM: 118,70 phút; historical median: 134,25 phút.
- Bootstrap cụm courier cho hiệu ứng LightGBM trừ historical median có khoảng
  tin cậy 95% hoàn toàn âm.
- Nhánh quan hệ không vượt cổng validation, do đó không triển khai GNN.
- Deadline mềm giải được 204/204 tuyến Amazon trong giao thức hiện hành.

Chi tiết và giới hạn diễn giải nằm trong
[`eta_route_optimization/docs/FINAL_RESULTS.md`](eta_route_optimization/docs/FINAL_RESULTS.md),
data card, model card và bảng claim-evidence.

## Tái lập

```bash
python3 -m venv .venv-eta
UV_CACHE_DIR=/tmp/bcck-uv-cache uv pip install --python .venv-eta/bin/python -e 'eta_route_optimization[dev]'
./scripts/download_lade_d.sh
./scripts/download_amazon.sh
PYTHON_BIN=.venv-eta/bin/python eta_route_optimization/scripts/reproduce_v3.sh
```

Script tái lập sinh lại dataset/prediction cấp dòng và model nhị phân. Những
file lớn có thể tái tạo này không được commit; repository chỉ giữ artifact tổng
hợp cần thiết để kiểm tra các con số trong báo cáo.

## Kiểm tra release

```bash
.venv-eta/bin/python -m pytest -q eta_route_optimization/tests
.venv-eta/bin/python -m ruff check eta_route_optimization
.venv-eta/bin/python -m compileall -q eta_route_optimization/src eta_route_optimization/scripts
```

`RELEASE_MANIFEST.json` ghi kích thước và SHA-256 của mọi file thuộc commit,
ngoại trừ chính manifest và metadata `.git`.
