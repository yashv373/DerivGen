module Demux1to4_IP(input wire [1:0] sel, input wire [31:0] in0, output reg [31:0] out0, output reg [31:0] out1, output reg [31:0] out2, output reg [31:0] out3);
    always @(*) begin out0=0; out1=0; out2=0; out3=0; case(sel) 2'd0: out0=in0; 2'd1: out1=in0; 2'd2: out2=in0; 2'd3: out3=in0; endcase end
endmodule
