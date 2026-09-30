module ip_dma(
    input wire clk,
    input wire rst,
    input wire [31:0] src_addr,
    input wire [31:0] dst_addr,
    input wire [15:0] length,
    output wire busy,
    output wire done_irq
);
    assign busy = 1'b0;
    assign done_irq = 1'b0;
endmodule
