import os
from migen import *
from migen.fhdl import verilog

from ml_generated_scripts import instances, bus_interfaces, adhoc_connections, tie_offs, export_ports

class MLGeneratedSoC(Module):
    def __init__(self):
        # We use a pure Migen Module to handle structural stitching flawlessly.
        # This bypasses LiteX CPU/CSR auto-naming bugs during dynamic execution.
        
        self.ios = set()
        
        # 1. Instantiate the IPs
        instances.apply(self)
        
        # 2. Connect the bus interfaces
        bus_interfaces.apply(self)
        
        # 3. Adhoc connections (interrupts, sidebands)
        adhoc_connections.apply(self)
        
        # 4. Tie-offs (intentional 0/1)
        tie_offs.apply(self)
        
        # 5. Export signals to the top level
        export_ports.apply(self)

if __name__ == "__main__":
    soc = MLGeneratedSoC()
    
    os.makedirs("build/gateware", exist_ok=True)
    
    # Generate the Verilog wrapper
    v_output = verilog.convert(soc, ios=soc.ios, name="my_soc")
    
    with open("build/gateware/my_soc.v", "w") as f:
        f.write(v_output.main_source)
        
    print("\\n✅ Commercial EDA/Migen Assembly Complete.")
    print("Check build/gateware/my_soc.v for the RTL wrapper!")
