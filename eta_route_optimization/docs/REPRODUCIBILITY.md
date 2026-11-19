# Hướng dẫn tái lập phiên bản 3

Chạy từ thư mục chứa `eta_route_optimization`. Môi trường đã kiểm tra dùng Python
3.13 và dependency khai báo trong `pyproject.toml`:

```bash
python3 -m venv .venv-eta
UV_CACHE_DIR=/tmp/bcck-uv-cache uv pip install --python .venv-eta/bin/python -e 'eta_route_optimization[dev]'
PYTHON_BIN=.venv-eta/bin/python eta_route_optimization/scripts/reproduce_v3.sh
```

Script thực hiện theo thứ tự: audit dữ liệu; tạo và xác nhận dataset v3; baseline
ETA; suy luận thống kê; xếp hạng; lát cắt; cổng quan hệ; robustness; cân bằng
thành phố; rolling-origin; deadline mềm Amazon; benchmark; test; và manifest.
Biến `LOKY_MAX_CPU_COUNT` được đặt mặc định là 8 để tránh phụ thuộc việc hệ điều
hành có cho phép truy vấn số lõi vật lý hay không.

Các điều kiện phát hành chính:

- `eta_dataset_v3/validation.json` phải `pass` và xác nhận không lọc cohort bằng
  nhãn tương lai.
- Chọn mô hình, city weighting và cổng quan hệ chỉ dùng validation.
- Mọi `best_iteration` phải nhỏ hơn trần tương ứng: 10.000 cho thí nghiệm chính
  và city-balanced, 15.000 cho rolling-origin.
- Bộ giải deadline mềm chạy ba lần trên cả 204 tuyến; calibration tách khỏi 187
  tuyến evaluation.
- Unit test, compile, lint, JSON/YAML và checksum được kiểm tra trước khi chốt
  kết quả.

`MANIFEST.json` phải được tạo sau cùng; nếu source hoặc artifact thay đổi thì
manifest cũ không còn hợp lệ và phải tạo lại.
