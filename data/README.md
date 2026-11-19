# Dữ liệu

Dữ liệu thô không được lưu trong GitHub. Chạy từ thư mục gốc repository:

```bash
./scripts/download_lade_d.sh
./scripts/download_amazon.sh
```

- LaDe-D được cố định tại revision ghi trong `download_lade_d.sh` và tải từ
  `Cainiao-AI/LaDe-D` trên Hugging Face.
- Amazon Last Mile Routing Research Challenge được tải từ bucket công khai
  `s3://amazon-last-mile-challenges/almrrc2021/` bằng AWS CLI không cần tài khoản.

Các script đặt dữ liệu vào `data/raw/lade_d/` và `data/raw/amazon/`, đúng đường
dẫn mà pipeline tái lập sử dụng.
