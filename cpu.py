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

  MISC = 0b0001111
  SYSTEM = 0b1110011

class Funct3(Enum):
  ADD = ADDI = ECALL = EBREAK =0b000
  SLLI = 0b001
  SLT = SLTI = 0b010
  SLTU = SLTIU = 0b011

  XOR = XORI = 0b100
  SRL = SRLI = SRA = SRAI = 0b101
  OR = ORI =0b110
  AND = ANDI = 0b111
   

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
  def gibi(s, e):
    return (ins >> e) &  ((1 << (s-e + 1)) - 1)
  
  opcode = Ops(gibi(6, 0))
  print("%x %08x %r" %(regfile[PC], ins, opcode))

  if opcode == Ops.JAL:
    # J-type instruction
    rd = gibi(11, 7)
    # assert rd == 0
    imm_10_1 = gibi(31, 21)
    imm_11 = gibi(20, 20)
    imm_19_12 = gibi(19, 12)
    imm_20 = gibi(31, 31)
    imm = imm_10_1 << 1 | imm_11 << 11 | imm_19_12 << 12 | imm_20 << 31
    # Store the return address
    regfile[rd] = regfile[PC] + 4
    # Add offfset
    regfile[PC] += imm
    return True
  elif opcode == Ops.JALR:
    # I-type
    imm = gibi(31, 20)
    rs1 = gibi(19, 15)
    funct3 = Funct3(gibi(14, 12))
    rd = gibi(11, 7)
    regfile[rd] = regfile[PC] + 4
    regfile[PC] = regfile[rs1] + imm
    return True
  elif opcode == Ops.IMM:
    # I-type instruction
    rd = gibi(11, 7)
    funct3 = Funct3(gibi(14, 12))
    rs1 = gibi(19, 15)
    imm = gibi(30, 20)
    if gibi(31, 31) == 1:
      imm |= 0xfffff800
    print("imm:", imm, "funct3:", funct3, "rs1:", rs1, "rd:", rd)
    if funct3 == Funct3.ADDI:
      regfile[rd] = regfile[rs1] + imm
      print("rd:", hex(regfile[rd]))
    elif funct3 == Funct3.SLLI:
        regfile[rd] = regfile[rs1] << (imm & 0x1f)
    else:
        dump()
        raise Exception("%r: Unknown funct3: %r" % (opcode, funct3))
    # elif funct3 == Funct3.SLLI:
    #   regfile[rd] = regfile[rs1] << (imm & 0x1f)
    # elif funct3 == Funct3.SLTI:
    #   regfile[rd] = 1 if regfile[rs1] < imm else 0
    # elif funct3 == Funct3.SLTIU:
    #   regfile[rd] = 1 if regfile[rs1] < imm else 0
    # else:
  elif opcode == Ops.AUIPC:
    rd = gibi(11, 7)
    imm = gibi(31, 12)
    regfile[rd] = regfile[PC] + (imm << 12)
  elif opcode == Ops.BRANCH:
    imm = (gibi(31, 31) << 12 | gibi(30, 25) << 5 | gibi(11, 8) << 1 | gibi(7, 7) << 11) << 1
    funct3 = Funct3(gibi(14, 12))
    print("imm:", imm, "funct3:", funct3)
  elif opcode == Ops.STORE:
    imm = gibi(31, 25) << 5 | gibi(11, 7)
    rs2 = gibi(24, 20)
    rs1 = gibi(19, 15)
    funct3 = Funct3(gibi(14, 12))
    print("imm:", imm, "funct3:", funct3, "rs2:", rs2, "rs1:", rs1)
  elif opcode == Ops.SYSTEM:
    pass
    # if funct3 == Funct3.ECALL:
    #   if imm == 0:
    #       print("ECALL")
    #   elif imm == 1:
    #       print("EBREAK")
    #   else:
    #       raise Exception("%r: Unknown funct3: %r" % (opcode, funct3))
    # elif funct3 == Funct3.SLLI:
    #   imm = gibi(31, 20)
    #   rs1 = gibi(19, 15)
    #   funct3 = Funct3(gibi(14, 12))
    #   rd = gibi(11, 7)
    #   regfile[rd] = regfile[rs1] << (imm & 0x1f)
    # elif funct3 == Funct3.SRL:
    #   funct7 = gibi(31, 25)
    #   rs2 = gibi(24, 20)
    #   rs1 = gibi(19, 15)
    #   funct3 = Funct3(gibi(14, 12))
    #   rd = gibi(11, 7)
    #   if funct7 == 0:
    #     # Shift left logical
    #     regfile[rd] = regfile[rs1] << (imm & 0x1f)
    #   elif funct7 == 0x20:
    #     # Shift right arithmetic
    # else:
    #   raise Exception("%r: Unknown funct3: %r" % (opcode, funct3))
  elif opcode == Ops.OP:
    # R-type instruction
    funct7 = gibi(31, 25)
    rs2 = gibi(24, 20)
    rs1 = gibi(19, 15)
    funct3 = Funct3(gibi(14, 12))
    rd = gibi(11, 7)
    if funct3 == Funct3.ADD:
        regfile[rd] = regfile[rs1] + regfile[rs2]
    else:
      raise Exception("%r: Unknown funct3: %r" % (opcode, funct3))

    
  else:
    dump()
    raise Exception("Unknown opcode: %r" % opcode)
  


    
  # Execute
  # Access
  # Write Back
  regfile[PC] += 4
  return True

if __name__ == "__main__":
  print(Funct3.ADD == Funct3.ADDI)
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