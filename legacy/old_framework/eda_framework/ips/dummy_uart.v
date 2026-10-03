module dummy_uart(
    input wire clk,
    input wire rst,
    input wire rx,
    output wire tx,
    output wire irq
);
    assign tx = rx;
    assign irq = 1'b0;
endmodule
