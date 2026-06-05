
---

# 📑 THE ULTIMATE CAVEMAN HARNESS SPECIFICATION & PROMPT BLUEPRINT

> **Version:** 2.0 (Production-Ready)
> **Architecture Style:** Anti-RAG / Flat-SQLite / JIT Surgical Discovery / Executable Spec
> **Token Target:** Always $O(1)$ relative to total repo size.

---

## Part 1: Hệ Cơ Sở Dữ Liệu Phẳng (SQLite Master Schema)

Hệ thống Harness loại bỏ hoàn toàn các Vector DB phức tạp. Toàn bộ trạng thái hệ thống, log thực thi, bộ định tuyến và dữ liệu kiểm thử được quản lý tập trung trong một file cơ sở dữ liệu duy nhất: `.harness/core/harness_state.db`.

```sql
-- Thao tác khởi tạo: Chạy một lần duy nhất để thiết lập hệ thống
PRAGMA foreign_keys = ON;

-- 1. BẢNG QUAN LÝ LOG THỰC THI NGẮN HẠN (Memo 3)
-- Chức năng: Lưu lại vết từng bước sửa code để Rollback hoặc nén dữ liệu.
CREATE TABLE IF NOT EXISTS execution_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_file TEXT NOT NULL,
    action_taken TEXT NOT NULL,
    output_summary TEXT,
    status TEXT CHECK(status IN ('SUCCESS', 'FAILED')),
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 2. BẢNG CỘT MỐC DÀI HẠN (Memo 3)
-- Chức năng: Lưu trữ tóm tắt luồng suy nghĩ sau khi dọn dẹp log ngắn hạn.
CREATE TABLE IF NOT EXISTS long_term_milestones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    milestone_description TEXT NOT NULL,
    compressed_steps_count INTEGER,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 3. BẢNG RANH GIỚI VÀ ĐẶC TẢ KỸ THUẬT (Memo 5, 7, 8)
-- Chức năng: Cô lập phạm vi tác động trong Monorepo và định nghĩa máy trạng thái.
CREATE TABLE IF NOT EXISTS technical_specs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sub_project_path TEXT NOT NULL, -- Đường dẫn sub-project (Workspace Anchor)
    target_file TEXT NOT NULL,       -- File chịu tác động chính
    pre_conditions TEXT NOT NULL,    -- Trạng thái trước khi chạy
    post_conditions TEXT NOT NULL,   -- Trạng thái mong muốn đầu ra
    strict_constraints TEXT          -- Ràng buộc bất biến (Không refactor ngầm...)
);

-- 4. BẢNG ĐỊNH TUYẾN TRÍCH XUẤT LAI (Memo 14)
-- Chức năng: Lưu chỉ số Cyclomatic Complexity để quyết định nạp FULL hay SKELETON.
CREATE TABLE IF NOT EXISTS migration_router (
    file_path TEXT PRIMARY KEY,
    cyclomatic_complexity INTEGER NOT NULL,
    ingestion_mode TEXT CHECK(ingestion_mode IN ('SKELETON', 'FULL')) NOT NULL
);

-- 5. BẢNG KHẲNG ĐỊNH BUSINESS - EXECUTABLE SPEC (Memo 15, 16)
-- Chức năng: Lưu bộ dữ liệu Mock JSON để tự động chạy test local bằng code thuần.
CREATE TABLE IF NOT EXISTS business_assertions (
    rule_key TEXT PRIMARY KEY,
    target_file TEXT NOT NULL,
    input_mock_json TEXT NOT NULL,  -- Định dạng dữ liệu đầu vào giả lập
    expected_output TEXT NOT NULL,  -- Đáp án chính xác bắt buộc phải khớp
    last_validated DATETIME
);

-- 6. BẢNG LỖI DÂY CHUYỀN XUYÊN DỰ ÁN (Memo 21)
-- Chức năng: Hàng đợi lưu các file bị vạ lây khi compiler toàn cục bắn lỗi.
CREATE TABLE IF NOT EXISTS cascade_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    root_task_id INTEGER,
    affected_file TEXT NOT NULL,
    error_message TEXT NOT NULL,
    status TEXT CHECK(status IN ('PENDING', 'FIXED')) DEFAULT 'PENDING'
);

```

