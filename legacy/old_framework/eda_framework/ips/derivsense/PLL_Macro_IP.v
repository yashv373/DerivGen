module PLL_Macro_IP(input ref_clk, output clk_fast, output clk_slow); assign clk_fast=ref_clk; assign clk_slow=ref_clk; endmodule
