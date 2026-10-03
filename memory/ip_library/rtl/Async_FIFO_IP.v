module Async_FIFO_IP(
    input wire wclk, input wire rclk, input wire rst,
    input wire we, input wire re,
    input wire [31:0] din,
    output wire [31:0] dout,
    output wire full, output wire empty
);
    // Simplified behavioral async FIFO for simulation
    reg [31:0] mem [0:15];
    reg [3:0] wptr, rptr;
    assign empty = (wptr == rptr);
    assign full = ((wptr + 1) == rptr);
    assign dout = mem[rptr];
    always @(posedge wclk) if (we && !full) begin mem[wptr] <= din; wptr <= wptr + 1; end
    always @(posedge rclk) if (rst) rptr <= 0; else if (re && !empty) rptr <= rptr + 1;
endmodule