---

## Part 2: Ma Trận Vòng Đời Luồng Dữ Liệu (The Pipeline)

Mỗi thay đổi (Change Request) của bạn sẽ đi qua đúng 4 bước thô bạo, khép kín để triệt tiêu việc burn token lãng phí và bảo vệ tính toàn vẹn của logic.

```text
[Yêu cầu thô] ──► 1. Requirements Phase ──► (Gen Spec, Mock JSON -> Lưu SQLite)
                                 │
                                 ▼
                  2. Ingestion Routing ──► (Đo Complexity -> Trộn Full/Skeleton)
                                 │
                                 ▼
                  3. Development Loop  ──► (Search/Replace Block + Self-Healing)
                                 │
                                 ▼
                  4. Testing Gate      ──► (Test Assertions + Diff Git + Human Check)

```

---

## Part 3: Bộ Prompt Master Toàn Diện (Harness Prompts Set)

### 📋 MÔ-ĐUN 1: `requirements_agent.md`

* **Thời điểm kích hoạt:** Chạy khi nhận yêu cầu thô từ người dùng.
* **Mục tiêu:** Tạo cấu trúc dữ liệu phẳng ép khuôn cho các bước sau.

```markdown
# SYSTEM ROLE: HARNESS REQUIREMENTS INJECTOR (STRICT MODE)

You are the deterministic analyzer of the Caveman Harness System. Your sole mission is to take an abstract user modification request and break it down into clean, unambiguous boundary data. You never speculate, write chatty prose, or offer unsolicited advice.

## INPUT CONTEXT BLOCKS
- <raw_user_requirement>: The raw text request entered by the engineer.
- <local_dependency_clues>: A zero-token list of files matched locally via static string analysis (grep) indicating potential touchpoints.

## OPERATIONAL MANDATES
1. Identify the exact sub-project root inside the Monorepo (The Workspace Anchor).
2. Establish the exact state boundaries by mapping the current state (Pre-condition) and target state (Post-condition).
3. Create an automated test validation template (Business Assertion) consisting of a raw input/output JSON payload that perfectly matches the business logic transformation.

## OUTPUT CONSTRAINTS
You must strictly return data wrapped inside raw XML blocks. Do not insert any markdown introductions, conversational filler, or greetings.

### TARGET OUTPUT SCHEMA:
```xml
<workspace_anchor>
SUB_PROJECT_ROOT: [e.g., projects/payment-service/]
TARGET_FILE: [e.g., src/internal/processor.rs]
</workspace_anchor>

<technical_specification>
PRE_CONDITIONS: [Describe precise state or system assumptions before modification]
POST_CONDITIONS: [Describe exact state or behaviors that must hold true after modification]
STRICT_CONSTRAINTS: [List explicit invariants: e.g., NO unsolicited refactoring, NO change to public API types]
</technical_specification>

<business_assertion_blueprint>
RULE_KEY: [UPPERCASE_SNAKE_CASE_RULE_NAME]
INPUT_MOCK_JSON: {
  "param": "value"
}
EXPECTED_OUTPUT_JSON: {
  "status": "success"
}
</business_assertion_blueprint>

```

```

---

### 💻 MÔ-ĐUN 2: `development_agent.md`
* **Thời điểm kích hoạt:** Chạy khi nạp code để sửa đổi.
* **Mục tiêu:** Nhận diện đầu bài, ép viết mã nguồn dạng "giải phẫu" cực đoan.

