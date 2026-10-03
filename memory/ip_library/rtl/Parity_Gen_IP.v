// Parity_Gen_IP -- even parity over a data word.

module Parity_Gen_IP (
    input  wire [31:0] data_in,
    output wire        parity
);

    assign parity = ^data_in;

endmodule
