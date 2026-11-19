# Giao thức nghiên cứu phiên bản 2.0

Ngày đóng băng sửa đổi: 18-11-2026.

## 1. Tên đề tài làm việc

**Dự đoán thời gian hoàn tất và tối ưu thứ tự giao hàng chặng cuối dựa trên dữ
liệu lịch sử, đặc điểm khu vực và tải công việc**

Tên này phản ánh đúng các biến đang có. Cụm “điều kiện giao thông” và “khối lượng
hàng” chưa được dùng trong tên vì hai bộ dữ liệu không có tốc độ giao thông thời
gian thực và không có trọng lượng kiện hàng.

## 2. Bài toán nghiên cứu

Nghiên cứu gồm hai mô-đun có liên hệ nhưng được đánh giá riêng.

1. Mô-đun ETA nhận trạng thái của shipper tại thời điểm truy vấn và các đơn chưa
   hoàn tất, sau đó dự đoán số phút còn lại đến khi từng đơn được giao.
2. Mô-đun định tuyến nhận một tập điểm dừng và chi phí đi giữa các điểm, sau đó
   tìm thứ tự phục vụ có chi phí thấp và thỏa các ràng buộc có thể quan sát.

Phần tích hợp đưa chi phí thời gian dự đoán vào bộ tối ưu. Trên LaDe-D, kết quả
tích hợp chỉ được đánh giá về sai số ETA, tính hợp lệ, độ giống thứ tự thực tế và
chi phí mô hình. Không diễn giải chi phí mô hình thành thời gian thực tế tiết
kiệm được. Trên Amazon, ma trận thời gian đầy đủ cho phép so sánh chi phí của các
thứ tự thay thế trong cùng một hệ chi phí, nhưng đây vẫn là thời gian lịch sử ước
tính do bộ dữ liệu cung cấp, không phải quan sát giao thông thời gian thực.

## 3. Mục tiêu

### Mục tiêu tổng quát

Xây dựng và đánh giá một quy trình có thể tái lập để dự đoán ETA và hỗ trợ sắp
xếp thứ tự giao hàng, đồng thời xác định liệu biểu diễn đồ thị có tạo ra lợi ích
ổn định ngoài các baseline bảng và tối ưu truyền thống hay không.

### Mục tiêu cụ thể

1. Tái lập các baseline ETA được bài báo LaDe sử dụng trên cùng giao thức dữ liệu.
2. Xây dựng baseline định tuyến bằng khoảng cách, thời gian lịch sử và OR-Tools.
3. Đo mức thay đổi của ETA và chất lượng thứ tự khi kiểm định theo thời gian,
   shipper chưa thấy và thành phố chưa thấy.
4. Tích hợp chi phí ETA với bộ tối ưu mà không sử dụng thông tin tương lai.
5. Chỉ đánh giá GNN sau khi baseline được đóng băng, kèm ablation và chi phí tính
   toán.

## 4. Câu hỏi nghiên cứu

**RQ1.** Mô hình học máy cải thiện độ chính xác ETA bao nhiêu so với trung vị
lịch sử, tốc độ lịch sử và KNN khi dự đoán trên thời gian tương lai?

**RQ2.** Việc sử dụng chi phí thời gian dự đoán có tạo ra thứ tự giao hàng tốt
hơn các baseline khoảng cách, thời gian lịch sử và OR-Tools theo các thước đo đã
định trước hay không?

**RQ3.** Mức cải thiện còn duy trì khi áp dụng cho shipper hoặc thành phố không
tham gia huấn luyện hay không?

**RQ4.** Mô hình đồ thị có cải thiện ổn định so với LightGBM và mô hình không đồ
thị sau khi tính đến độ bất định, thời gian huấn luyện và thời gian suy luận hay
không?

## 5. Vai trò của dữ liệu

### LaDe-D

