# platform: derivsense
#
# A small sensor-monitoring SoC used as the parent for derivative tests.
# 16 instances, 10 IP types. Hand-written -- this is the "verified parent"
# that every derivative starts from.
#
# Note on resets: the IPs disagree on polarity (some want rst_n active-low,
# the sensor/FSM blocks want rst active-high). A structural wrapper cannot
# invert a signal without inventing logic, so both pins are brought out.

# --- top-level pins ---
add_port  clk               in   1
add_port  rst_n             in   1
add_port  rst               in   1
add_port  sensor_data_in    in   64
add_port  uart_tx           out  1
add_port  intr_threshold    out  1
add_port  err_lockstep      out  1
add_port  err_parity        out  1

# --- top-level buses ---
add_port_bus  host_axi  axi4lite  slave

# --- instances ---
add_instance  axi_xbar0      AXI4_Lite_Fabric_IP
add_instance  apb_bridge0    APB_Bridge_IP
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
add_instance  shadow_fsm0    Shadow_FSM_IP
add_instance  lockstep_cmp0  Lockstep_Comparator_IP
add_instance  parity_gen0    Parity_Gen_IP
add_instance  parity_chk0    Parity_Check_IP

# --- bus connections ---
connect_bus  host_axi            axi_xbar0/s_axi
connect_bus  axi_xbar0/m0_axi    sram_ctrl0/s_axi
connect_bus  axi_xbar0/m1_axi    apb_bridge0/s_axi
connect_bus  apb_bridge0/m_apb   reg_bank0/apb
connect_bus  apb_bridge0/m_apb   uart_tx0/apb

# --- address map ---
set_address  sram_ctrl0/s_axi    0x20000000  0x1000
set_address  apb_bridge0/s_axi   0x40000000  0x2000
set_address  reg_bank0/apb       0x40000000  0x1000
set_address  uart_tx0/apb        0x40001000  0x1000

# --- clocks and resets ---
connect  clk    axi_xbar0/clk
connect  clk    apb_bridge0/clk
connect  clk    sram_ctrl0/clk
connect  clk    sram_macro0/clk
connect  clk    reg_bank0/clk
connect  clk    uart_tx0/clk_slow
connect  clk    sensor_fmt_0/clk_fast
connect  clk    sensor_fmt_1/clk_fast
connect  clk    thresh_chk_0/clk_fast
connect  clk    thresh_chk_1/clk_fast
connect  clk    data_agg0/clk_fast
connect  clk    core_fsm0/clk_fast
connect  clk    shadow_fsm0/clk_fast

connect  rst_n  axi_xbar0/rst_n
connect  rst_n  apb_bridge0/rst_n
connect  rst_n  sram_ctrl0/rst_n
connect  rst_n  reg_bank0/rst_n
connect  rst_n  uart_tx0/rst_n

connect  rst    sensor_fmt_0/rst
connect  rst    sensor_fmt_1/rst
connect  rst    thresh_chk_0/rst
connect  rst    thresh_chk_1/rst
connect  rst    data_agg0/rst
connect  rst    core_fsm0/rst
connect  rst    shadow_fsm0/rst

# --- memory data path ---
connect  sram_ctrl0/sram_we    sram_macro0/we
connect  sram_ctrl0/sram_addr  sram_macro0/addr
connect  sram_ctrl0/sram_din   sram_macro0/din
connect  sram_macro0/dout      sram_ctrl0/sram_dout

# --- sensor path ---
connect  sensor_data_in[31:0]            sensor_fmt_0/raw_sensor_in
connect  sensor_data_in[63:32]           sensor_fmt_1/raw_sensor_in
connect  sensor_fmt_0/formatted_data     thresh_chk_0/formatted_data
connect  sensor_fmt_1/formatted_data     thresh_chk_1/formatted_data
connect  thresh_chk_0/threshold_alert    data_agg0/alert_bus[0]
connect  thresh_chk_1/threshold_alert    data_agg0/alert_bus[1]
connect  data_agg0/aggregated_intr       intr_threshold

# --- control ---
connect  sensor_fmt_0/formatted_data     core_fsm0/sensor_data
connect  uart_tx0/tx                     uart_tx

# --- safety: lockstep ---
connect  sensor_fmt_0/formatted_data     shadow_fsm0/sensor_data
connect  core_fsm0/state_out             lockstep_cmp0/fsm_a
connect  shadow_fsm0/state_out           lockstep_cmp0/fsm_b
connect  lockstep_cmp0/err_lockstep      err_lockstep

# --- safety: memory parity ---
connect  sram_ctrl0/sram_din             parity_gen0/data_in
connect  sram_macro0/dout                parity_chk0/data_in
connect  parity_gen0/parity_bit          parity_chk0/parity_bit
connect  parity_chk0/parity_err          err_parity

# --- tie-offs ---
# Only 2 of the aggregator's 32 alert inputs are used in this platform.
tie  data_agg0/alert_bus[31:2]  30'b0
