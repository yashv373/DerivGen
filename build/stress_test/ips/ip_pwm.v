module ip_pwm(
    input wire clk,
    input wire rst,
    input wire [7:0] duty_cycle,
    output wire pwm_out
);
    assign pwm_out = 1'b0;
endmodule
