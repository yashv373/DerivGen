/* Machine-generated using Migen */
module test4_derivative_5ip(
	input sys_clk,
	input sys_rst,
	output ip_uart_tx,
	output ip_uart_irq,
	output [7:0] ip_gpio_gpio_out,
	output ip_gpio_irq,
	output ip_spi_mosi,
	output ip_spi_sclk_o,
	output ip_spi_cs_n,
	output ip_i2c_sda_out,
	output ip_i2c_scl_out,
	output ip_timer_timer_irq
);

wire ip_uart_rx;
wire [7:0] ip_gpio_gpio_in;
wire ip_spi_miso;
wire ip_i2c_sda_in;
wire [15:0] ip_timer_prescale;

// synthesis translate_off
reg dummy_s;
initial dummy_s <= 1'd0;
// synthesis translate_on

assign ip_uart_rx = 1'd1;
assign ip_gpio_gpio_in = 1'd0;
assign ip_spi_miso = 1'd1;
assign ip_i2c_sda_in = 1'd1;
assign ip_timer_prescale = 7'd100;

ip_uart ip_uart(
	.clk(sys_clk),
	.rst(sys_rst),
	.rx(ip_uart_rx),
	.irq(ip_uart_irq),
	.tx(ip_uart_tx)
);

ip_gpio ip_gpio(
	.clk(sys_clk),
	.gpio_in(ip_gpio_gpio_in),
	.rst(sys_rst),
	.gpio_out(ip_gpio_gpio_out),
	.irq(ip_gpio_irq)
);

ip_spi ip_spi(
	.clk(sys_clk),
	.miso(ip_spi_miso),
	.rst(sys_rst),
	.cs_n(ip_spi_cs_n),
	.mosi(ip_spi_mosi),
	.sclk_o(ip_spi_sclk_o)
);

ip_i2c ip_i2c(
	.clk(sys_clk),
	.rst(sys_rst),
	.sda_in(ip_i2c_sda_in),
	.scl_out(ip_i2c_scl_out),
	.sda_out(ip_i2c_sda_out)
);

ip_timer ip_timer(
	.clk(sys_clk),
	.prescale(ip_timer_prescale),
	.rst(sys_rst),
	.timer_irq(ip_timer_timer_irq)
);

endmodule
