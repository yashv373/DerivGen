module Clk_Mux_IP(input sel, input clk0, input clk1, output clk_out); assign clk_out = sel ? clk1 : clk0; endmodule
