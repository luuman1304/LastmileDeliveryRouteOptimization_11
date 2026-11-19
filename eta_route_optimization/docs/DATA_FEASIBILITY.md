# Đánh giá tính khả thi của dữ liệu

Các số dưới đây được tính trực tiếp từ tệp cục bộ ngày 16-11-2026. Chúng là kết
quả kiểm toán dữ liệu, không phải kết quả mô hình.

## 1. Amazon Last Mile Routing Research Challenge

### Kết quả kiểm toán phần training

- 6.112 route, 17 station.
- 904.527 stop có package và 1.457.175 package.
- Trung vị 151 stop mỗi route.
- Có observed sequence, tọa độ, zone, ma trận transit time giữa các stop, planned
  service time, kích thước package và executor capacity theo cm3.
- 113.993 trên 1.457.175 package có đủ hai đầu time window, tương ứng 7,82%.
- Trung vị tỷ lệ tổng thể tích package trên executor capacity là 0,737.
- Có 12 route có tỷ lệ thể tích tính toán lớn hơn 1; phải được đánh dấu kiểm tra,
  không tự động xóa hay sửa.

### Khả năng sử dụng

Amazon phù hợp cho tối ưu thứ tự tĩnh và đánh giá chi phí của tuyến thay thế vì
có ma trận transit time đầy đủ. Dữ liệu không có thời điểm đến thực tế tại từng
stop, nên không tạo được nhãn ETA quan sát cho từng stop. Transit time được bài
báo dữ liệu mô tả là trung bình lịch sử giữa các vị trí giao hàng, không phải tín
hiệu giao thông thời gian thực.

Kích thước package cho phép tính thể tích, không cho phép suy ra trọng lượng.
Trong bài toán một xe với tập đơn đã được gán sẵn, capacity chủ yếu kiểm tra tải
ban đầu; nó không tự tạo ra ràng buộc thứ tự mới vì tải giảm sau mỗi lần giao.

## 2. LaDe-D

### Kết quả kiểm toán năm tệp thành phố

| Thành phố | Số đơn | Shipper | Region | AOI | Shipper-ngày |
|---|---:|---:|---:|---:|---:|
| Chongqing | 931.351 | 1.494 | 48 | 17.451 | 68.521 |
| Hangzhou | 1.861.600 | 1.392 | 51 | 17.714 | 71.670 |
| Jilin | 31.415 | 57 | 4 | 1.259 | 1.930 |
| Shanghai | 1.483.864 | 1.733 | 52 | 15.564 | 70.253 |
| Yantai | 206.431 | 205 | 17 | 8.163 | 17.941 |
| **Tổng** | **4.514.661** | **4.881 theo từng tệp** |  |  | **230.315** |

- Không có order ID trùng trong từng tệp.
- Jilin thiếu 955 cặp tọa độ GPS lúc nhận; Yantai thiếu 2.422 cặp.
- Có 3 bản ghi Chongqing có thời gian hoàn tất sớm hơn thời gian nhận và cần loại
  hoặc sửa theo một quy tắc được đóng băng trước huấn luyện.
- Trung vị thời gian từ nhận đến hoàn tất trên các bản ghi trong phạm vi bảy ngày
  là 105 phút.
- Trung vị khoảng thời gian dương giữa hai lần hoàn tất liên tiếp của cùng
  shipper-ngày là 10 phút. Đại lượng này gồm di chuyển, phục vụ và chờ, không phải
  thời gian chạy xe thuần túy.
- Quy mô thành phố mất cân bằng mạnh: số đơn Hangzhou lớn khoảng 59 lần Jilin.

### Khả năng sử dụng

LaDe-D phù hợp cho ETA vì có accept time, delivery time, vị trí, courier, region
và AOI. Nhãn được xây dựng theo định nghĩa của bài báo LaDe: thời gian từ thời
điểm truy vấn đến thời điểm hoàn tất thực tế của nhiệm vụ chưa hoàn thành.

LaDe-D không có trọng lượng, kích thước package, vehicle capacity hoặc trạng thái
giao thông. Số nhiệm vụ chưa hoàn thành chỉ được gọi là tải công việc. Dữ liệu có
thể hỗ trợ route prediction; việc đánh giá route optimization theo thời gian thực
tế bị giới hạn vì không có kết quả phản thực của tuyến không được thực hiện.

## 3. Quyết định sử dụng

| Yêu cầu | LaDe-D | Amazon | Quyết định |
|---|---|---|---|
| ETA quan sát | Có | Không | Huấn luyện ETA trên LaDe-D |
| Thứ tự thực tế | Có thể suy từ delivery time | Có observed sequence | Dùng cả hai theo giao thức riêng |
| Chi phí mọi cạnh | Không đầy đủ | Có | Đánh giá tối ưu tĩnh chính trên Amazon |
| Trọng lượng | Không | Không | Không đưa ra tuyên bố về trọng lượng |
| Thể tích/dung tích xe | Không | Có | Chỉ báo cáo trên Amazon |
| Giao thông thời gian thực | Không | Không | Không đưa ra tuyên bố về giao thông thực |

## 4. Rủi ro bắt buộc xử lý

1. Rò rỉ từ việc xây AOI graph hoặc thống kê tốc độ bằng cả tập kiểm định.
2. Random split theo từng đơn làm cùng shipper-ngày xuất hiện ở cả train và test.
3. Thành phố lớn chi phối metric tổng hợp.
4. Gọi accept-to-delivery time là thời gian di chuyển thuần túy.
5. Đánh giá tuyến LaDe-D bằng chính mô hình chi phí đã dùng để tạo tuyến rồi xem
   đó là bằng chứng tiết kiệm thời gian thực tế.
6. Dùng tập evaluation Amazon trong quá trình chọn mô hình.
