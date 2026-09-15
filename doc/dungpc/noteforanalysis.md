## Bước 0 — Liệt kê những gì sơ đồ không nói

1. Address decoding — đường từ SoC BUS sang APB BUS không cho biết dải địa chỉ nào, decode ở đâu
2. Chính sách phân xử tại TCDM interconnect và SoC bus (round-robin? priority? ai thắng khi đụng?)
3. Outstanding transaction và backpressure 
4. Mạng event/interrupt
5. Trục thời gian

## Phương pháp 1 - Skim - Đọc cùng một sơ đồ 5 lần, mỗi lần chỉ nhìn MỘT lớp

Lỗi phổ biến nhất là cố nhìn tất cả cùng lúc rồi thấy rối. Tách thành 5 lớp trực giao, mỗi lớp vẽ lại một bản sơ đồ riêng:

### Lớp 1 — Địa chỉ (master/slave). 
Xóa hết mọi thứ, chỉ giữ: cái gì là initiator, cái gì là target, dải địa chỉ nào. Trên hình này các master là: FC core, uDMA, cluster DMA, cluster cores, debug module. Target: L2, ROM, APB peripherals, TCDM. Sản phẩm: một bảng memory map + một ma trận master–slave (hàng = master, cột = slave, ô = có đi được không, qua bridge nào). Đây là lớp nền — mọi lớp sau đều tham chiếu về nó.

### Lớp 2 — Giao thức & băng thông.
Mỗi đường gán 3 thuộc tính: protocol (AXI / APB / TCDM / stream), độ rộng, và lớp độ trễ (1 chu kỳ / pipelined / nhiều chu kỳ). Chỗ nào đổi độ rộng thì ở đó có converter; chỗ nào đổi protocol thì ở đó có bridge. Liệt kê hết bridge ra — đó chính là axi2per, per2axi, axi2mem, apb2per. Lớp này cho bạn biết nút thắt băng thông nằm ở đâu, và với mục tiêu "thành thạo interconnect" của bạn thì đây là lớp đáng đầu tư nhất.

### Lớp 3 — Miền vật lý (clock / reset / power).
Khoanh vùng: đếm số FLL → biết số clock domain. Mỗi khối DC FIFO trên hình = một biên clock domain. Cluster power-gate được → có isolation cell và trình tự bật/tắt. Câu hỏi then chốt: mỗi tín hiệu qua biên được đồng bộ bằng cách gì? (dual-clock FIFO, 2-FF synchronizer, token ring). Đây là lớp mà sơ đồ logic thường che mất, và cũng là chỗ dễ sai nhất khi bạn tự làm SoC.

### Lớp 4 — Điều khiển & sự kiện.
Không phải dữ liệu, mà là: ai đánh thức ai. Peripheral sinh event → SoC event unit → interrupt FC hoặc wake cluster. DMA xong → event. 8 core gặp barrier → event unit cho ngủ. Lớp này gần như không có trên sơ đồ, và nó chính là thứ giải thích tại sao PULP ultra-low-power: mô hình không phải "CPU điều khiển mọi thứ" mà là "CPU ngủ, sự kiện đánh thức". Ai bỏ qua lớp 4 thì hiểu PULP như một SoC bình thường, tức là hiểu sai trọng tâm.

### Lớp 5 — Vòng đời.
Vẽ một FSM của cả con chip: reset → boot ROM → chọn nguồn boot → chạy FC → bật cluster → giao việc → cluster ngủ → tắt cluster. Lớp này biến ảnh tĩnh thành chuyện động.

## Phương pháp 2 — Trace

Sau 5 lớp, bạn có bản đồ. Giờ mới đến phần thực sự tạo ra hiểu biết: chọn khoảng 10 giao dịch cụ thể và lần từng cái từ đầu đến cuối. Mỗi câu chuyện đi qua 5–10 module; 10 câu chuyện phủ gần hết con chip — và quan trọng hơn, chúng phủ theo đúng cách con chip thực sự hoạt động, chứ không theo thứ tự file trong repo.

### Danh sách đề xuất, xếp theo độ khó tăng dần:

1. FC nạp lệnh đầu tiên sau reset (ROM → FC bus)
2. FC ghi một thanh ghi GPIO (SoC bus → bridge → APB → apb_node → gpio)
3. Một byte UART vào → uDMA ghi thẳng vào L2, không qua CPU
4. FC bật cluster: clock, reset, power, fetch_enable — qua những thanh ghi nào, theo thứ tự nào
5. FC giao việc cho cluster và cluster bắt đầu chạy
6. Cluster DMA (mchan) kéo một tile từ L2 → TCDM: qua cluster bus → DC FIFO → SoC interconnect → L2 bank
7. 8 core cùng đọc TCDM trong một chu kỳ → bank conflict, ai stall
8. I$ miss của một core → refill qua AXI ra L2
9. Barrier: 8 core gặp nhau ở event unit rồi ngủ, core cuối đánh thức cả nhóm
10. Cluster xong việc → event → interrupt về FC

Mỗi câu chuyện đi 3 lần:

Lần 1 — trên sơ đồ, bằng bút chì, 5 phút. Dự đoán đường đi. Viết dự đoán ra.
Lần 2 — trong RTL. Grep tên tín hiệu, lần qua từng module, xác minh.
Lần 3 — trong waveform. Đặt cursor, đi theo transaction thật.

Chỗ nào ba lần không khớp nhau chính là chỗ bạn thực sự học được điều mới — ghi lại chỗ đó. Sau vài tuần, tập ghi chú "những chỗ tôi đoán sai" sẽ có giá trị hơn toàn bộ phần đọc suôn sẻ cộng lại.

## Phương pháp 3 — Sáu câu hỏi cho mỗi khối

Khi dừng lại ở một khối bất kỳ, tự trả lời đủ 6 câu trước khi đi tiếp:

Nó là master, slave, hay cả hai?
Nó nói giao thức gì, ở phía nào?
Cấu hình nó bằng cách nào — thanh ghi nào, ai ghi?
Nó báo cáo bằng cách nào — interrupt, event, hay phải polling?
Nó ở clock domain nào, tắt được không?
Nếu xóa nó đi thì cái gì hỏng?

Câu 6 là câu quan trọng nhất. Nó buộc bạn phát biểu ra vai trò thật của khối, thay vì chỉ thuộc tên. Nếu không trả lời được câu 6, bạn chưa hiểu khối đó.

Sản phẩm cuối: 4 thứ bạn tự tạo, không copy

Hiểu được đo bằng cái bạn vẽ lại được từ đầu, không phải số file đã đọc:

Memory map một trang — từ góc nhìn FC và từ góc nhìn một cluster core (hai bản đồ khác nhau!)
Ma trận master–slave — ô nào trống cũng có ý nghĩa
Sơ đồ miền clock/power/reset với đầy đủ điểm CDC
10 transaction story, mỗi cái một trang kèm ảnh waveform