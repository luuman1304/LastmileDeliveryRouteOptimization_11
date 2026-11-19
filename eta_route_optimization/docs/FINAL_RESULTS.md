# Kết quả thực nghiệm và kết luận phiên bản 3

## 1. Phạm vi và giao thức

LaDe-D được dùng để dự đoán số phút từ query đến khi hoàn tất từng đơn đang chờ
và đánh giá thứ tự nhiệm vụ. Amazon được dùng cho định tuyến tĩnh vì có ma trận
thời gian giữa mọi cặp điểm. Kết quả không đại diện giao thông thời gian thực,
không tối ưu trọng lượng và không chứng minh hiệu quả thực địa.

Cohort ETA giữ mọi đơn có `accept_time <= query_time < delivery_time`, cap tối đa
25 nhiệm vụ bằng thông tin quan sát được và giữ mọi ETA dương. Không lọc
`ETA <= 120`. Split theo query: train 769.458 dòng/92.615 query, validation
180.719/20.721 và test 178.430/16.346. Tập test có 76.701 dòng ETA trên hai giờ
và ETA tối đa 54.549 phút.

## 2. Dự đoán ETA

Mô hình được chọn bằng query-MAE validation; test không tham gia lựa chọn.

| Mô hình | MAE test | RMSE test | Median AE | ACC@20 |
|---|---:|---:|---:|---:|
| Historical median | 134,25 | 529,99 | 59,00 | 18,86% |
| Effective speed | 219,01 | 2.766,43 | 59,54 | 24,23% |
| KNN | 148,80 | 524,62 | 71,41 | 16,37% |
| **LightGBM, 5 seed** | **118,70** | **512,81** | **40,76** | **29,29%** |
| MLP, 5 seed | 169,87 | 521,44 | 88,01 | 14,63% |

LightGBM có query-MAE validation 187,90 phút, thấp nhất trong năm ứng viên. Năm
seed dừng tại 2.455–8.035 vòng trong trần 10.000; MLP dừng tại 63–211 vòng trong
trần 250. Không run chính nào chạm trần.

So với historical median, chênh query-MAE là -18,11 phút, tương ứng -12,43%.
CI bootstrap cụm `city × courier_id` 95% là [-20,57; -15,76]; bootstrap query
độ nhạy là [-19,87; -16,39]. Mô hình tốt hơn tại 12.089/16.346 query và
2.026/2.540 cụm courier. Hướng cải thiện vẫn âm khi bỏ lần lượt từng thành phố.

Leave-one-city-out suy giảm ở cả năm thành phố; Chongqing khó nhất với MAE
238,26 phút. AOI chưa thấy chiếm 3,84% test. Vì vậy kết quả hỗ trợ mô hình nền
trong năm thành phố đã quan sát, chưa hỗ trợ dispatch tự động tại thành phố mới.

## 3. Mất cân bằng và rolling-origin

Inverse-city weighting làm macro-MAE validation xấu hơn từ 114,33 lên 115,15
phút và micro-MAE từ 131,75 lên 133,18. Mọi seed weighted hội tụ trước trần.
Mô hình unweighted được giữ hoàn toàn theo validation.

Rolling-origin unweighted có micro-MAE 118,93; 92,04 và 132,31 phút cho tháng 7,
8 và 9. Macro-MAE trung bình là 109,83, tốt hơn 111,59 của weighted. Fold
September unweighted được nâng trần riêng và dừng tại 14.409/15.000, nên kết luận
không dựa trên một fit chạm trần.

## 4. Chất lượng thứ tự

Trên 15.247 query có ít nhất hai nhiệm vụ, LightGBM đạt HR@3 0,6157, KRC 0,2975,
LSD 17,401 và edit distance 8,585; tốt nhất trong các baseline chính ở cả bốn
metric. Khi thêm nhiễu chuẩn 5/10/20 phút, KRC trung bình giảm còn
0,280/0,255/0,211. ETA tốt hơn hỗ trợ xếp hạng nhưng không thay thế ràng buộc
tuyến.

## 5. Định tuyến Amazon

Baseline time-window cứng chỉ có nghiệm cho 119/204 tuyến. Deadline mềm chọn
penalty trên 17 tuyến calibration và đánh giá 187 tuyến còn lại, đúng 11 tuyến
mỗi station. Mỗi cấu hình chạy ba lần; kết quả lấy median theo tuyến trước khi
suy luận.

Solver có nghiệm 204/204, fallback 0%. Trên evaluation, chênh operational cost
trung bình là -761,49 giây; CI bootstrap cụm station 95% là
[-1.157,79; -322,42]. Có 14/17 station tốt hơn observed, kiểm định dấu hai phía
`p = 0,0127`. Kết luận giữ hướng khi trọng số lateness là 0,5; 1 hoặc 2.

Chuỗi giống nhau ở cả ba lần trên 189/204 tuyến và cost giống nhau trên 190/204;
biên độ cost trung bình 11,52 giây nhưng lớn nhất 1.106,50 giây. Vì vậy không
tuyên bố nghiệm duy nhất hoặc tối ưu toàn cục.

## 6. Quyết định GNN

Ablation quan hệ chỉ dùng thống kê fit trên train. Trên validation, query-MAE
tăng 11,63 phút, CI 95% [9,93; 13,41]; cổng GNN bị bác bỏ trước khi xem test.
Test xác nhận cùng chiều (+12,69 phút) nhưng không tham gia quyết định. Đây là
kết quả của graph-feature ablation, không phải kết quả của một GNN.

## 7. Kết luận

Bằng chứng mạnh nhất là quy trình ETA không chọn cohort bằng nhãn tương lai,
LightGBM được chọn trên validation và cải thiện có CI cụm courier không chứa 0.
City weighting và đặc trưng quan hệ không tạo giá trị theo tiêu chí định trước.
Deadline mềm cho hiệu ứng thuận lợi trong evaluator Amazon và có kiểm tra lặp,
nhưng vẫn cần shadow mode hoặc thử nghiệm đối chứng trước ứng dụng thực tế.
