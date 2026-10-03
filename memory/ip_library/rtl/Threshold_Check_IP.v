// Threshold_Check_IP -- raises alert when a sample exceeds a fixed limit.

module Threshold_Check_IP (
    input  wire        clk,
    input  wire        rst_n,
    input  wire [31:0] data_in,
    output reg         alert
);

    localparam [31:0] LIMIT = 32'd1000;

    always @(posedge clk) begin
        if (!rst_n)
            alert <= 1'b0;
        else
            alert <= (data_in > LIMIT);
    end

endmodule
