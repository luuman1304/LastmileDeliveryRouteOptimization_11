# Data card

## LaDe-D

LaDe-D gồm 4.514.661 đơn tại Chongqing, Hangzhou, Jilin, Shanghai và Yantai.
Nghiên cứu dùng thời điểm nhận và hoàn tất, tọa độ điểm giao, AOI, region,
courier và city. Ba bản ghi có thời gian hoàn tất sớm hơn thời gian nhận bị
loại.

Một query được tạo tại lần giao hoàn tất đầu tiên của mỗi courier trong từng
ngày vận hành `ds`. Trạng thái tại query chỉ gồm các đơn đã nhận và chưa hoàn
tất tại thời điểm đó; mỗi query giữ tối đa 25 đơn theo quy tắc xác định trước.
Nhãn là số phút từ query đến lúc đơn hoàn tất và chỉ yêu cầu dương. Phiên bản v3
không lọc `ETA <= 120` vì phép lọc đó sử dụng kết quả tương lai để quyết định
đơn nào thuộc tập quan sát.

Split dùng thời điểm query: trước tháng 9 là train, tháng 9 là validation và từ
tháng 10 là test. Quy mô cuối là 769.458/180.719/178.430 dòng và
92.615/20.721/16.346 query tương ứng. Tập test có 76.701 dòng ETA trên 120 phút;
ETA lớn nhất là 54.549 phút. Đuôi rất dài phản ánh đơn tồn đọng hoặc hoàn tất
muộn trong dữ liệu và làm RMSE nhạy với ngoại lệ. Vì vậy MAE là chỉ số chính,
đồng thời báo cáo riêng các dải `<=2h`, `2–8h`, `8–24h` và `>24h`.

Giới hạn chính: dữ liệu không có giao thông thời gian thực, trọng lượng, dung
tích xe hoặc trạng thái hủy/thất bại đủ chi tiết. Thành phố mất cân bằng mạnh,
Jilin chỉ có 939 dòng test, và nhãn đuôi dài có thể gồm cả độ trễ quy trình chứ
không chỉ thời gian di chuyển. Do đó mô hình dự đoán thời gian hoàn tất quan sát
được, không được diễn giải như ETA lái xe thuần túy.

## Amazon Last Mile Routing Research Challenge

Phần training có 6.112 tuyến tại 17 station, 1.457.175 kiện và 904.527 stop có
kiện. Dữ liệu có observed sequence, transit matrix, planned service time, time
window của một phần kiện, kích thước kiện và dung tích xe. Thực nghiệm dùng 204
tuyến được chọn xác định bằng SHA-256; 17 tuyến calibration (một tuyến mỗi
station) được tách khỏi 187 tuyến đánh giá.

Chỉ 7,82% kiện có đủ hai đầu time window. Dữ liệu không có thời điểm đến thực tế
tại từng stop, tín hiệu giao thông thời gian thực hoặc trọng lượng. Kích thước
kiện chỉ được dùng để tính thể tích. Tập evaluation chính thức không được dùng
trong phát triển.

Checksum, kích thước tệp, quy tắc tạo query và kiểm tra null được lưu trong
`artifacts/generated/data_audit_v3.json`, `eta_dataset_v3/manifest.json` và
`eta_dataset_v3/validation.json`.
