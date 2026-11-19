# Cơ sở tài liệu và nhật ký quyết định

Tài liệu này ghi rõ mỗi quyết định đến từ đâu. “Đã chốt” nghĩa là quyết định giao
thức, không có nghĩa phương pháp đã cho kết quả tốt.

## 1. Nguồn được chọn

### LaDe

Wu và cộng sự công bố LaDe tại KDD 2024, DOI
`10.1145/3637528.3671548`. Công trình được chọn vì đây là bài báo giới thiệu đúng
bộ dữ liệu đang sử dụng, định nghĩa route prediction và ETA, công bố baseline,
metric và mã tham chiếu. Bài báo xác định ETA là thời gian từ thời điểm truy vấn
đến thời điểm hoàn tất thực tế của nhiệm vụ chưa hoàn thành.

### Amazon

Merchán và cộng sự công bố bộ Amazon tại Transportation Science, DOI
`10.1287/trsc.2022.1173`. Công trình được chọn vì đây là mô tả chính thức của dữ
liệu, bao gồm 6.112 route training, transit time lịch sử, observed sequence,
planned service time, package dimensions và executor capacity.

### LightGBM

Ke và cộng sự giới thiệu LightGBM tại NeurIPS 2017. Mô hình được chọn làm baseline
bảng vì có khả năng mở rộng, xử lý quan hệ phi tuyến và đã được chính bài báo LaDe
dùng trong cả route prediction và ETA. Việc chọn làm baseline không đồng nghĩa
LightGBM sẽ là mô hình tốt nhất trên giao thức mới.

### OR-Tools

Tài liệu chính thức của Google mô tả Routing Solver cho TSP, VRP, capacity và time
windows. OR-Tools được chọn vì có thể sử dụng trực tiếp ma trận thời gian Amazon
và áp dụng cùng một bộ kiểm tra ràng buộc. Tài liệu cũng nêu rõ bài toán lớn có
thể chỉ nhận được nghiệm tốt trong giới hạn thời gian, vì vậy báo cáo phải dùng
“nghiệm tốt nhất tìm được”, không mặc định gọi là tối ưu toàn cục.

### Graph2Route và M2G4RTP

Graph2Route, DOI `10.1145/3534678.3539084`, mô hình hóa các nhiệm vụ chưa hoàn tất
thành đồ thị không gian-thời gian cho route prediction. M²G4RTP, DOI
`10.1109/ICDE55515.2023.00253`, nghiên cứu dự đoán chung tuyến và thời gian bằng
mô hình đồ thị đa mức, đa nhiệm. Hai công trình là cơ sở khoa học để tạo nhánh
GNN, nhưng không phải bằng chứng rằng GNN cần thiết cho mọi dữ liệu hoặc giao thức.

## 2. Bảng quyết định

| ID | Quyết định | Cơ sở | Trạng thái |
|---|---|---|---|
| D01 | LaDe-D là dữ liệu ETA chính | LaDe định nghĩa và benchmark ETA; schema có accept/delivery event | Đã chốt |
| D02 | Amazon là dữ liệu tối ưu tĩnh chính | Bài Amazon xác nhận ma trận transit time đầy đủ và observed sequence | Đã chốt |
| D03 | Không dùng cụm “giao thông thời gian thực” | Không schema nào có trạng thái giao thông trực tiếp | Đã chốt |
| D04 | Không dùng “trọng lượng hàng” | Amazon chỉ có kích thước; LaDe-D không có kích thước hoặc trọng lượng | Đã chốt |
| D05 | MAE và RMSE là metric ETA chính | LaDe sử dụng MAE, RMSE và ACC@20; MAE diễn giải trực tiếp theo phút | Đã chốt |
| D06 | KRC, HR@3, LSD, ED là metric thứ tự | Giao thức route prediction của LaDe/Graph2Route | Đã chốt |
| D07 | LightGBM là baseline bắt buộc | Bài gốc LightGBM và benchmark LaDe | Đã chốt |
| D08 | OR-Tools là baseline bắt buộc | Benchmark LaDe và tài liệu Routing Solver chính thức | Đã chốt |
| D09 | GNN chỉ triển khai sau baseline | Graph2Route/M²G4RTP cho thấy tiềm năng, chưa chứng minh lợi ích trên split mới | Đã chốt |
| D10 | Phép chia chính LaDe theo thời gian | Mô phỏng dự đoán tương lai và ngăn dùng sự kiện tương lai | Giả thuyết giao thức, phải kiểm tra độ đủ mẫu |
| D11 | Đánh giá phụ held-out courier/city | LaDe ghi nhận khác biệt lớn giữa thành phố | Đã chốt |
| D12 | Không tuyên bố thời gian thực tiết kiệm trên tuyến LaDe thay thế | Thiếu phản thực cho tuyến không được chạy | Đã chốt |
| D13 | Không triển khai GNN ở phiên bản 1 | Ablation quan hệ làm MAE tăng 2,74 phút, CI 95% [2,58; 2,89] | Đã chốt sau thực nghiệm |
| D14 | Không xem OR-Tools transit-only là phương án vận hành tốt hơn | Transit giảm nhưng trễ trung bình tăng mạnh | Đã chốt sau thực nghiệm |

## 3. Điều kiện chọn GNN

GNN chỉ được đưa vào kết quả chính khi đáp ứng đồng thời:

1. LightGBM, MLP không đồ thị và baseline tối ưu đã chạy đúng cùng split.
2. Graph được xây hoàn toàn từ training fold.
3. Node không phụ thuộc duy nhất vào AOI ID để còn áp dụng được cho AOI mới.
4. Có ít nhất năm seed và khoảng tin cậy cho chênh lệch metric chính.
5. Báo cáo thêm số tham số, thời gian huấn luyện và thời gian suy luận.
6. Kết luận dựa trên chênh lệch và khoảng tin cậy, không đặt trước ngưỡng tăng tùy
   ý sau khi xem test.

## 4. Quy tắc thêm tài liệu tham khảo

- Ưu tiên bài báo gốc, trang nhà xuất bản, DOI, repository của tác giả hoặc tài
  liệu chính thức của phần mềm.
- Không dùng bài tổng hợp không rõ tác giả để chứng minh kết quả định lượng.
- Không chép số liệu từ một nghiên cứu sang bài hiện tại như kết quả của nhóm.
- Mọi số liệu thực nghiệm của nhóm phải có artifact, cấu hình, seed và lệnh tái lập.
- Nếu chưa truy cập được toàn văn hoặc chưa xác minh metadata, tài liệu chỉ được
  ghi vào danh sách chờ, không dùng để hỗ trợ kết luận.
