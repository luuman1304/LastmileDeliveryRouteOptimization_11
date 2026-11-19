# Model card

## Mô hình ETA được chọn

Mô hình chính là ensemble trung bình của năm LightGBM regressor với seed 17, 29,
43, 71 và 101. Đầu vào gồm thời điểm query, thời gian chờ, khoảng cách thẳng,
quan hệ cùng AOI/region, số nhiệm vụ đang chờ, thứ tự nhận đơn, tọa độ và loại
AOI. Số nhiệm vụ chờ, thứ tự và cap được xác định từ trạng thái tại query. Mọi
nhãn ETA dương đều được giữ; không có feature hoặc bộ lọc cohort nào dùng
delivery time tương lai ngoài việc tạo nhãn.

Mô hình được chọn bằng query-MAE trên validation, không dùng test. Trên 178.430
mẫu test, mô hình đạt MAE 118,70 phút, RMSE 512,81 phút và ACC@20 29,29%. So với
historical median, query-MAE giảm 12,43%; CI bootstrap cụm city-courier 95% là
[-20,57; -15,76] phút. Năm seed dừng tại 2.455–8.035 vòng trong trần 10.000.
Không nên dùng ngoài năm thành phố mà không hiệu chỉnh, cũng không nên hiểu đầu
ra là thời gian lái xe thuần túy vì nhãn có đuôi rất dài và gồm cả chờ, phục vụ
hoặc độ trễ quy trình.

## Bộ giải tuyến

OR-Tools transit-only luôn trả nghiệm trong mẫu 204 tuyến nhưng không kiểm soát
trễ. OR-Tools với time window cứng chỉ có nghiệm cho 58,33% tuyến. Phiên bản
deadline mềm chọn penalty trên 17 tuyến calibration và tìm được nghiệm cho
204/204 tuyến với giới hạn một giây; fallback nearest-neighbor + 2-opt được định
nghĩa nhưng không phải dùng. Mỗi tuyến được chạy ba lần và lấy median trước khi
suy luận. Trên 187 tuyến giữ lại, 14 trong 17 station có chênh lệch operational
cost theo hướng thuận lợi; CI bootstrap cụm station là [-1.157,79; -322,42]
giây. Chuỗi giống nhau ở cả ba lần trên 189/204 tuyến; biên độ cost lớn nhất vẫn
là 1.106,50 giây. Bộ giải cần thử nghiệm vận hành và không được xem là tạo nghiệm
tối ưu duy nhất.

Benchmark cục bộ của một LightGBM seed-17 có file 17,33 MB, median latency
1,99 ms cho một dòng và 396,28 ms cho batch 4.096. Các số này chưa gồm API,
feature store, mạng hoặc giám sát. Ensemble năm mô hình có thể tốn xấp xỉ năm
lần nếu chạy tuần tự; RSS 1,11 GB gồm Python và dữ liệu đã nạp, không phải bộ nhớ
riêng của model.

## Mô hình không được chọn

MLP dừng sớm hợp lệ trong trần 250 nhưng kém LightGBM trên validation. GNN không
được triển khai vì ablation quan hệ làm query-MAE validation xấu hơn 11,63 phút,
CI 95% [9,93; 13,41]. Hai quyết định có thể được xem xét lại nếu giao thức hoặc
dữ liệu đầu vào thay đổi.
