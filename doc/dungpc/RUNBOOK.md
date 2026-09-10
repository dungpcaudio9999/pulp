# Runbook — chạy `sw/full_system` từ máy trắng đến kết quả

Mục tiêu: từ một máy chưa có gì đến dòng `==== FULL-SYSTEM SUMMARY: SUCCESS`.

Đây là file **thao tác**. Vì sao mỗi bước lại như vậy thì xem:

| Cần hiểu | Đọc |
|---|---|
| chương trình test làm gì, 9 phase | [sw/full_system/README.md](../../sw/full_system/README.md) |
| quá trình dựng môi trường và gỡ lỗi | [nhat-ky-mo-phong-pulp-questasim.md](nhat-ky-mo-phong-pulp-questasim.md) |
| vì sao QuestaSim chứ không Vivado XSim | [lua-chon-simulator.md](lua-chon-simulator.md) |
| kết quả và bằng chứng | [BAO-CAO-TONG-KET.md](BAO-CAO-TONG-KET.md) |

Thời gian tham khảo: bước 1–3 khoảng 30–60 phút (phần lớn là compile RTL), mỗi lượt
chạy mô phỏng khoảng 10–20 phút thời gian thực.

---

## 0. Điều kiện cần

| Công cụ | Phiên bản đã kiểm chứng | Ghi chú |
|---|---|---|
| QuestaSim | `10.7c` (2018.08) | cần license và `lmgrd` chạy được |
| PULP RISC-V GCC | `v1.0.16`, bản **Ubuntu 16** | GCC RISC-V generic **không** đủ |
| Bender | `0.31.0` | script `./bender` trong repo tự tải |
| Python | `/usr/bin/python3` 3.12 | cần `pyelftools` và `numpy` |
| Linux | kernel 7.0.0-30-generic | |

Cài hai gói Python vào **python hệ thống**, không phải conda:

```bash
/usr/bin/python3 -m pip install pyelftools numpy
```

Lý do: `make run` gọi `stim_utils.py` và `slm_hyper.py` bằng `/usr/bin/python3`. Nếu
conda che mất, lỗi hiện ra là `ModuleNotFoundError: No module named 'elftools'` ở giữa
lượt chạy. [run_sim.sh](../../sw/full_system/run_sim.sh) tự rời conda khỏi `PATH`, nhưng
gói vẫn phải có sẵn.

---

## 1. Lấy mã nguồn và dependency

```bash
git clone <fork-url> pulp && cd pulp
git checkout feature/dungpc-work

./bender checkout        # tải dependency về .bender/
./patch-deps             # BẮT BUỘC, xem bên dưới
make scripts             # sinh sim/compile.tcl và fpga/pulp/tcl/generated/compile.tcl

make pulp-runtime        # clone pulp-runtime v0.0.15
sed -i 's|"rU"|"r"|' pulp-runtime/bin/slm_hyper.py
```

### Đừng dùng `make checkout`

