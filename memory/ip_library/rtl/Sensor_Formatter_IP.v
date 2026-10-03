// Sensor_Formatter_IP -- registers a raw sensor word and scales it.

module Sensor_Formatter_IP (
    input  wire        clk,
    input  wire        rst_n,
    input  wire [31:0] data_in,
    output reg  [31:0] data_out
);

    always @(posedge clk) begin
        if (!rst_n)
            data_out <= 32'd0;
        else
            data_out <= data_in << 1;   // stand-in for real scaling
    end

endmodule
