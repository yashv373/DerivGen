module Comparator_IP(
    input wire clk,
    input wire rst,
    input wire [31:0] din,
    output wire [31:0] dout
);
    assign dout = din ^ 32'hDEADBEEF; // Dummy logic
endmodule
