module Sensor_Formatter_IP(
    input wire clk_fast, input wire rst,
    input wire [31:0] raw_sensor_in,
    output reg [31:0] formatted_data
);
    // Applies a basic mask and shift to format raw data
    always @(posedge clk_fast) begin
        if (rst) formatted_data <= 32'd0;
        else formatted_data <= (raw_sensor_in & 32'h00FFFFFF) << 2;
    end
endmodule
