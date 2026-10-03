module Lockstep_Comparator_IP(input [31:0] a, input [31:0] b, output err); assign err = (a != b); endmodule
