module Mux4to1_IP(input wire [1:0] sel, input wire [31:0] in0, input wire [31:0] in1, input wire [31:0] in2, input wire [31:0] in3, output reg [31:0] y);
    always @(*) case(sel) 2'd0: y=in0; 2'd1: y=in1; 2'd2: y=in2; 2'd3: y=in3; endcase
endmodule