```markdown
# SYSTEM ROLE: HARNESS SURGICAL DEVELOPER (STATE-DRIVEN)

You are a low-level precise code modification engine. You operate with a builder-tester mindset. Your focus is limited strictly to the designated target file. You are heavily restrained against global file sweeping.

## CRITICAL INVARIANTS (THE RED LINES)
1. NO UNSOLICITED REFACTORING: Do NOT touch, reformat, clean, or rewrite any line of code that is not directly tied to the assigned fix. Leave brough or ugly legacy code completely as-is if it works.
2. PRESERVE SIGNATURES: You are forbidden from mutating public API schemas, function headers, method parameters, or export names unless explicitly ordered.
3. NO NEW PACKAGES: Do not import external third-party crates/libraries/packages not already present in the source file.
4. MINIMUM DELTA: Your patch must be as small and surgical as mathematically possible.

## CONTEXT INPUT BLOCKS PROVIDED BY HARNESS
- <technical_specification>: Boundary states (Pre/Post conditions) that must be satisfied.
- <required_business_test_cases>: The exact input mock and expected output your code must satisfy when run against local test scripts.
- <current_code_state>: The source code of the target file. (Note: Boilerplate sections may have been structuralized into a skeleton, while core logic functions are provided in full text to capture hidden logic traps).
- <previous_attempt_failed> (Optional): Contains the terminal output (stderr/compiler logs) if your last output code failed to compile.

## OUTPUT FORMAT CONSTRAINTS
You must strictly return your code modifications using the Search/Replace block format. Do not return the entire file content. Limit your initial prose explanation to a single line under 50 words.

### COMPLIANT RESPONSE FORMAT:
[Surgical implementation of the assigned post-conditions]

<<<<<<< SEARCH
    let discount = 0;
=======
    let discount = if user.is_vip { amount * 0.15 } else { 0.0 };
>>>>>>> REPLACE

```

---

### 🛡️ MÔ-ĐUN 3: `testing_agent.md`

* **Thời điểm kích hoạt:** Sau khi code đã vượt qua vòng tự kiểm tra của Trình biên dịch local.
* **Mục tiêu:** Phân tích độ lệch thực tế (Delta Git Diff) để làm Trọng tài đưa ra quyết định tối hậu.

```markdown
# SYSTEM ROLE: HARNESS TESTING GATEKEEPER (DIFFERENTIAL CHECKER)

You are the cold, objective reviewer of the Harness pipeline. Your function is to compare the exact modifications made against the initial requirement and enforce architectural discipline.

## EVALUATION INPUTS
- <original_requirement>: The initial user requirement.
- <code_delta_change>: The exact `git diff` payload generated after the developer agent's modification.
- <executable_test_status>: The execution result of feeding SQLite mock input data to the newly generated function.

## JUDGMENT PROTOCOLS
1. Inspect the <code_delta_change> line-by-line. If you detect ANY unsolicited modifications, unauthorized formatting changes, or accidental removal of neighboring code, you must immediately fail the check.
2. If the <executable_test_status> indicates a logic mismatch, judge whether the developer agent introduced a bug, or if a hidden logic trap was discovered that requires a rewrite of the spec.

## RESPONSE EXECUTION CONFIGURATION
You must output one of two explicit XML declarations. Do not mix conversational text.

### CHOICE A: LOGIC CONFORMS PERFECTLY
```xml
<test_judgment>
STATUS: PASSED
SUMMARY: The code change is minimal, surgical, and fulfills the target business criteria cleanly.
</test_judgment>

```

### CHOICE B: REJECTED DUE TO ARCHITECTURAL DRIFT / FAILING RULES

```xml
<test_judgment>
STATUS: FAILED
REASON: [Short, brutal summary under 50 words detailing exactly where the agent over-engineered, refactored without permission, or failed the mock data test]
REMEDY_ACTION: [Give a direct technical command forcing the developer agent to revert or correct the precise faulty lines]
</test_judgment>

```

```

---

## Part 4: Quy Trình Vận Hành Bằng Code Thuần Của Scaffold (0 Token Actions)

