# platform: derivsense_extra_regbank

# --- top-level pins ---
add_port clk in 1
add_port err_lockstep out 1
add_port err_parity out 1
add_port intr_threshold out 1
add_port rst_n in 1
add_port sensor_data_in in 64
add_port uart_tx out 1

# --- top-level buses ---
add_port_bus host_apb apb slave

# --- instances ---
add_instance bus_fabric0 Bus_Fabric_IP
add_instance core_fsm0 Core_FSM_IP
add_instance data_agg0 Data_Aggregator_IP
add_instance lockstep_cmp0 Lockstep_Comparator_IP
add_instance parity_chk0 Parity_Check_IP
add_instance parity_gen0 Parity_Gen_IP
add_instance reg_bank0 RegBank_IP
add_instance reg_bank1 RegBank_IP
add_instance sensor_fmt_0 Sensor_Formatter_IP
add_instance sensor_fmt_1 Sensor_Formatter_IP
add_instance shadow_fsm0 Shadow_FSM_IP
add_instance sram_ctrl0 SRAM_Ctrl_IP
add_instance sram_macro0 SRAM_Macro_IP
add_instance thresh_chk_0 Threshold_Check_IP
add_instance thresh_chk_1 Threshold_Check_IP
add_instance uart_tx0 UART_TX_IP

# --- bus connections ---
connect_bus bus_fabric0/m0_apb sram_ctrl0/apb
connect_bus bus_fabric0/m1_apb reg_bank0/apb
connect_bus bus_fabric0/m2_apb uart_tx0/apb
connect_bus bus_fabric0/m3_apb reg_bank1/apb
connect_bus host_apb bus_fabric0/s_apb

# --- address map ---
set_address reg_bank0/apb 0x20001000 0x1000
set_address reg_bank1/apb 0x20003000 0x1000
set_address sram_ctrl0/apb 0x20000000 0x1000
set_address uart_tx0/apb 0x20002000 0x1000

# --- connections ---
connect clk core_fsm0/clk
connect clk data_agg0/clk
connect clk reg_bank0/clk
connect clk reg_bank1/clk
connect clk sensor_fmt_0/clk
connect clk sensor_fmt_1/clk
connect clk shadow_fsm0/clk
connect clk sram_macro0/clk
connect clk thresh_chk_0/clk
connect clk thresh_chk_1/clk
connect clk uart_tx0/clk
connect core_fsm0/state lockstep_cmp0/state_a
connect data_agg0/intr intr_threshold
connect lockstep_cmp0/err err_lockstep
connect parity_chk0/err err_parity
connect parity_gen0/parity parity_chk0/parity
connect rst_n core_fsm0/rst_n
connect rst_n data_agg0/rst_n
connect rst_n reg_bank0/rst_n
connect rst_n reg_bank1/rst_n
connect rst_n sensor_fmt_0/rst_n
connect rst_n sensor_fmt_1/rst_n
connect rst_n shadow_fsm0/rst_n
connect rst_n thresh_chk_0/rst_n
connect rst_n thresh_chk_1/rst_n
connect rst_n uart_tx0/rst_n
connect sensor_data_in[31:0] sensor_fmt_0/data_in
connect sensor_data_in[63:32] sensor_fmt_1/data_in
connect sensor_fmt_0/data_out core_fsm0/data_in
connect sensor_fmt_0/data_out shadow_fsm0/data_in
connect sensor_fmt_0/data_out thresh_chk_0/data_in
connect sensor_fmt_1/data_out thresh_chk_1/data_in
connect shadow_fsm0/state lockstep_cmp0/state_b
connect sram_ctrl0/sram_addr sram_macro0/addr
connect sram_ctrl0/sram_din parity_gen0/data_in
connect sram_ctrl0/sram_din sram_macro0/din
connect sram_ctrl0/sram_we sram_macro0/we
connect sram_macro0/dout parity_chk0/data_in
connect sram_macro0/dout sram_ctrl0/sram_dout
connect thresh_chk_0/alert data_agg0/alert_bus[0]
connect thresh_chk_1/alert data_agg0/alert_bus[1]
connect uart_tx0/tx uart_tx

# --- tie-offs ---
tie data_agg0/alert_bus[31:2] 30'b0