Target đó chạy `./bender checkout` rồi **thẳng** sang `make scripts`
([Makefile:40-48](../../Makefile#L40-L48)), không có chỗ chèn `patch-deps`. Trên checkout
sạch nó sẽ gãy ở `make scripts` với `[E31] File ... doesn't exist`.

`patch-deps` sửa hai lỗi trong `Bender.yml` của dependency upstream: `clk_div.s` thiếu
chữ `v` trong `common_cells`, và dấu phẩy thừa sau `adbg_axi_biu.sv` trong `adv_dbg_if`.
Bender 0.25.x bỏ qua, 0.31.0 báo lỗi và dừng. `.bender/` bị gitignore và sinh lại sau mỗi
lần checkout nên patch **không commit được** — phải chạy lại script mỗi lần.

### Vì sao phải sửa `slm_hyper.py`

Chế độ `open(..., "rU")` đã bị **xoá** khỏi Python 3.11. `pulp-runtime` là repo clone
riêng, bị gitignore ở repo cha, nên bản vá này không đi theo `git pull` — clone mới là
lại hỏng. Nó chỉ gãy ở bước sinh stimuli của `make run`, tức là sau khi đã compile xong
mọi thứ.

`./update-regression-tests` **không cần** cho `full_system`. Chỉ chạy nếu muốn dùng các
bài regression upstream như `hello`.

---

## 2. Build RTL

```bash
source setup/vsim.sh
ulimit -n 4096

cd sim
make clean       # xoá cả work/ lẫn librbs.so (qua clean-deps)
vmap -c          # tạo modelsim.ini — PHẢI đứng sau 'clean'
make lib
make build       # build librbs.so rồi vlog toàn bộ RTL
make opt         # vopt -> sim/work/vopt_tb
cd ..
```

Kỳ vọng: `make build` 0 error; `make opt` 0 error, 23 warning, và tạo ra `sim/work/vopt_tb`.

### Đừng dùng `make build` ở gốc trên checkout sạch

Nó gọi `make -C sim all` = `clean lib build opt` ([sim/Makefile:14](../../sim/Makefile#L14)).
Nhưng `clean` kết thúc bằng `rm modelsim.ini`, còn `lib` ngay sau đó mở đầu bằng
`chmod +w modelsim.ini` trên file vừa bị xoá — hỏng. Trình tự thủ công ở trên chèn
`vmap -c` vào đúng khe hở đó.

Từ lần build thứ hai trở đi, khi `modelsim.ini` đã tồn tại, `make build` ở gốc dùng được
bình thường.

---

## 3. Thư viện DPI cho JTAG — không phải bước riêng

`make build` ở bước 2 **tự lo** thư viện này: target `build-deps`
([sim/Makefile:17-18](../../sim/Makefile#L17-L18)) gọi `make -C ../rtl/tb/remote_bitbang all`
trước khi vlog. Cũng vì thế `make clean` xoá luôn `librbs.so` qua `clean-deps`.

`librbs.so` hiện thực giao thức remote-bitbang mà testbench dùng để nạp chương trình qua
JTAG. Thiếu nó thì `-gLOAD_L2=JTAG` không nạp được gì.

Muốn build lại riêng nó:

```bash
make -C rtl/tb/remote_bitbang clean
make -C rtl/tb/remote_bitbang all
ls -l rtl/tb/remote_bitbang/librbs.so
```

### `-fcommon` nay nằm trong Makefile, không truyền qua dòng lệnh

`remote_bitbang.h` định nghĩa biến toàn cục ngay trong header — `tck`, `tms`, `tdi`,
`rbs_err`, `recv_buf`… — và cả `remote_bitbang.c` lẫn `sim_jtag.c` đều include nó. GCC 10
trở đi mặc định `-fno-common` nên link báo `multiple definition of 'recv_end'` và mười
dòng tương tự.

Cách cũ là truyền `CFLAGS="-Wall -O2 -g -fcommon"` trên dòng lệnh. Cách đó **chỉ cứu được
lần build thủ công**: `build-deps` gọi sang không kèm `CFLAGS` nào, nên `cd sim && make build`
vẫn gãy, và vì `build-deps` gãy thì RTL không được vlog, `make opt` sau đó báo
`(vopt-13130) Failed to find design unit tb_pulp` — một triệu chứng trông chẳng liên quan gì
tới C.

Cờ này nay đã nằm trong [rtl/tb/remote_bitbang/Makefile](../../rtl/tb/remote_bitbang/Makefile),
nên không cần truyền gì thêm.

---

## 4. Chạy

```bash
cd sw/full_system
./run_sim.sh
```

Không cần export biến môi trường nào. [run_sim.sh](../../sw/full_system/run_sim.sh) tự lo:
rời conda, dò toolchain, khởi động `lmgrd` nếu chưa chạy, `source setup/vsim.sh` **và**
`pulp-runtime/configs/pulp.sh`, đặt `vsim_flags` kèm `-gUSE_HWPE_CL=1`, rồi bọc watchdog.

Trước khi làm gì, script chạy preflight và **báo hết một lượt** những thứ còn thiếu thay
vì chết giữa chừng ở chỗ khó đoán.

### Các dạng gọi

| Lệnh | Tác dụng |
|---|---|
| `./run_sim.sh` | `clean all run` — lượt sạch, kỳ vọng SUCCESS |
| `./run_sim.sh all` | chỉ build ELF, không mô phỏng |
| `./run_sim.sh clean all run INJECT_FAULT=1` | phép thử ngược core 3 |
| `./run_sim.sh clean all run INJECT_FAULT_DMA=1` | phép thử ngược phase 6 |
| `SIM_TIMEOUT="5 ms" ./run_sim.sh` | ép watchdog nổ, kiểm chứng đường TIMEOUT |

### Biến ghi đè được

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `QUESTA_HOME` | `$HOME/questasim` | thư mục cài Questa |
| `PULP_RISCV_GCC_TOOLCHAIN` | tự dò | toolchain RISC-V |
| `SIM_TIMEOUT` | `40 ms` | watchdog **thời gian mô phỏng** |
| `WALL_TIMEOUT` | `1800` | watchdog **thời gian thực**, giây |

Hai watchdog vì tầng một không cứu được trường hợp vsim treo *trước* khi nạp do-file —
chờ license, mạng hỏng. Tầng hai giết cả process group nên vsim con không sống sót.

---

## 5. Đọc kết quả

Mã thoát của `run_sim.sh`:

| Mã | Nghĩa |
|---|---|
| `0` | PASS |
| `1` | lỗi dữ liệu — có phase FAIL |
| `124` | treo, watchdog nổ |

Lượt sạch phải đủ **cả bốn**:

1. đủ 9 dòng `[PHASE n] ... OK`
2. log có `[STDOUT-CL0_PE0]` đến `CL0_PE7` — bằng chứng cluster thật sự sống
3. `==== FULL-SYSTEM SUMMARY: SUCCESS`
4. `[TB] ... Received status core: 0x00000000`

Điểm 2 không thừa: `cluster_start()` thất bại **trong im lặng** khi cấp phát stack L1
hỏng, và `cluster_wait()` khi đó trả về 0 — không phân biệt được với thành công. Đã có
lần chương trình này báo SUCCESS trong khi cluster chưa hề khởi động.

Nhiễu đã biết của Questa 10.7c, **không phải** hồi quy: bốn lỗi `vsim-191`, warning
`jtag_tick`, warning `vsim-8683` về port FLL chưa khởi tạo.

---

## 6. Phép thử ngược — phần bắt buộc của một lượt nghiệm thu

Một bài test chỉ báo PASS thì chưa chứng minh được gì. Hai phép dưới đây chứng minh nó
**bắt được lỗi thật**.

```bash
./run_sim.sh clean all run INJECT_FAULT=1        # phải FAIL, status 0x00000001
./run_sim.sh clean all run INJECT_FAULT_DMA=1    # phải FAIL tại word 254
```

- `INJECT_FAULT` phá dữ liệu của **core 3**. Nếu nó PASS thì cơ chế gom lỗi hỏng: runtime
  chỉ giữ giá trị trả về của core 0, lỗi do core 1–7 phát hiện bị nuốt mất.
- `INJECT_FAULT_DMA` cắt ngắn lượt DMA còn 2 word. DMA vẫn báo xong bình thường, chỉ dữ
  liệu là thiếu. Nếu nó PASS thì phase 6 chỉ đang đọc thanh ghi `MCHAN_STATUS` chứ không
  đối chiếu dữ liệu — một phép kiểm tra rỗng.

Dùng đúng hai biến này. **Đừng ghi đè `PULP_CFLAGS`** trên dòng lệnh: làm vậy xoá luôn các
define mà rule của runtime thêm bằng `+=`, và build hỏng với lỗi lạc hướng
`archi/chips/PULP_CHIP_STR/pulp.h: No such file`.

---

## 7. Thu waveform

Cần chạy `./run_sim.sh` trọn một lượt trước, vì stimuli (`build/vectors/stim.txt`) và các
symlink trong `build/` được sinh ra trong bước `run`.

```bash
cd /path/to/pulp
ROOT="$PWD"
source setup/vsim.sh
export SIM_TIMEOUT="40 ms"

cd sw/full_system/build
vsim -c -modelsimini "$ROOT/sim/modelsim.ini" vopt_tb \
    -L models_lib -L vip_lib -t ps \
    +nowarnTRAN +nowarnTSCALE +nowarnTFMPC \
    -sv_lib "$ROOT/rtl/tb/remote_bitbang/librbs" \
    -permit_unmatched_virtual_intf \
    +ENTRY_POINT=0x1c008080 "+VSIM_PATH=$ROOT/sim" \
    -do "$ROOT/sw/full_system/wave_capture.do" \
    -gBAUDRATE=115200 -gENABLE_DEV_DPI=0 -gLOAD_L2=JTAG -gUSE_HWPE_CL=1
```

Chạy từ `build/` để VCD rơi vào đó. Kết quả: `full_system.vcd.gz`, khoảng 4.6 MB nén,
16 tín hiệu, 18.27 ms. VCD **không commit** — tái tạo được và nằm trong `.gitignore`.

Do-file in ra các dòng `EVT|<thời điểm ns>|<nhãn>` mốc thời gian, `EXIT-STATUS|<hex>`, và
`WATCHDOG|...` nếu hết giờ. Phân tích của lần đo đã lưu ở
[report/waveform_20260906/](../../report/waveform_20260906/) — phát hiện chính là **70%
thời gian mô phỏng dành cho nạp chương trình qua JTAG**, không phải chạy nó.

Muốn rút ngắn vòng lặp debug thì đổi sang `-gLOAD_L2=STANDALONE`. Đánh đổi: không còn
kiểm chứng đường JTAG, nên giữ ít nhất một lượt `LOAD_L2=JTAG` để bảo chứng đường nạp.

---

## 8. Khi hỏng

| Triệu chứng | Nguyên nhân | Xử lý |
|---|---|---|
| `THIEU DIEU KIEN DE CHAY:` | preflight của `run_sim.sh` | làm theo đúng danh sách nó in ra |
| `[E31] File ... doesn't exist` khi `make scripts` | chưa chạy `./patch-deps` | bước 1 |
| `Fatal: Invalid license environment` | `lmgrd` chưa chạy | `run_sim.sh` tự khởi động; nếu vẫn hỏng, xem log `$QUESTA_HOME/license_server.log` |
| `cc1: libmpfr.so.4: cannot open shared object file` | thiếu `LD_LIBRARY_PATH` | toolchain Ubuntu 16 cần `compat-libs` đi kèm |
| `ModuleNotFoundError: No module named 'elftools'` | conda che python hệ thống | bước 0 |
| `ValueError: invalid mode: 'rU'` | `slm_hyper.py` chưa vá | bước 1 |
| `No rule to make target 'clean'` | chưa `source pulp-runtime/configs/pulp.sh` | dùng `run_sim.sh` thay vì gọi `make` tay |
| `multiple definition of 'recv_end'` khi build `librbs` | `-fcommon` bị mất khỏi `rtl/tb/remote_bitbang/Makefile` | bước 3 |
| `(vopt-13130) Failed to find design unit tb_pulp` | `make build` đã gãy ở `build-deps` nên RTL chưa hề được vlog | cuộn ngược log tìm lỗi thật, thường là `librbs` |
| `chmod: cannot access 'modelsim.ini'` | dùng `make build` ở gốc trên checkout sạch | bước 2 |
| vsim đứng im ở prompt, không PASS không FAIL | testbench không tới `$stop` | watchdog sẽ nổ; `exit_status` còn `-1` nghĩa là chưa chạy xong |
| SUCCESS nhưng log **không có** `CL0_PE0..PE7` | cluster không khởi động mà test vẫn báo pass | kiểm tra `CLUSTER_STACK_SIZE`; xem quyết định 2 trong README của test |
| phase 7 treo tới hết timeout | thiếu `-gUSE_HWPE_CL=1` hoặc chưa `DATAMOVER_CG_ENABLE()` | HWPE mặc định bị clock-gate và không được instantiate |

Ba lỗi im lặng nguy hiểm nhất — cluster không chạy mà báo pass, lỗi ở core khác 0 bị nuốt,
DMA báo xong nhưng thiếu dữ liệu — đều **không** hiện ra ở lượt chạy sạch. Chỉ phép thử
ngược ở mục 6 bắt được.

---

## 9. Ngoài phạm vi runbook này

| Việc | Trạng thái | Tài liệu |
|---|---|---|
| Build cho FPGA | `make clean all io=uart PLATFORM=fpga` — chỉ dùng được sau khi có bitstream | [sw/full_system/README.md](../../sw/full_system/README.md) |
| Port sang ZCU104 | chưa xong, có bảng khoảng trống | [zcu102-to-zcu104-gap.md](zcu102-to-zcu104-gap.md) |
| Chạy bằng Vivado XSim | bị chặn bởi lỗi XSIM 43-4177, không phải flow chính | [lua-chon-simulator.md](lua-chon-simulator.md), `sim/xsim/run_full_system_xsim.tcl` |
