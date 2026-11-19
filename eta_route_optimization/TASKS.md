# Kế hoạch thực hiện và cổng chất lượng

Ký hiệu: `[ ]` chưa làm, `[x]` đã hoàn thành, `[!]` bị chặn.

## Giai đoạn 0. Đóng băng phạm vi

- [x] Tách dự án khỏi source nghiên cứu cũ.
- [x] Kiểm toán schema và quy mô hai bộ dữ liệu.
- [x] Ghi các tuyên bố không được phép về giao thông, trọng lượng và phản thực.
- [x] Xác minh nguồn gốc của LaDe, Amazon, LightGBM, Graph2Route, M²G4RTP và
  OR-Tools.

**Cổng hoàn thành:** tài liệu nghiên cứu, dữ liệu và quyết định không mâu thuẫn.

## Giai đoạn 1. Hợp đồng dữ liệu và kiểm toán tái lập

- [x] Hoàn thiện CLI audit cho toàn bộ năm tệp LaDe-D và Amazon training.
- [x] Xuất schema, checksum, số dòng, null, duplicate và phân phối theo thành phố.
- [x] Định nghĩa quy tắc xử lý ba thời gian âm, thời gian kéo dài bất thường và GPS
  thiếu trước khi tạo split.
- [x] Viết unit test cho parser thời gian `MM-DD`, ranh giới ngày và thứ tự sự kiện.
- [x] Đối chiếu số đếm của CLI với snapshot kiểm toán ngày 16-11-2026.

**Cổng hoàn thành:** cùng dữ liệu tạo cùng báo cáo; không sửa raw data.

## Giai đoạn 2. Dataset ETA không rò rỉ

- [x] Xác định rõ thời điểm truy vấn và tập đơn chưa hoàn tất tại thời điểm đó.
- [x] Chỉ tạo feature có sẵn tại thời điểm truy vấn.
- [x] Tạo split forward-time theo thành phố.
- [x] Đánh giá riêng courier chưa thấy và leave-one-city-out.
- [x] Fit thống kê AOI/cạnh và scaler bên trong training fold.
- [x] Kiểm tra không có query hoặc sample đi qua nhiều tập.

**Cổng hoàn thành:** test tự động phát hiện mọi feature dùng delivery time tương lai.

## Giai đoạn 3. Baseline ETA

- [x] Historical median theo training fold.
- [x] SPEED theo định nghĩa tái lập được.
- [x] KNN.
- [x] LightGBM.
- [x] MLP không đồ thị.
- [x] Chạy năm seed khi mô hình có ngẫu nhiên.
- [x] Báo cáo MAE, RMSE, ACC@20 và median AE theo từng thành phố.

**Cổng hoàn thành:** kết quả có config, seed, thời gian chạy và prediction cấp mẫu.

## Giai đoạn 4. Baseline định tuyến

- [x] Chuẩn hóa hàm chi phí Amazon: transit time và planned service time báo cáo
  riêng, sau đó mới tính tổng.
- [x] Kiểm tra depot, số lần thăm stop, stop thiếu và stop trùng.
- [x] Observed sequence.
- [x] Nearest Neighbor.
- [x] Nearest Neighbor + 2-opt.
- [x] OR-Tools với time limit cố định 2 giây theo giao thức đã đóng băng.
- [x] Báo cáo feasibility, tổng chi phí, runtime và khoảng cách với observed route.

**Cổng hoàn thành:** mọi phương pháp dùng chung một evaluator và cùng tập route.

## Giai đoạn 5. Tích hợp ETA với định tuyến

- [x] Xác định ETA LaDe-D không đủ để tạo ma trận cạnh phản thực và không dùng nó
  như ma trận chi phí giả.
- [x] Ngăn dùng thứ tự tương lai làm feature ETA.
- [x] Đánh giá sensitivity khi ETA bị nhiễu.
- [x] Tách rõ đánh giá phản thực Amazon và đánh giá mô hình trên LaDe-D.
- [x] Không dùng predicted objective làm bằng chứng duy nhất cho chính predictor đó.

**Cổng hoàn thành:** sơ đồ nhân quả của dữ liệu đầu vào, dự đoán và evaluator không
có vòng tự đánh giá.

## Giai đoạn 6. Quyết định GNN

- [x] Tổng hợp kết quả baseline và xác định sai số còn lại theo AOI/cạnh.
- [x] Kiểm tra graph có thêm thông tin ngoài feature bảng hay không.
- [x] Gate không đạt nên ghi quyết định không triển khai encoder đồ thị; nếu đạt mới
  triển khai encoder đồ thị quy nạp có edge feature và decoder
  thứ tự; nếu không đạt, ghi quyết định không dùng GNN.
- [x] Ablation graph-feature so với cùng LightGBM nền trên năm seed, với quyết
  định chỉ dựa trên validation và test chỉ dùng xác nhận.
- [x] Dừng nhánh GNN theo gate; không tạo số tham số/runtime giả cho mô hình chưa chạy.

**Cổng hoàn thành:** quyết định giữ hoặc loại GNN dựa trên giao thức validation
đóng băng, không dựa trên test hay một run tốt nhất.

## Giai đoạn 7. Kiểm định và độ bền

- [x] Bootstrap theo query cho LaDe-D; bootstrap cụm station và kiểm định dấu cho Amazon.
- [x] Khoảng tin cậy 95% cho chênh lệch ghép cặp.
- [x] Phân tích thành phố, giờ trong ngày, khoảng cách và số nhiệm vụ đang chờ.
- [x] Stress test AOI chưa thấy, thời gian bất thường, nhiễu ETA và edge chưa thấy.
- [x] Kiểm tra kết luận khi bỏ lần lượt từng thành phố.
- [x] Kiểm tra leave-one-station-out và độ ổn định ba lần chạy trên 34 tuyến.

**Cổng hoàn thành:** kết luận chính không chỉ dựa trên micro average.

## Giai đoạn 8. Báo cáo

- [x] Bảng claim-evidence liên kết từng phát biểu với artifact.
- [x] Data card và model card.
- [x] Quy trình được mô tả tuần tự trong giao thức và không có mũi tên mơ hồ.
- [x] Tài liệu tái lập, môi trường, checksum, seed và lệnh chạy.
- [x] Phần hạn chế nêu rõ thiếu traffic, weight và counterfactual route outcome.
- [x] Kiểm tra toàn bộ trích dẫn bằng DOI hoặc nguồn chính thức trước khi nộp.

**Cổng hoàn thành:** không có số liệu thủ công không truy được về artifact.

## Giai đoạn 9. Điều kiện trước khi triển khai thực tế

- [x] Đánh giá rolling-origin trên nhiều cửa sổ thời gian thay vì một test tháng 10.
- [x] Thử city-balanced sample weight và chọn bằng macro MAE trên validation.
- [x] Thay time window cứng bằng penalty mềm được hiệu chỉnh trên calibration và
  nâng tỷ lệ route có nghiệm vượt mức 58,33% hiện tại.
- [x] Xác nhận ngoài mẫu bằng leave-one-city-out và test tháng 10 không dùng để chọn mô hình.
- [x] Đo latency, bộ nhớ, drift và thiết kế fallback trước khi tích hợp vận hành.

Các mục này không ngăn hoàn thành thực nghiệm nghiên cứu phiên bản 1, nhưng là
điều kiện bắt buộc nếu mục tiêu chuyển từ báo cáo nghiên cứu sang triển khai thật.
