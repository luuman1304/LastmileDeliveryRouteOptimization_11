# Quyết định sử dụng GNN

**Quyết định:** không triển khai GNN trong giao thức phiên bản 2.

Quyết định dựa trên ablation năm seed, không dựa trên độ phức tạp hoặc sở thích
mô hình. Thống kê quan hệ chỉ được tính từ train. Trên validation, chúng làm
query-MAE tăng 11,63 phút, với khoảng tin cậy 95% [9,93; 13,41]. Vì CI nằm hoàn
toàn trên 0, cổng validation bác bỏ nhánh quan hệ trước khi xem kết quả test.
Test chỉ xác nhận cùng chiều (tăng 12,69 phút); số test không tham gia quyết
định. Tỷ lệ cạnh test từng xuất hiện trong train là 64,78%, nên mô hình phụ thuộc
mạnh vào ID cạnh còn gặp rủi ro khái quát hóa.

Graph2Route và M²G4RTP vẫn là cơ sở khoa học phù hợp cho nhánh đồ thị. Tuy nhiên,
các công trình đó không chứng minh GNN sẽ tốt hơn trên mọi cách đặt query và mọi
split. Chỉ mở lại nhánh GNN khi có biểu diễn node quy nạp, dữ liệu cạnh bổ sung
hoặc một validation experiment cho thấy lợi ích ổn định trước khi xem test.
