module ip_aes(
    input wire clk,
    input wire rst,
    input wire [127:0] key_in,
    input wire [127:0] data_in,
    output wire [127:0] data_out,
    output wire done
);
    assign data_out = 128'd0;
    assign done = 1'b0;
endmodule
