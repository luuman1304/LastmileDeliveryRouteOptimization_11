# Đánh giá overfitting, đuôi dài và mất cân bằng

## 1. Hội tụ và khoảng cách theo thời gian

Ensemble LightGBM năm seed có MAE train 114,54 phút, validation 131,75 phút và
test 118,70 phút. Validation cao hơn train 17,20 phút; test cao hơn train 4,16
phút nhưng thấp hơn validation 13,04 phút. Vì độ khó giữa các tháng không tăng
đơn điệu, không thể gọi riêng các khoảng cách này là overfitting hoặc drift.
Phải đọc chúng cùng early stopping, rolling-origin và lát cắt thành phố.

Năm seed dừng tại 2.455–8.035 vòng trong trần 10.000; MLP dừng tại 63–211 vòng
trong trần 250. Không mô hình chính nào chạm trần. LightGBM được chọn bằng
query-MAE validation, không dùng test.

## 2. Nhãn đuôi dài

Phiên bản v3 giữ mọi ETA dương thay vì lọc `ETA <= 120`. Tập test có 76.701 trên
178.430 dòng vượt hai giờ, gồm 65.917 dòng 2–8 giờ, 8.597 dòng 8–24 giờ và 2.187
dòng trên 24 giờ. ETA tối đa là 54.549 phút. Đuôi này có thể phản ánh đơn tồn
đọng, trì hoãn hoặc quy trình hoàn tất chứ không chỉ thời gian lái xe.

Do đó MAE là metric chính; RMSE 512,81 phút được giữ để biểu hiện độ nhạy với
ngoại lệ, không dùng làm tiêu chí chọn mô hình. Báo cáo thêm median AE, ACC@20 và
metric theo bốn dải ETA. SMOTE hoặc class weight không phù hợp vì đây là hồi quy.

## 3. Mất cân bằng thành phố

Train có 249.994 dòng Hangzhou nhưng 16.624 dòng Jilin; test có khoảng 50.000
dòng cho Chongqing, Hangzhou và Shanghai nhưng chỉ 939 dòng Jilin. Nghiên cứu
giảm rủi ro bằng cap theo thành phố, split theo thời gian, báo cáo per-city và
đồng thời dùng micro/macro MAE.

Inverse-city weighting được chọn hoặc loại chỉ bằng macro-MAE validation. Nhánh
weighted đạt 115,15 phút so với 114,33 của mô hình không trọng số; micro-MAE
validation cũng xấu hơn, 133,18 so với 131,75. Mọi seed weighted dừng trước trần
(3.169–5.664 vòng). Vì vậy mô hình không trọng số được giữ. Test chỉ xác nhận
cùng chiều và không tham gia quyết định.

## 4. Ngoài miền

Leave-one-city-out làm MAE tăng so với mô hình có dữ liệu cùng thành phố ở cả
năm thành phố. Chongqing khó nhất với 238,26 phút; Jilin đạt 93,58 phút nhưng chỉ
có 939 dòng test. AOI chưa thấy chiếm 3,84% test. Kết quả chưa hỗ trợ tự động
triển khai ở thành phố mới; cần calibration hoặc dữ liệu đại diện trước dispatch.

## 5. Rolling-origin và drift

Rolling-origin dùng ba cửa sổ tháng 7, 8 và 9; mỗi cửa sổ tự fit vocabulary,
early stopping và city weighting từ dữ liệu quá khứ. Micro-MAE unweighted lần
lượt là 118,93; 92,04 và 132,31 phút. Macro-MAE trung bình là 109,83 phút, tốt
hơn 111,59 của nhánh weighted. Fold September unweighted ban đầu chạm trần
10.000; sau khi nâng trần rolling lên 15.000, nó dừng hợp lệ tại 14.409. Vì vậy
kết luận weighting xấu hơn không dựa trên một fold chưa hội tụ.

PSI trong `deployment_v3/summary.json` là tín hiệu theo dõi, không phải bằng chứng
nhân quả hay một chuẩn phổ quát. Ngưỡng 0,1/0,25 chỉ là quy tắc vận hành ban đầu
và phải được hiệu chỉnh bằng dữ liệu production.
