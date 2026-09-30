module ip_timer(
    input wire clk,
    input wire rst,
    input wire [15:0] prescale,
    output wire timer_irq
);
    assign timer_irq = 1'b0;
endmodule
