module Lockstep_Comparator_IP(
    input wire [31:0] fsm_a, input wire [31:0] fsm_b,
    output wire err_lockstep
);
    // Pure combinational XOR check for safety mismatch
    assign err_lockstep = (fsm_a != fsm_b);
endmodule
