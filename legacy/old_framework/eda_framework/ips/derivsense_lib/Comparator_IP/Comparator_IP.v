module Comparator_IP(input wire [31:0] a, input wire [31:0] b, output wire eq, output wire gt);
    assign eq = (a == b); assign gt = (a > b);
endmodule
