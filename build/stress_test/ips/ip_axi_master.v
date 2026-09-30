module ip_axi_master(
    input wire clk,
    input wire rst,
    input wire [255:0] rdata,
    input wire rvalid,
    input wire rready_in,
    output wire [255:0] wdata,
    output wire [31:0] wstrb,
    output wire [31:0] awaddr,
    output wire [31:0] araddr,
    output wire wvalid
);
    assign wdata = 256'd0;
    assign wstrb = 32'd0;
    assign awaddr = 32'd0;
    assign araddr = 32'd0;
    assign wvalid = 1'b0;
endmodule
