# Dữ liệu

Dữ liệu thô không được commit vào repository.

Để tải dữ liệu, chạy các lệnh sau tại thư mục gốc:

```bash
./scripts/download_lade_d.sh
./scripts/download_amazon.sh
```

- LaDe-D: tải từ `Cainiao-AI/LaDe-D` trên Hugging Face. Revision sử dụng được
  ghi trong `download_lade_d.sh`.
- Amazon Last Mile Routing Research Challenge: tải từ bucket công khai
  `s3://amazon-last-mile-challenges/almrrc2021/`.

Dữ liệu sau khi tải nằm tại `data/raw/lade_d/` và `data/raw/amazon/`.
