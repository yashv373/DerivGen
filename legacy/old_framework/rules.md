# DerivGen Project Rules & Core Philosophy

**CRITICAL DIRECTIVE FOR AI ASSISTANTS:** 
Read this file before generating any code or making any architectural decisions for this repository. This defines the exact boundary of what the product is and how the workflow operates.

## 1. Project Identity
* **DerivGen is an ML Assistance Solution.** The ultimate product is the Machine Learning model, not the EDA framework.
* **The Goal:** To generate derivative SoC designs (Child SoCs) from a Base SoC (Parent SoC) based on Natural Language Processing (NLP) instructions.

## 2. The EDA Framework's Role (The "Plumbing")
* We are using open-source tools (**Migen, FuseSoC, IP-XACT**) to strictly *mimic* a commercial EDA workflow (e.g., Arteris Magillem, Agnisys IDS-Integrate).
* **Why?** Because we DO NOT want hallucinated RTL from the ML model. The ML model is fundamentally bad at writing syntactically perfect Verilog wrappers. 
* **The Boundary:** The Python EDA framework handles 100% of the RTL assembly and XML generation. The EDA framework *never* writes the internal behavioral logic of an IP.

## 3. The ML Workflow (The Testing Pipeline)
This is the exact sequence of how DerivGen is tested and improved:

1. **Golden Reference:** A complete, functioning Base SoC (like `STA-SoC`) is manually built using real, synthesizable Verilog IPs. 
2. **NLP Instruction:** The ML model is given an instruction (e.g., *"Strip out the lockstep comparator and the shadow FSM to create a low-power derivative"*).
3. **ML Prediction:** The ML model determines which IPs to keep, remove, or rewire. It outputs structured input files (e.g., Python lists, JSON) for the EDA framework.
4. **Deterministic Assembly:** The EDA framework reads the ML's output, instantiates the requested IPs, and generates the Child SoC Wrapper RTL + IP-XACT.
5. **Accuracy Validation:** The ML-generated Child SoC is structurally diffed against a manually built "Ground Truth" Child SoC. This generates an accuracy statistic (e.g., % of correctly connected wires/ports) used to train and improve the model.

## 4. Hard Rules for Future AI Development
* **Never take shortcuts on the hardware.** When building baseline tests, use actual functional Verilog for the IPs, not dummy stubs. The ML needs real data to train on.
* **Never break the standard.** Always emit IEEE 1685-2009 compliant IP-XACT and proper FuseSoC `.core` files to maintain parity with commercial workflows.
* **Maintain the Separation of Concerns:**
  * **Hardware Engineers:** Write the `.v` IPs.
  * **The ML Model:** Decides *what* connects to *what*.
  * **The EDA Framework:** Writes the top-level Verilog wrapper and XML.
