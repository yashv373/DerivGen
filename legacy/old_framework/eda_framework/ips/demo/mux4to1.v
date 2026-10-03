module mux4to1(
    input  wire in0,
    input  wire in1,
    input  wire in2,
    input  wire in3,
    input  wire [1:0] sel,
    output reg  y
);
    always @(*) begin
        case(sel)
            2'b00: y = in0;
            2'b01: y = in1;
            2'b10: y = in2;
            2'b11: y = in3;
        endcase
    end
endmodule