- Dữ liệu chính cho ETA vì có sự kiện nhận và hoàn tất đơn.
- Đơn vị nhóm là tổ hợp thành phố, shipper và ngày.
- Nhãn ETA tại thời điểm truy vấn là số phút đến thời điểm hoàn tất thực tế.
- Thời điểm truy vấn phiên bản 1 là lần hoàn tất giao hàng đầu tiên của mỗi
  shipper-ngày. Toàn bộ nhiệm vụ thỏa `accept_time <= query_time < delivery_time`
  được dùng để tạo trạng thái tải công việc tại thời điểm truy vấn.
- Số nhiệm vụ chờ, thứ tự nhận và giới hạn tối đa 25 nhiệm vụ được xác định chỉ
  từ trạng thái quan sát tại query. Mọi nhãn ETA dương đều được giữ. Không lọc
  theo ngưỡng ETA tương lai; các dải thời gian chỉ dùng để báo cáo lát cắt.
- Số nhiệm vụ đang chờ được gọi là tải công việc, không gọi là trọng lượng hàng.

### Amazon

- Dữ liệu chính cho tối ưu thứ tự tĩnh.
- Ma trận transit time là chi phí cạnh.
- Thời gian phục vụ dự kiến được cộng vào chi phí tuyến và báo cáo riêng.
- Thể tích kiện được tính từ ba kích thước. Dung tích xe dùng để kiểm tra tính
  hợp lệ, không được diễn giải là trọng lượng.
- Tập evaluation chính thức không được dùng để chọn mô hình hoặc siêu tham số.

## 6. Baseline và lý do lựa chọn

### ETA

- **Historical median và SPEED:** baseline tối thiểu, giúp xác định lợi ích thực
  của học máy so với quy tắc lịch sử. Bài báo LaDe dùng SPEED trong đánh giá ETA.
- **KNN:** baseline phi tham số xuất hiện trong đánh giá LaDe.
- **LightGBM:** baseline chính cho dữ liệu bảng. LaDe báo cáo LightGBM trên cả ETA
  và route prediction; công trình gốc LightGBM thiết kế thuật toán cho hiệu quả
  và khả năng mở rộng trên dữ liệu có nhiều đặc trưng.
- **MLP:** baseline học sâu không sử dụng đồ thị, chỉ triển khai sau khi LightGBM
  ổn định để tách lợi ích của học sâu khỏi lợi ích của cấu trúc đồ thị.

### Định tuyến

- **Observed sequence:** mốc hành vi, không được gọi là tối ưu toán học.
- **Nearest Neighbor:** mốc tham lam dễ tái lập.
- **Nearest Neighbor + 2-opt:** kiểm tra lợi ích của tìm kiếm cục bộ.
- **OR-Tools:** baseline tối ưu có ràng buộc. Tài liệu OR-Tools hỗ trợ TSP, VRP,
  capacity và time windows, đồng thời lưu ý nghiệm trả về có thể chỉ là nghiệm
  tốt trong giới hạn thời gian, không nhất thiết tối ưu toàn cục.
- **OR-Tools deadline mềm:** thời điểm bắt đầu của stop là ràng buộc cứng, còn
  deadline chịu penalty. Penalty được chọn trên một tuyến calibration mỗi station;
  các tuyến còn lại không tham gia chọn hệ số. Nếu solver thất bại, fallback là
  nearest-neighbor kết hợp directed 2-opt.

### GNN

Graph2Route mô hình hóa route prediction dưới dạng đồ thị không gian-thời gian.
M²G4RTP kết hợp dự đoán tuyến và thời gian bằng mô hình đồ thị đa mức, đa nhiệm.
Hai công trình cung cấp cơ sở để thử GNN, nhưng không đủ để chọn GNN trước khi
so sánh với baseline trên giao thức hiện tại. Vì vậy GNN là mô hình ứng viên có
điều kiện, không phải thành phần bắt buộc.

## 7. Chia dữ liệu và kiểm soát rò rỉ

