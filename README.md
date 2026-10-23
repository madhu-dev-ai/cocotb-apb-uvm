\# cocotb-apb-uvm



\[!\[test](https://github.com/madhu-dev-ai/cocotb-apb-uvm/actions/workflows/test.yml/badge.svg)](https://github.com/madhu-dev-ai/cocotb-apb-uvm/actions/workflows/test.yml)



A UVM-style layered testbench in cocotb (Python) for an APB register block.



\## Structure



| Class | Job |

|---|---|

| ApbDriver | Drives the APB signals. The only class that touches them. |

| ApbMonitor | Only watches the bus. Records every finished transfer and sends it to subscribers. |

| ApbScoreboard | Python model of the registers. Checks every transfer the monitor sees. |

| ApbCoverage | Counts which legal cases were seen (10 bins). |

| make\_env | Builds the classes, connects them, starts the clock and monitor, resets the DUT. |



\## Design under test



apb\_regs.sv has 4 registers: CTRL (0x0), DATA (0x4), STATUS (0x8, read-only, 0xA5) and SCRATCH (0xC). pslverr is raised on a bad address or a write to STATUS.



\## Tests



\- test\_coverage\_basic: 6 directed transfers. Covers 6 of 10 bins.

\- test\_random: 500 random reads and writes with full 32-bit data. Covers 10 of 10 bins.



\## Bug stories



\### Bug 1: write to read-only STATUS did not raise an error



I removed the pslverr line for writes to STATUS. Both tests failed. The scoreboard reported that a write to address 0x8 returned err 0 when its model expected err 1. Fix: restored the pslverr line.



\### Bug 2: SCRATCH lost its upper 16 bits



I changed the SCRATCH write so only pwdata\[15:0] was stored. The directed test still passed, because it never writes SCRATCH. The random test failed on many reads of address 0xC. Example:



&#x20;   SCOREBOARD MISMATCH: read addr=0xc data got 0x5e68 expected 0x57c25e68



The written value was 0x57c25e68 and only 0x5e68 came back. Lesson: directed tests with small values can miss bugs that random 32-bit data finds. Fix: store the full pwdata.



\## Run it



&#x20;   make

