# Add simulation models omitted by the Vivado Bender backend.
set EXTRA_SIM_SOURCES [list \
    "$ROOT/.bender/git/checkouts/tech_cells_generic-6a4b27e0e56cbcda/src/deprecated/generic_rom.sv" \
    "$ROOT/.bender/git/checkouts/pulp_soc-c519334bd3ac5582/rtl/components/freq_meter.sv" \
    "$ROOT/.bender/git/checkouts/generic_fll-5f6d72bdaf06f326/fe/model/gf22_FLL_model.vhd" \
]

# Stop immediately if an expected model is missing.
foreach src $EXTRA_SIM_SOURCES {
    if {![file exists $src]} {
        error "Missing XSim source file: $src"
    }
}

# Add the omitted models to the main Vivado source set.
add_files -norecurse -fileset sources_1 $EXTRA_SIM_SOURCES

# Force the correct language for SystemVerilog sources.
set_property file_type SystemVerilog \
    [get_files -of_objects [get_filesets sources_1] \
        [list "*generic_rom.sv" "*freq_meter.sv"]]

puts "XSIM-INFO: Added simulation-only ROM, frequency meter and FLL models."
