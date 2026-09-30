module ip_spi(
    input wire clk,
    input wire rst,
    input wire miso,
    output wire mosi,
    output wire sclk_o,
    output wire cs_n
);
    assign mosi = 1'b0;
    assign sclk_o = 1'b0;
    assign cs_n = 1'b0;
endmodule
