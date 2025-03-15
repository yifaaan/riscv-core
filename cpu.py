import struct
import glob

from elftools.elf.elffile import ELFFile

regfile = [0]*33
PC = 32

from enum import Enum
# RV32I Base Instruction Set
class Ops(Enum):
  LUI = 0b0110111 # load upper immediate
  LOAD = 0b0000011
  STORE = 0b0100011

  AUIPC = 0b0010111 # add upper immediate to pc
  BRANCH = 0b1100011
  JAL = 0b1101111
  JALR = 0b1100111

  
  
  IMM = 0b0010011
  OP = 0b0110011

  FENCE = 0b0001111
  SYSTEM = 0b1110011
    


# 64k memory at 0x80000000, little endian
memory = bytearray(b'\x00' * 0x10000)

def ws(dat, addr):
  global memory
  # print(hex(addr), len(dat))
  addr -= 0x80000000
  
  assert addr >=0 and addr < len(memory)
  memory = memory[:addr] + dat + memory[addr+len(dat):]

def r32(addr):
  addr -= 0x80000000
  assert addr >=0 and addr < len(memory)
  # memory is little endian, so we need to reverse the bytes
  return struct.unpack("<I", memory[addr:addr+4])[0]

def gibi(ins, s, e):
   return (ins >> e) &  ((1 << (s-e + 1)) - 1)

def dump():
  pp = []
  for i in range(32):
      if i != 0 and i % 8 == 0:
          pp.append("\n")
      pp.append("%3s: %08x " % ("x%d" %i, regfile[i]))
  pp.append("\n")
  pp.append("PC: %08x" % regfile[PC])
  pp.append("\n")
  print("".join(pp))

def step():
  # Instruction Fetch
  ins = r32(regfile[PC])
  # Instruct Decode
  opcode = Ops(gibi(ins, 6, 0))
  print(hex(regfile[PC]), opcode)
  if opcode == Ops.JAL:
    rd = gibi(ins, 11, 7)
    assert rd == 0
    imm_10_1 = gibi(ins, 31, 21)
    imm_11 = gibi(ins, 20, 20)
    imm_19_12 = gibi(ins, 19, 12)
    imm_20 = gibi(ins, 31, 31)
    imm = imm_10_1 << 1 | imm_11 << 11 | imm_19_12 << 12 | imm_20 << 31
    # Store the return address
    regfile[rd] = regfile[PC] + 4
    # Add offfset
    regfile[PC] += imm
    # Increase PC
    regfile[PC] += 4
    return True
    
  # Execute
  # Access
  # Write Back
  return False

if __name__ == "__main__":
  for f in glob.glob("./riscv-tests/isa/rv32ui-*"):
      if f.endswith(".dump"):
          continue
      with open(f, "rb") as f:
          print("test", f)
          elf = ELFFile(f)
          for s in elf.iter_segments():
              if s.header.p_type != "PT_LOAD":
                  continue
              ws(s.data(), s.header.p_paddr)
          regfile[PC] = 0x80000000
          while step():
              pass
      break