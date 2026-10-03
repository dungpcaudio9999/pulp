# PULP execution-flow demo

`flow_demo.c` is a phase-oriented program built once and run unchanged on the
GVSoC `pulp-open` virtual platform and the PULP RTL Questa testbench.

It exercises:

1. FC execution, stdout and L2 data;
2. the FC timer and a short ALU loop;
3. cluster power-up and hand-off;
4. eight cores writing interleaved L1/TCDM slots;
5. event-unit barriers and cross-core reads;
6. MCHAN DMA from L2 to L1 and back;
7. cluster completion and return to the FC.

Every phase is a `noinline` function and emits `FLOW|...` markers. The same
boundaries therefore appear in application output, GVSoC traces, RTL traces,
and the generated HTML viewer.

## Build the single ELF

```bash
cd /home/dungpc/ndmoney4porche/projects/pulp
export PATH=$(printf '%s' "$PATH" | tr ':' '\n' | grep -v miniforge3 | paste -sd:)
export PULP_RISCV_GCC_TOOLCHAIN=/opt/pulp-toolchain
source pulp-runtime/configs/pulp.sh
export PULP_PROJECT_HOME=$PWD PULP_SDK_HOME=$PWD/pulp-runtime
make -C sw/flow_demo clean all
sha256sum sw/flow_demo/build/flow_demo/flow_demo
```

## Run GVSoC

```bash
source sw/gvsoc/env.sh
mkdir -p report/gvsoc_demo/gvsoc
gvsoc --target=pulp-open \
  --work-dir="$PWD/report/gvsoc_demo/gvsoc" \
  --binary="$PWD/sw/flow_demo/build/flow_demo/flow_demo" \
  --trace=chip/soc/fc/insn:fc.log \
  --trace=chip/cluster/pe0/insn:pe0.log run \
  2>&1 | tee report/gvsoc_demo/gvsoc.log
```

## Run the same ELF on RTL

Use a separate terminal from the GVSoC environment:

```bash
cd /home/dungpc/ndmoney4porche/projects/pulp
APP_DIR="$PWD/sw/flow_demo" \
SIM_TIMEOUT="80 ms" WALL_TIMEOUT=3600 \
PULP_RISCV_GCC_TOOLCHAIN=/opt/pulp-toolchain \
sw/full_system/run_sim.sh all run
```

Questa writes `trace_core_1f_0.log` for the FC and
`trace_core_00_0.log` ... `trace_core_00_7.log` for the cluster cores into
`sw/flow_demo/build/`.

## Generate the viewer

```bash
/usr/bin/python3 sw/flow_demo/flow_visualize.py \
  --elf sw/flow_demo/build/flow_demo/flow_demo \
  --gvsoc-fc report/gvsoc_demo/gvsoc/fc.log \
  --gvsoc-pe0 report/gvsoc_demo/gvsoc/pe0.log \
  --gvsoc-log report/gvsoc_demo/gvsoc.log \
  --rtl-dir report/gvsoc_demo/rtl/raw \
  --rtl-log report/gvsoc_demo/rtl/transcript.log \
  --addr2line /opt/pulp-toolchain/bin/riscv32-unknown-elf-addr2line \
  --output report/gvsoc_demo/flow_viewer.html
```

Open `report/gvsoc_demo/flow_viewer.html` in a browser. For the selected RTL
waveform:

```bash
cd report/gvsoc_demo/rtl/wave
gtkwave flow_demo.vcd.gz
```

The viewer deliberately omits the tens of thousands of repeated instructions
inside `cluster_wait`; the full raw logs remain available. The phase-2 span and
the delta at the first instruction after return still expose the wait time.
