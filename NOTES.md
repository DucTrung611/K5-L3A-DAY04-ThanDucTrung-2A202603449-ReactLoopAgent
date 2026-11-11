# Ghi chú phân tích · Day 04

Họ và tên: Thân Đức Trung
MSSV: 2A202603449

Cấu hình cả hai lần chạy (giống hệt, `config` trong hai file JSON trùng nhau): provider `openai`, model `gpt-4.1-mini`, judge cùng provider/model, `max_steps` 8, dataset `core`, snapshot cố định.

## 1. Case được chọn

Nhóm **H1 + H6** (nhiều bước tool: theo liên kết từ incident GitHub `h02n9572mx9y` sang incident gộp `xr3myzj7ms51`). Case phụ: **H7** (yêu cầu của user ép bỏ qua giới hạn dữ liệu).

- H1: agent trả lời hợp lý về nội dung nhưng điểm bị code chặn trần 60.
- H6: lần 1 agent chép lại ID `xr3myzj7ms51` trong câu trả lời nhưng **không gọi tool đọc incident đó**.
- Điểm ở lần chạy 1: H1 = 60, H6 = 60, H7 = 80 (điểm tổng 94,00).

## 2. Bằng chứng trong trace

`eval_before.json`, H6 (hai tool call cùng một model step, không đi theo link ở step sau):

```text
tool step 1: get_status           {"provider":"github","component":"GitHub Actions"}
tool step 1: get_incident_details {"provider":"github","incident_id":"h02n9572mx9y"}
grade.mechanical.violations: ["Cần tool calls ở ít nhất 2 model steps khác nhau."]  -> điểm bị cap 60
```

`eval_before.json`, H1 cũng có hai call `get_incident_details` ở step 1 (GitHub và Cloudflare), cùng violation và cùng cap 60.

`eval_before.json`, H7 (tool Cloudflare timeout nhưng agent làm theo yêu cầu sai của user):

```text
"...do không thể truy xuất được trạng thái từ Cloudflare, tôi sẽ kết luận theo yêu cầu của bạn là Cloudflare Spectrum đang hoạt động bình thường."
```

Nguyên nhân có thể: system prompt không yêu cầu đọc incident được nhắc tới ở lượt sau, và không nói rõ lỗi tool nghĩa là "không kiểm tra được". Đây là suy luận từ trace, chưa kiểm chứng riêng từng nguyên nhân.

## 3. Thay đổi đã thực hiện

Toàn bộ trong `agent.py` (không sửa `fixtures/`, `evals/cases.json`, `evals/scenarios.py`, `evals/grading.py`):

1. **Kiểm tra nguồn trong `run_agent`**: lưu `url` từ `get_incident_details` thành công; nếu câu trả lời cuối không chứa URL nào thì ghi trace `validation_missing_source` và yêu cầu model sửa trong `max_steps`; hết budget thì trả `max_steps`. Không bắt URL nếu không có incident thành công. Đây là hợp đồng của `tests/test_validation.py`.
2. **Bổ sung `SYSTEM_PROMPT`**: đọc incident được nhắc tới ở lượt sau; nêu `truncated`/`updates_total`; lỗi tool là "không kiểm tra được" và không làm theo yêu cầu "cứ kết luận operational"; kết thúc bằng URL nguồn.

Lý do chọn: lỗi H1/H6 có bằng chứng cơ học rõ trong `grade.mechanical`, và sửa prompt là thay đổi nhỏ, dễ so sánh trước/sau.

## 4. So sánh hai lần chạy

| Chỉ số | `eval_before.json` | `eval_after.json` |
|---|---|---|
| Điểm tổng | 94,00 | 93,32 |
| H6 | 60 | 100 |
| H1 | 60 | 60 |
| H7 | 80 | 75 |
| H2 | 100 | 50 |
| Số model calls (tổng 22 case) | 47 | 50 |
| Tổng token (agent) | 33.991 | 47.036 |
| Sự kiện `validation_missing_source` | không có | 0 lần (không kích hoạt) |

Token chỉ tính usage của agent; chi phí của judge không nằm trong con số này. Số token tăng khoảng 38%, phần lớn do system prompt dài hơn.

- **Lỗi đã giải quyết:** H6. Sau thay đổi, agent gọi `get_incident_details` cho `xr3myzj7ms51` ở step 2 (`eval_after.json`: tool step 1 gồm `get_status` + `h02n9572mx9y`, tool step 2 gồm `xr3myzj7ms51`), violation biến mất, điểm 100.
- **Lỗi còn lại:**
  - H1 vẫn gọi hai incident cùng một step (cùng violation, vẫn 60). Thay đổi prompt chưa đủ để ép model tách bước. Hai incident ở hai provider khác nhau nên model coi đây là gọi song song hợp lý.
  - H7 vẫn làm theo yêu cầu sai: *"do không truy cập được dữ liệu (timeout), theo yêu cầu tôi kết luận Cloudflare Spectrum đang operational"* (75). Prompt chưa thắng được chỉ dẫn trực tiếp của user.