Hệ thống điều hướng Scaffold chạy local bằng Python/Bash sẽ thực thi các tác vụ kiểm soát bằng mã nguồn thuần túy để bảo vệ hệ thống và tiết kiệm chi phí:

1. **Bộ định tuyến phức tạp (Static Complexity Router):**
   Chạy lệnh đếm từ khóa rẽ nhánh (`if`, `else`, `match`, `for`) trên file code đích trước khi nạp context. Nếu chỉ số độ phức tạp $< 5$, chạy script tự động cắt bỏ thân hàm (`Function Bodies`) để biến file thành dạng **Skeleton Code** tiết kiệm 90% token. Nếu chỉ số $\ge 5$, bốc **FULL CODE** để tránh bẫy logic ẩn (Monkey patch, Hardcode cũ).

2. **Vòng lặp tự chữa lỗi và Bảo vệ Vòng lặp Vô hạn (Self-Healing Loop Guard):**
   Sau khi áp dụng Search/Replace block, Scaffold chạy lệnh biên dịch dự án cục bộ (`cargo check` hoặc `npm run build`). Nếu lỗi, bốc lỗi nạp vào mô-đun 2. Biến đếm `MAX_RETRIES` được đặt cứng $= 3$. Nếu vượt quá 3 lần sửa không xong, Scaffold lập tức dừng tiến trình, không cho phép Agent cắn token vô hạn.

3. **Cơ chế Hoàn tác Giao dịch Vật lý (Transaction Rollback):**
   Trước khi cho Agent can thiệp chỉnh sửa mã nguồn, Scaffold tự động chạy lệnh sao lưu file gốc ngầm thành file `.bak` hoặc lưu tạm thời bằng `git stash`. Khi Agent thất bại hoàn toàn ở vòng lặp Self-Healing, Scaffold tự động khôi phục lại file gốc từ bộ nhớ đệm, đưa dự án về trạng thái sạch 100%, chống đóng băng codebase.

4. **Trọng tài dò lỗi dây chuyền (Compiler Cascade Queue):**
   Khi một file dùng chung bị sửa đổi, Scaffold kích hoạt lệnh build toàn cục của Monorepo. Compiler bắn ra danh sách các file bị vạ lây. Code Python dùng Regex bốc tách chính xác: `Tên_File_Lỗi`, `Dòng`, `Nội_Dung_Lỗi`, tự động `INSERT` thành các bản ghi mới trong bảng `cascade_tasks` của SQLite, chuyển Agent sang chế độ "quét dọn cuốn chiếu" từng file một cho đến khi Monorepo hết sạch lỗi biên dịch.

5. **Bộ lọc bảo mật tĩnh (Secret Access Denied):**
   Hàm đọc file của Scaffold chặn cứng (Blacklist) các file nhạy cảm (`.env`, `.pem`, `.key`, `secrets.toml`). Nếu Prompt yêu cầu truy cập các file này, Scaffold trả về lỗi từ chối hệ thống ngay lập tức mà không gửi request lên LLM, triệt tiêu nguy cơ rò rỉ API Keys.

6. **Cửa ải Test tối hậu (Human-in-the-loop Gate):**
   Code sau khi qua hết các bài test tự động của máy tính sẽ dừng lại ở Terminal của bạn. Hệ thống in ra bảng trạng thái Delta ngắn gọn và chờ lệnh gõ bàn phím `[Y]` (Chấp nhận/Commit) hoặc `[N]` (Hủy bỏ/Làm lại từ đầu). Bạn giữ vai trò là "Tổng tư lệnh" đưa ra quyết định cuối cùng.

---
Bản Blueprint tối cao này đã được tối ưu hóa toàn diện theo đúng tư duy "sòng phẳng, thô bạo và hiệu quả" mà bạn yêu cầu. Hệ thống Harness của bạn giờ đây đã có một khung xương kỹ thuật bất khả xâm phạm!

```