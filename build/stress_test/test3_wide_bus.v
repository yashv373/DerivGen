/* Machine-generated using Migen */
module test3_wide_bus(
	input sys_clk,
	input sys_rst,
	output [31:0] ip_axi_master_araddr,
	output [255:0] ip_axi_slave_rdata
);

wire [255:0] ip_axi_master_rdata;
wire ip_axi_master_rvalid;
wire ip_axi_master_rready_in;
wire [255:0] ip_axi_master_wdata;
wire [31:0] ip_axi_master_wstrb;
wire [31:0] ip_axi_master_awaddr;
wire ip_axi_master_wvalid;
wire [255:0] ip_axi_slave_wdata;
wire [31:0] ip_axi_slave_wstrb;
wire [31:0] ip_axi_slave_awaddr;
wire ip_axi_slave_wvalid;
wire ip_axi_slave_rvalid;

// synthesis translate_off
reg dummy_s;
initial dummy_s <= 1'd0;
// synthesis translate_on

assign ip_axi_master_rready_in = 1'd1;
assign ip_axi_slave_wdata = ip_axi_master_wdata;
assign ip_axi_slave_wstrb = ip_axi_master_wstrb;
assign ip_axi_slave_awaddr = ip_axi_master_awaddr;
assign ip_axi_slave_wvalid = ip_axi_master_wvalid;
assign ip_axi_master_rdata = ip_axi_slave_rdata;
assign ip_axi_master_rvalid = ip_axi_slave_rvalid;

ip_axi_master ip_axi_master(
	.clk(sys_clk),
	.rdata(ip_axi_master_rdata),
	.rready_in(ip_axi_master_rready_in),
	.rst(sys_rst),
	.rvalid(ip_axi_master_rvalid),
	.araddr(ip_axi_master_araddr),
	.awaddr(ip_axi_master_awaddr),
	.wdata(ip_axi_master_wdata),
	.wstrb(ip_axi_master_wstrb),
	.wvalid(ip_axi_master_wvalid)
);

ip_axi_slave ip_axi_slave(
	.awaddr(ip_axi_slave_awaddr),
	.clk(sys_clk),
	.rst(sys_rst),
	.wdata(ip_axi_slave_wdata),
	.wstrb(ip_axi_slave_wstrb),
	.wvalid(ip_axi_slave_wvalid),
	.rdata(ip_axi_slave_rdata),
	.rvalid(ip_axi_slave_rvalid)
);

endmodule