1. Các đơn được gom theo `city`, `courier_id` và ngày vận hành `ds`. Ngày chia
   tập được rút từ thời điểm query, không rút từ thời điểm hoàn tất tương lai của
   từng đơn: query trước tháng 9 dùng huấn luyện, tháng 9 dùng xác nhận và từ
   tháng 10 dùng kiểm định. Cách này giữ đúng ca vận hành nhưng không dùng nhãn
   tương lai để xác định split.
2. Kiểm định phụ giữ lại toàn bộ shipper hoặc toàn bộ thành phố.
3. Các bản ghi của cùng tổ hợp shipper-ngày không được đi qua nhiều tập.
4. Thống kê AOI, tốc độ lịch sử, cạnh đồ thị, bộ mã hóa, chuẩn hóa và imputation
   chỉ được khớp trên tập huấn luyện của từng fold.
5. Amazon được chia ở cấp route. Không chia các stop của một route sang nhiều tập.
6. Tập evaluation Amazon không dùng cho phát triển.
7. Để giới hạn chi phí tính toán trước khi xem kết quả, mỗi thành phố giữ tối đa
   250.000 dòng train, 50.000 dòng validation và 50.000 dòng test bằng hash ổn
   định của khóa mẫu. Amazon giữ tối đa 12 route training mỗi station bằng hash
   route ID. Các giới hạn này được giữ nguyên trong giao thức phiên bản 2.
8. Từ v2, lựa chọn mô hình và mọi cổng quyết định chỉ dùng validation. Test được
   mở một lần để xác nhận cấu hình đã chọn và không được dùng để đổi quyết định.

## 8. Thước đo

### ETA

- MAE theo phút là thước đo chính vì có cách diễn giải trực tiếp.
- RMSE theo phút cho biết mức ảnh hưởng của sai số lớn.
- ACC@20 và median absolute error là thước đo phụ.
- Báo cáo micro và macro theo thành phố để tránh thành phố lớn chi phối kết quả.

### Thứ tự và tối ưu

- Tổng transit time, tổng planned service time, tổng chi phí và thời gian chạy.
- Tỷ lệ nghiệm hợp lệ.
- KRC, HR@3, LSD và edit distance để so sánh thứ tự, phù hợp với giao thức LaDe.
- Không gọi thứ tự gần tài xế hơn là tuyến nhanh hơn nếu không có bằng chứng chi
  phí tương ứng.

## 9. Suy luận thống kê

- Chạy năm seed đã định trước đối với mô hình ngẫu nhiên.
- Với LaDe-D, hiệu ứng được tính ở cấp query nhưng bootstrap chính lấy cụm
  `city × courier_id`; bootstrap query là phân tích độ nhạy. Kiểm định dấu dùng
  hiệu ứng trung bình theo courier. Với Amazon, suy luận chính dùng bootstrap
  theo station và kiểm định dấu trên 17 station.
- Bộ giải deadline mềm được chạy ba lần trên cả 204 tuyến; calibration chọn
  penalty bằng trung bình cost-median của ba lần. Đánh giá dùng median theo tuyến
  trước khi suy luận theo station. Không suy ra nghiệm duy nhất hoặc tối ưu toàn
  cục từ một lần chạy giới hạn thời gian.
- Báo cáo chênh lệch tuyệt đối, chênh lệch tương đối và khoảng tin cậy 95%.
- Không kết luận cải thiện chỉ từ một seed hoặc chỉ từ trung bình toàn bộ.
- Nhánh quan hệ/GNN chỉ được giữ nếu CI validation của chênh query-MAE nằm hoàn
  toàn dưới 0. Test chỉ xác nhận sau quyết định.

## 10. Các kết luận chưa được phép

- Không kết luận mô hình sử dụng giao thông thời gian thực.
- Không kết luận mô hình tối ưu theo trọng lượng hàng.
- Không kết luận tuyến LaDe-D thay thế giúp tiết kiệm thời gian thực tế.
- Không kết luận OR-Tools tìm được tối ưu toàn cục nếu có giới hạn thời gian.
- Không kết luận GNN tốt hơn trước khi hoàn thành baseline, ablation và kiểm định.
