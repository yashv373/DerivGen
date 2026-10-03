// Parity_Check_IP -- recomputes parity and flags a mismatch.

module Parity_Check_IP (
    input  wire [31:0] data_in,
    input  wire        parity,
    output wire        err
);

    assign err = (^data_in) != parity;

endmodule