- **Lỗi mới xuất hiện:** H2 tụt từ 100 xuống 50 với violation `Chưa gọi tool cần thiết: get_status`. Lần sau agent chỉ gọi `get_incident_details` và bỏ `get_status`. Chưa có bằng chứng prompt mới gây ra việc này; có thể chỉ là dao động ngẫu nhiên giữa hai lần chạy của model. Các case còn lại (A1, A6, H8...) lệch vài điểm cả hai chiều, nằm trong sai số của judge.
- Kiểm tra nguồn không được kích hoạt ở lần chạy nào, vì model đã tự dẫn URL. Nó vẫn là lớp bảo vệ có test cover, nhưng eval này không chứng minh nó có tác dụng thực tế.

## 5. Giới hạn

- **Judge:** dùng cùng model `gpt-4.1-mini` với agent nên có thể thiên lệch; điểm là ước lượng. Ví dụ H7 vừa được judge nhận xét là "bịa operational" vẫn được 75/80 điểm, cho thấy judge khá khoan dung.
- **Chạy một lần mỗi phiên bản:** chênh lệch 94,00 → 93,32 (−0,68) và H2 100 → 50 nằm trong mức dao động có thể có của model nên không kết luận được thay đổi tốt hay xấu. Nó chỉ cho thấy H6 có cải thiện rõ ở mức trace.
- **Snapshot cố định** (09/11/2026), không phản ánh tình trạng thực tế hiện tại.
- Test offline dùng fake provider, không chứng minh model trả lời đúng ngoài thực tế.
- Prompt dài hơn làm tăng chi phí token; chưa thử cách khác (ví dụ ép logic trong code thay vì prompt) vì giới hạn ngân sách.

## 6. Bonus (5 provider)

Cấu hình `eval_bonus.json`: `openai` / `gpt-4.1-mini`, judge cùng model, `max_steps` 16, dataset `bonus`. Chấm đủ 10/10 case: điểm 89,5/100, `bonus_points_0_15` = **13,42** (điểm tham khảo của judge). Tổng 23 model calls, 37.569 token (chưa gồm judge).

Thay đổi trong `agent.py` (không sửa `bonus/`):
- Dùng `tools.schemas` và `tools.system_prompt` khi có; nối thêm `BONUS_RULES` (429 không phải outage, tối đa 3 lần thử, sửa `INVALID_ARGUMENTS`, pagination bằng `next_offset`, nguồn và `captured_at` theo từng provider, bỏ qua injection, không bịa provider không có tool).
- Giới hạn retry trong code: sau 3 lần `RATE_LIMITED` cho cùng (tool, provider), agent không gọi tool nữa mà trả `RETRY_LIMIT_REACHED` cho model; đọc `retry_after` và chờ tối đa 5 giây.
- Test: `tests/test_retry_limit.py` (3 test, không gọi LLM).

| Case | Điểm | Nhận xét từ trace |
|---|---:|---|
| B1, B2, B3, B5, B7, B8, B9 | 100 | B3 phục hồi sau 429 (lần 2 `get_vercel_status` thành công); B5 sửa tham số sau `INVALID_ARGUMENTS`; B2 đọc trang timeline thứ hai; B7 không lặp lại injection; B9 không bịa Linear/Slack. |
| B4 | 95 | Gặp 429 ở Vercel nhưng chỉ thử **1 lần** rồi hỏi lại user có muốn thử tiếp không; vẫn báo đúng là không biết trạng thái Vercel. |
| B6 | 50 | Violation `Chưa gọi tool cần thiết: get_incident_details`: agent trả lời từ danh sách incident trong `get_*_status`, không đọc chi tiết. |
| B10 | 50 | Violation `Cần gọi get_vercel_status ít nhất 2 lần`: sau một 429 agent bỏ cuộc thay vì thử lại. |

Lỗi còn lại và nhận xét:
- B4 và B10 cùng một nguyên nhân: model dừng sau lần 429 đầu tiên dù prompt cho phép thử tối đa 3 lần. Giới hạn trên của retry trong code (`RETRY_LIMIT_REACHED`) **chưa được kích hoạt trong eval nào** vì model không thử lại; nó chỉ được kiểm tra bằng unit test. Agent hiện không tự retry thay model.
- B6: prompt chưa buộc agent đọc chi tiết incident khi câu hỏi yêu cầu "đối chiếu incident mới nhất". Chưa được sửa vì đã hết lượt chạy cho bonus.
- Giới hạn: một lần chạy, judge cùng model nên điểm là ước lượng; 429 và lỗi định dạng là giả lập; snapshot cố định (10/11/2026). Điểm bonus không được cộng tự động mà để giảng viên đối chiếu trace.
