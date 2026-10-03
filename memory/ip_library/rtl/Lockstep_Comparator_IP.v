// Lockstep_Comparator_IP -- flags a mismatch between the two FSMs.

module Lockstep_Comparator_IP (
    input  wire [31:0] state_a,
    input  wire [31:0] state_b,
    output wire        err
);

    assign err = (state_a != state_b);

endmodule
