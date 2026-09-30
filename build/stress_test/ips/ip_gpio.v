module ip_gpio(
    input wire clk,
    input wire rst,
    input wire [7:0] gpio_in,
    output wire [7:0] gpio_out,
    output wire irq
);
    assign gpio_out = 8'd0;
    assign irq = 1'b0;
endmodule
