module ip_i2c(
    input wire clk,
    input wire rst,
    input wire sda_in,
    output wire sda_out,
    output wire scl_out
);
    assign sda_out = 1'b0;
    assign scl_out = 1'b0;
endmodule
