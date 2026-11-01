# QUY LUẬT LÀM INVOICE SHIRAI (học từ bộ 1: PO → invoice)

> Chỉ ghi **quy luật**, không có số liệu thật của khách. Dữ liệu từng mặt hàng (SL/kiện…) nằm trong file dữ liệu học
> người dùng nạp ở **Cài đặt → Dữ liệu học**, không đưa vào repo. Mẫu đối chiếu: invoice do người dùng cung cấp.

## Đọc PO
- PO Shirai có thể là `.xls` hoặc `.xlsx` (`excel_rows`; `.xls` dùng `xlrd`, có vá lỗi tên liên kết ngoài hỏng của file Shirai).
- Cột: B mã khách, E mô tả, F ngày giao, G số lượng, H đơn giá, I thành tiền; số PO ở ô `Po.No …`.
- PO có thể chia nhiều ngày giao. **Người dùng chọn ngày nào để khai**: chọn cả → một invoice + một tờ khai; chọn một ngày →
  invoice và tờ khai riêng cho ngày đó, ngày còn lại làm sau. Hồ sơ phân biệt theo (khách, PO, **ngày khai**) nên các lần khai
  của cùng một PO không ghi đè nhau; mỗi lần khai có thư mục ngày riêng (`HAI_QUAN/<Khách>/<Năm>_Thang_<mm>/<ngày>/`).

## Dòng hàng
| Hạng mục | Quy luật |
|---|---|
| Tên | `Carton Box…` → `Thùng ` + tên; `Pad…` → `Tấm lót ` + tên; `Inner Pad…` → `Tấm ` + tên (không có "lót"); gộp khoảng trắng thừa |
| Thứ tự | đúng thứ tự dòng của PO (`po_seq`) |
| Thành tiền | **luôn = SL × đơn giá**. Thành tiền ghi trên PO khác thì **báo ở "Kiểm tra trước khi xuất"** |
| kg/cái | từ thư viện cân nặng (thùng: trọng lượng nhà cung cấp; tấm lót: `làm tròn(g/1000, 2)`) |
| Tịnh | `làm tròn half-up(SL × kg/cái, 2)` (kiểu Excel: 51,145 → 51,15; `round_half_up`) |
| Cả bì | tịnh + bì mỗi dòng, **thường 0,02 (đôi khi 0,01)**; mặc định 0,02. Có thể nhập `0.08%` để tính theo phần trăm (invoice 57 dùng 0,08%) |
| Số kiện | `làm tròn lên(SL ÷ SL/kiện)`. SL/kiện ưu tiên định mức đã nhớ cho mặt hàng, chưa có thì theo loại: thùng 10; tấm lót AF*, BF_1, Inner Pad 50; WF_1, WF_2 20; WF/BF không số thứ tự: không đoán (báo thiếu) |

## Mẫu invoice (`build_pkl_shirai_sheet`)
12 cột A–L, cột B (Mã hàng) **ẩn**; tên sheet `d,m` (vd `25,5`); `PXKKVCNB : <số>`, `Ngày: dd/mm/yyyy`; cột PO ghi `Po.No <số PO>`;
trọng lượng ghi sẵn thành số; thành tiền là công thức; Tổng bằng `SUBTOTAL` ngay dưới dòng hàng; cấu hình in A4 dọc, tỉ lệ 47%, lặp hàng 11.
Địa chỉ công ty và khách lấy từ **Cài đặt** và **Khách hàng** (người dùng tự cập nhật khi đổi địa chỉ hành chính).

## Việc còn mở
- Cả bì của thùng trong invoice 57 không khớp hoàn toàn một công thức (115/144 dòng khớp khi dùng 0,08%).
- Hai file đơn đặt hàng gửi nhà cung cấp (Ojitex, SP Vina) chỉ là **nguồn dữ liệu cũ** để học; phần mềm không cần tạo.
