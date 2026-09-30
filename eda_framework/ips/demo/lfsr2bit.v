module lfsr2bit(
    input  wire       clk,
    input  wire       rst,
    output reg  [1:0] q
);
    // 2-bit LFSR: taps at bits 1 and 0 (XOR feedback)
    // Sequence: 01 -> 10 -> 11 -> 01 -> ...
    always @(posedge clk or posedge rst) begin
        if (rst)
            q <= 2'b01;  // Seed (non-zero)
        else begin
            q[0] <= q[1];
            q[1] <= q[0] ^ q[1];
        end
    end
endmodule
