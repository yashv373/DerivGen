module Threshold_Check_IP(
    input wire clk_fast, input wire rst,
    input wire [31:0] formatted_data,
    output reg threshold_alert
);
    // Hardcoded threshold of 0x000F_0000 for the sensor
    always @(posedge clk_fast) begin
        if (rst) threshold_alert <= 1'b0;
        else if (formatted_data > 32'h000F0000) threshold_alert <= 1'b1;
        else threshold_alert <= 1'b0;
    end
endmodule
