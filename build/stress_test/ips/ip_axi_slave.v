module ip_axi_slave(
    input wire clk,
    input wire rst,
    input wire [255:0] wdata,
    input wire [31:0] wstrb,
    input wire [31:0] awaddr,
    input wire wvalid,
    output wire [255:0] rdata,
    output wire rvalid
);
    assign rdata = 256'd0;
    assign rvalid = 1'b0;
endmodule
