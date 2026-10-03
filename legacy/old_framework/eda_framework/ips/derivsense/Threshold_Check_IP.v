module Threshold_Check_IP(input clk, input rst, input [31:0] din, output alert); assign alert = din[31]; endmodule
