# platform: derivsense_no_uart
#
# GOLDEN -- hand-written from derivsense.tcl, not generated.
#
# uart_tx0 is gone, along with its clock, reset, bus connection, address and
# the uart_tx pin it drove.
#
# The interesting part: fabric port m2 now answers to nobody, so its three
# response inputs need holding, the same way the spare m3 port already is.
# pready must be 1'b1, not zero -- a slave that never signals ready would
# hang the bus. That value is copied from what the parent does on m3.

# --- top-level pins ---
add_port  clk               in   1
add_port  rst_n             in   1
add_port  sensor_data_in    in   64
add_port  intr_threshold    out  1
add_port  err_lockstep      out  1
add_port  err_parity        out  1

# --- top-level buses ---
add_port_bus  host_apb  apb  slave

# --- instances ---
add_instance  bus_fabric0    Bus_Fabric_IP
add_instance  sram_ctrl0     SRAM_Ctrl_IP
add_instance  sram_macro0    SRAM_Macro_IP
add_instance  reg_bank0      RegBank_IP
add_instance  sensor_fmt_0   Sensor_Formatter_IP
add_instance  sensor_fmt_1   Sensor_Formatter_IP
add_instance  thresh_chk_0   Threshold_Check_IP
add_instance  thresh_chk_1   Threshold_Check_IP
add_instance  data_agg0      Data_Aggregator_IP
add_instance  core_fsm0      Core_FSM_IP
add_instance  shadow_fsm0    Shadow_FSM_IP
add_instance  lockstep_cmp0  Lockstep_Comparator_IP
add_instance  parity_gen0    Parity_Gen_IP
add_instance  parity_chk0    Parity_Check_IP

# --- bus connections ---
connect_bus  host_apb             bus_fabric0/s_apb
connect_bus  bus_fabric0/m0_apb   sram_ctrl0/apb
connect_bus  bus_fabric0/m1_apb   reg_bank0/apb

# --- address map ---
set_address  sram_ctrl0/apb       0x20000000  0x1000
set_address  reg_bank0/apb        0x20001000  0x1000

# --- clocks and resets ---
connect  clk    sram_macro0/clk
connect  clk    reg_bank0/clk
connect  clk    sensor_fmt_0/clk
connect  clk    sensor_fmt_1/clk
connect  clk    thresh_chk_0/clk
connect  clk    thresh_chk_1/clk
connect  clk    data_agg0/clk
connect  clk    core_fsm0/clk
connect  clk    shadow_fsm0/clk

connect  rst_n  reg_bank0/rst_n
connect  rst_n  sensor_fmt_0/rst_n
connect  rst_n  sensor_fmt_1/rst_n
connect  rst_n  thresh_chk_0/rst_n
connect  rst_n  thresh_chk_1/rst_n
connect  rst_n  data_agg0/rst_n
connect  rst_n  core_fsm0/rst_n
connect  rst_n  shadow_fsm0/rst_n

# --- memory data path ---
connect  sram_ctrl0/sram_we    sram_macro0/we
connect  sram_ctrl0/sram_addr  sram_macro0/addr
connect  sram_ctrl0/sram_din   sram_macro0/din
connect  sram_macro0/dout      sram_ctrl0/sram_dout

# --- sensor path ---
connect  sensor_data_in[31:0]   sensor_fmt_0/data_in
connect  sensor_data_in[63:32]  sensor_fmt_1/data_in
connect  sensor_fmt_0/data_out  thresh_chk_0/data_in
connect  sensor_fmt_1/data_out  thresh_chk_1/data_in
connect  thresh_chk_0/alert     data_agg0/alert_bus[0]
connect  thresh_chk_1/alert     data_agg0/alert_bus[1]
connect  data_agg0/intr         intr_threshold

# --- control ---
connect  sensor_fmt_0/data_out  core_fsm0/data_in

# --- safety: lockstep ---
connect  sensor_fmt_0/data_out  shadow_fsm0/data_in
connect  core_fsm0/state        lockstep_cmp0/state_a
connect  shadow_fsm0/state      lockstep_cmp0/state_b
connect  lockstep_cmp0/err      err_lockstep

# --- safety: memory parity ---
connect  sram_ctrl0/sram_din    parity_gen0/data_in
connect  sram_macro0/dout       parity_chk0/data_in
connect  parity_gen0/parity     parity_chk0/parity
connect  parity_chk0/err        err_parity

# --- tie-offs ---
tie  data_agg0/alert_bus[31:2]  30'b0

# m2 lost its peripheral, m3 never had one.
tie  bus_fabric0/m2_apb_prdata   32'b0
tie  bus_fabric0/m2_apb_pready   1'b1
tie  bus_fabric0/m2_apb_pslverr  1'b0

tie  bus_fabric0/m3_apb_prdata   32'b0
tie  bus_fabric0/m3_apb_pready   1'b1
tie  bus_fabric0/m3_apb_pslverr  1'b0
