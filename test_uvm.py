import random

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge


class ApbDriver:
    """Drives the APB signals. Nothing else should touch them."""

    def __init__(self, dut):
        self.dut = dut

    async def reset(self):
        d = self.dut
        d.presetn.value = 0
        d.psel.value = 0
        d.penable.value = 0
        d.pwrite.value = 0
        d.paddr.value = 0
        d.pwdata.value = 0
        for _ in range(3):
            await RisingEdge(d.pclk)
        d.presetn.value = 1
        await RisingEdge(d.pclk)

    async def write(self, addr, data):
        d = self.dut
        # Setup phase
        d.psel.value = 1
        d.penable.value = 0
        d.pwrite.value = 1
        d.paddr.value = addr
        d.pwdata.value = data
        await RisingEdge(d.pclk)
        # Access phase
        d.penable.value = 1
        await RisingEdge(d.pclk)
        err = int(d.pslverr.value)
        # Back to idle
        d.psel.value = 0
        d.penable.value = 0
        d.pwrite.value = 0
        return err

    async def read(self, addr):
        d = self.dut
        # Setup phase
        d.psel.value = 1
        d.penable.value = 0
        d.pwrite.value = 0
        d.paddr.value = addr
        await RisingEdge(d.pclk)
        # Access phase
        d.penable.value = 1
        await RisingEdge(d.pclk)
        data = int(d.prdata.value)
        err = int(d.pslverr.value)
        # Back to idle
        d.psel.value = 0
        d.penable.value = 0
        return data, err


class ApbMonitor:
    """Only watches the bus. Never drives anything.
    Records one transaction for every finished APB access
    and tells every subscriber (like the scoreboard and coverage)."""

    def __init__(self, dut):
        self.dut = dut
        self.transactions = []
        self.subscribers = []

    async def run(self):
        d = self.dut
        while True:
            await RisingEdge(d.pclk)
            try:
                psel = int(d.psel.value)
                penable = int(d.penable.value)
            except ValueError:
                continue  # signals not ready yet (before reset)
            if psel == 1 and penable == 1:
                tx = {
                    "write": int(d.pwrite.value),
                    "addr": int(d.paddr.value),
                    "wdata": int(d.pwdata.value),
                    "rdata": int(d.prdata.value),
                    "err": int(d.pslverr.value),
                }
                self.transactions.append(tx)
                for sub in self.subscribers:
                    sub.check(tx)


class ApbScoreboard:
    """Python model of the register block.
    Checks every transaction the monitor sees."""

    def __init__(self, dut):
        self.dut = dut
        self.regs = {0x0: 0, 0x4: 0, 0xC: 0}  # CTRL, DATA, SCRATCH
        self.status = 0xA5
        self.checked = 0
        self.errors = 0

    def fail(self, msg):
        self.errors += 1
        self.dut._log.error(f"SCOREBOARD MISMATCH: {msg}")

    def check(self, tx):
        self.checked += 1
        addr = tx["addr"]

        if tx["write"] == 1:
            # Write to CTRL, DATA, SCRATCH: ok. STATUS or bad address: error.
            if addr in self.regs:
                expected_err = 0
                self.regs[addr] = tx["wdata"]
            else:
                expected_err = 1
            if tx["err"] != expected_err:
                self.fail(f"write addr={hex(addr)} err got {tx['err']} expected {expected_err}")
        else:
            if addr in self.regs:
                expected_data, expected_err = self.regs[addr], 0
            elif addr == 0x8:
                expected_data, expected_err = self.status, 0
            else:
                expected_data, expected_err = 0, 1
            if tx["rdata"] != expected_data:
                self.fail(f"read addr={hex(addr)} data got {hex(tx['rdata'])} expected {hex(expected_data)}")
            if tx["err"] != expected_err:
                self.fail(f"read addr={hex(addr)} err got {tx['err']} expected {expected_err}")


class ApbCoverage:
    """Counts which legal cases were seen.
    Bins: (register, read/write, error/ok). Only 10 cases are possible."""

    NAMES = {0x0: "CTRL", 0x4: "DATA", 0x8: "STATUS", 0xC: "SCRATCH"}

    def __init__(self, dut):
        self.dut = dut
        self.bins = {}
        for reg in ["CTRL", "DATA", "SCRATCH"]:
            self.bins[(reg, "read", "ok")] = 0
            self.bins[(reg, "write", "ok")] = 0
        self.bins[("STATUS", "read", "ok")] = 0
        self.bins[("STATUS", "write", "err")] = 0
        self.bins[("BAD", "read", "err")] = 0
        self.bins[("BAD", "write", "err")] = 0

    def check(self, tx):
        reg = self.NAMES.get(tx["addr"], "BAD")
        rw = "write" if tx["write"] == 1 else "read"
        res = "err" if tx["err"] == 1 else "ok"
        key = (reg, rw, res)
        if key in self.bins:
            self.bins[key] += 1
        else:
            self.dut._log.info(f"unexpected case seen: {key}")

    def report(self):
        hit = sum(1 for count in self.bins.values() if count > 0)
        total = len(self.bins)
        self.dut._log.info(f"FUNCTIONAL COVERAGE: {hit}/{total} bins")
        for key, count in self.bins.items():
            if count == 0:
                self.dut._log.info(f"  not hit: {key}")
        return hit, total


async def make_env(dut):
    """Builds and connects everything, starts clock and monitor, resets the DUT."""
    cocotb.start_soon(Clock(dut.pclk, 10, unit="ns").start())
    driver = ApbDriver(dut)
    monitor = ApbMonitor(dut)
    scoreboard = ApbScoreboard(dut)
    coverage = ApbCoverage(dut)
    monitor.subscribers.append(scoreboard)
    monitor.subscribers.append(coverage)
    cocotb.start_soon(monitor.run())
    await driver.reset()
    return driver, monitor, scoreboard, coverage


@cocotb.test()
async def test_coverage_basic(dut):
    driver, monitor, scoreboard, coverage = await make_env(dut)

    await driver.write(0x0, 0x1234)   # write CTRL
    await driver.read(0x0)            # read CTRL back
    await driver.write(0x4, 0xBEEF)   # write DATA
    await driver.read(0x8)            # read STATUS (0xA5)
    await driver.write(0x8, 0x55)     # write STATUS -> error expected
    await driver.read(0x2)            # bad address -> error expected
    await RisingEdge(dut.pclk)

    hit, total = coverage.report()
    assert scoreboard.errors == 0
    assert total == 10
    assert hit == 6


@cocotb.test()
async def test_random(dut):
    driver, monitor, scoreboard, coverage = await make_env(dut)

    legal = [0x0, 0x4, 0x8, 0xC]
    bad = [a for a in range(16) if a not in legal]

    for _ in range(500):
        if random.random() < 0.7:
            addr = random.choice(legal)
        else:
            addr = random.choice(bad)
        if random.random() < 0.5:
            await driver.write(addr, random.getrandbits(32))
        else:
            await driver.read(addr)
    await RisingEdge(dut.pclk)

    hit, total = coverage.report()
    dut._log.info(f"scoreboard checked {scoreboard.checked} transactions")
    assert scoreboard.checked == 500
    assert scoreboard.errors == 0
    assert hit == total