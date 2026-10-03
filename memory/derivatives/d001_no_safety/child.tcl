# platform: derivsense_no_safety
#
# GOLDEN -- hand-written from derivsense.tcl, not generated.
#
# The safety group is gone: shadow_fsm0, lockstep_cmp0, parity_gen0,
# parity_chk0, every line that mentioned them, and the two error pins they
# were the only drivers of (err_lockstep, err_parity).
#
# core_fsm0 stays and still runs the control flow; its state output is simply
# no longer compared against anything.

# --- top-level pins ---
add_port  clk               in   1
add_port  rst_n             in   1
add_port  sensor_data_in    in   64
add_port  uart_tx           out  1
add_port  intr_threshold    out  1

# --- top-level buses ---
add_port_bus  host_apb  apb  slave

# --- instances ---
add_instance  bus_fabric0    Bus_Fabric_IP
add_instance  sram_ctrl0     SRAM_Ctrl_IP
add_instance  sram_macro0    SRAM_Macro_IP
add_instance  reg_bank0      RegBank_IP
add_instance  uart_tx0       UART_TX_IP
add_instance  sensor_fmt_0   Sensor_Formatter_IP
add_instance  sensor_fmt_1   Sensor_Formatter_IP
add_instance  thresh_chk_0   Threshold_Check_IP
add_instance  thresh_chk_1   Threshold_Check_IP
add_instance  data_agg0      Data_Aggregator_IP
add_instance  core_fsm0      Core_FSM_IP

# --- bus connections ---
connect_bus  host_apb             bus_fabric0/s_apb
connect_bus  bus_fabric0/m0_apb   sram_ctrl0/apb
connect_bus  bus_fabric0/m1_apb   reg_bank0/apb
connect_bus  bus_fabric0/m2_apb   uart_tx0/apb

# --- address map ---
set_address  sram_ctrl0/apb       0x20000000  0x1000
set_address  reg_bank0/apb        0x20001000  0x1000
set_address  uart_tx0/apb         0x20002000  0x1000

# --- clocks and resets ---
connect  clk    sram_macro0/clk
connect  clk    reg_bank0/clk
connect  clk    uart_tx0/clk
connect  clk    sensor_fmt_0/clk
connect  clk    sensor_fmt_1/clk
connect  clk    thresh_chk_0/clk
connect  clk    thresh_chk_1/clk
connect  clk    data_agg0/clk
connect  clk    core_fsm0/clk

connect  rst_n  reg_bank0/rst_n
connect  rst_n  uart_tx0/rst_n
connect  rst_n  sensor_fmt_0/rst_n
connect  rst_n  sensor_fmt_1/rst_n
connect  rst_n  thresh_chk_0/rst_n
connect  rst_n  thresh_chk_1/rst_n
connect  rst_n  data_agg0/rst_n
connect  rst_n  core_fsm0/rst_n

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
connect  uart_tx0/tx            uart_tx

# --- tie-offs ---
tie  data_agg0/alert_bus[31:2]  30'b0

tie  bus_fabric0/m3_apb_prdata   32'b0
tie  bus_fabric0/m3_apb_pready   1'b1
tie  bus_fabric0/m3_apb_pslverr  1'b0
