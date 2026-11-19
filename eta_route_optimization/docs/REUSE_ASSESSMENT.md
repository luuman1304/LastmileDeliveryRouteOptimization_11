# Đánh giá khả năng sử dụng lại source cũ

Nguyên tắc: dự án mới không import package `lastmile_data`. Mã được chấp nhận chỉ
được sao chép có chọn lọc, đổi hợp đồng đầu vào nếu cần và có test riêng trong dự
án này. Kết quả thực nghiệm cũ không được chuyển thành kết quả của đề tài mới.

## 1. Thành phần được chấp nhận

| Thành phần cũ | Nguồn | Cách sử dụng | Lý do |
|---|---|---|---|
| Kiểm tra chuỗi route | `src/lastmile_data/baselines.py` | Sao chép và type hóa trong `routing_baselines.py` | Hợp đồng đơn giản: depot đầu tiên, đủ stop, không trùng |
| Nearest Neighbor | `src/lastmile_data/baselines.py` | Sao chép với tie-break xác định | Baseline tham lam bắt buộc, không phụ thuộc nghiên cứu cũ |
| Directed 2-opt | `src/lastmile_data/baselines.py` | Sao chép cùng giới hạn số pass | Hỗ trợ ma trận bất đối xứng Amazon; không tuyên bố local optimum khi dừng sớm |
| Amazon route adapter | `src/lastmile_data/prepare.py` | Dùng làm tài liệu thiết kế, sẽ viết adapter mới tối giản | Parser hiện tại đã fail-closed nhưng mang schema và city map của bài cũ |
| Các metric thứ tự | `src/lastmile_data/lade_external.py` | Chỉ đối chiếu công thức; triển khai mới theo định nghĩa LaDe/Graph2Route | Cần thống nhất chính xác KRC, HR@3, LSD và ED với nghiên cứu gốc |
| Bootstrap theo nhóm | Nhiều module cũ | Chỉ dùng ý tưởng; triển khai một bản chung mới | Các bản cũ gắn với đơn vị trạm hoặc route khác nhau |

## 2. Thành phần không đưa sang

| Thành phần | Lý do loại |
|---|---|
| JPT-AMZ và các patch | Tối ưu theo lịch sử zone của đề tài cũ, không phải ETA model mới |
| Residual ranker, SARP, CCPO, JIPP | Được thiết kế để sửa hoặc chọn tour JPT, mục tiêu và nhãn không phù hợp |
| Cold-start station evaluator | Có thể học cách chia nhóm nhưng không tái sử dụng trực tiếp vì đơn vị LaDe là shipper-ngày/city |
| Các output và số liệu cũ | Không được tạo dưới giao thức, mục tiêu và metric mới |
| Bộ chọn conformal cũ | Chỉ xem xét lại sau khi có residual ETA hợp lệ; không sao chép trước |

## 3. Thành phần cần đánh giá lại sau baseline

- Cách bootstrap theo cụm có thể dùng lại về nguyên tắc, nhưng cụm LaDe-D phải là
  shipper-ngày thay vì tuyến đơn lẻ.
- Cách tạo manifest chia tập và hash artifact nên được áp dụng lại vì hỗ trợ tái
  lập, nhưng schema manifest phải viết mới.
- Cách kiểm tra station-held-out gợi ý cho leave-one-city-out, nhưng không được
  xem là bằng chứng rằng cùng một hiệu ứng sẽ xuất hiện trong nghiên cứu mới.
- Conformal prediction chỉ được đưa vào nếu câu hỏi nghiên cứu bổ sung yêu cầu
  khoảng dự báo ETA và có tập calibration độc lập.

## 4. Trạng thái

`routing_baselines.py` là phần mã đầu tiên đã được tách. Nó có test cho tính hợp
lệ, tie-break và điều kiện 2-opt không làm tăng chi phí trên ví dụ kiểm thử. Đây
chỉ là kiểm tra đơn vị, chưa phải kết quả thực nghiệm.
