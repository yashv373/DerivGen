module Sync_FIFO_IP(
    input wire clk, input wire rst,
    input wire we, input wire re,
    input wire [31:0] din,
    output wire [31:0] dout,
    output wire full, output wire empty
);
    reg [31:0] mem [0:15];
    reg [3:0] wptr, rptr;
    reg [4:0] count;
    
    assign empty = (count == 0);
    assign full  = (count == 16);
    assign dout  = mem[rptr];
    
    always @(posedge clk) begin
        if (rst) begin
            wptr <= 0; rptr <= 0; count <= 0;
        end else begin
            if (we && !full) begin
                mem[wptr] <= din;
                wptr <= wptr + 1;
            end
            if (re && !empty) begin
                rptr <= rptr + 1;
            end
            if ((we && !full) && !(re && !empty)) count <= count + 1;
            else if (!(we && !full) && (re && !empty)) count <= count - 1;
        end
    end
endmodule
