import struct
import glob

from elftools.elf.elffile import ELFFile

regnames = ["zero", "ra", "sp", "gp", "tp","t0", "t1", "t2", "s0", "s1", "a0", "a1", "a2", "a3", "a4", "a5", "a6", "a7", "s2", "s3", "s4", "s5", "s6", "s7", "s8", "s9", "s10", "s11", "t3", "t4", "t5", "t6", "PC"]
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
  ADD = ADDI = 0b000
  SLLI = BNE = 0b001
  SLT = SLTI = 0b010
  SLTU = SLTIU = 0b011

  XOR = XORI = 0b100
  SRL = SRLI = SRA = SRAI = 0b101
  OR = ORI =0b110
  AND = ANDI = 0b111

  BEQ = 0b000
  # BNE = 0b001
  BLT = 0b100
  BGE = 0b101
  BLTU = 0b110
  BGEU = 0b111

  LB = 0b000
  LH = 0b001
  LW = 0b010
  LBU = 0b100
  LHU = 0b101


  ECALL = EBREAK = 0b000
  CSRRW = 0b001
  CSRRS = 0b010
  CSRRC = 0b011
  CSRRWI = 0b101
  CSRRSI = 0b110
  CSRRCI = 0b111

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
  if not (addr >=0 and addr < len(memory)):
    raise Exception("read invalid address: %r" % addr)
  # memory is little endian, so we need to reverse the bytes
  return struct.unpack("<I", memory[addr:addr+4])[0]



def dump():
  pp = []
  for i in range(33):
      if i != 0 and i % 8 == 0:
          pp.append("\n")
      pp.append("%3s: %08x " % ("%s" %regnames[i], regfile[i]))
  # pp.append("\n")
  # pp.append("PC: %08x" % regfile[PC])
  pp.append("\n")
  print("".join(pp))


def sign_extend(x, width):
  if x >> (width - 1) == 1:
    return -((1 << width) - x)
  else:
    return x

def arith(funct3, x, y):
  if funct3 == Funct3.ADDI:
    return x + y
  # elif funct3 == Funct3.SRL:
  elif funct3 == Funct3.ANDI:
    return x & y
  elif funct3 == Funct3.SRLI:
    return x >> y
  elif funct3 == Funct3.ORI:
    return x | y
  elif funct3 == Funct3.XORI:
    return x ^ y
  elif funct3 == Funct3.SLLI:
    return x << (y & 0x1f)
  elif funct3 == Funct3.SLTI:
    return 1 if x < y else 0
  elif funct3 == Funct3.SLTU:
    return 1 if x < y else 0
  else:
    dump()
    raise Exception("Unknown funct3: %r" % funct3)


def step():
  # Instruction Fetch
  ins = r32(regfile[PC])
  if ins == 0xC0001073:
    print("success")
    return False
  # Instruct Decode
  def gibi(s, e):
    return (ins >> e) &  ((1 << (s-e + 1)) - 1)
  if (gibi(6, 0) == 47):
    regfile[PC] += 4
    return True
  opcode = Ops(gibi(6, 0))
  print("%x:\t%08x, opcode: %r, regfile[rs1]: %x" %(regfile[PC], ins, opcode, regfile[gibi(19, 15)]))

  if opcode == Ops.JAL:
    # J-type instruction
    rd = gibi(11, 7)
    # assert rd == 0
    imm = gibi(31, 21) << 1 | gibi(20, 20) << 11 | gibi(19, 12) << 12
    # sign extend
    imm = sign_extend(imm, 21)
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
    imm = gibi(31, 20)
    imm = sign_extend(imm, 12)

    # print("imm:", imm, "funct3:", funct3, "rs1:", rs1, "rd:", rd)
    regfile[rd] = arith(funct3, regfile[rs1], imm)
  elif opcode == Ops.AUIPC:
    rd = gibi(11, 7)
    imm = gibi(31, 12)
    regfile[rd] = regfile[PC] + (imm << 12)
  elif opcode == Ops.BRANCH:
    imm = (gibi(31, 31) << 12 | gibi(30, 25) << 5 | gibi(11, 8) << 1 | gibi(7, 7) << 11)

    # sign extend
    imm = sign_extend(imm, 13)
    rs1 = gibi(19, 15)
    rs2 = gibi(24, 20)
    

    funct3 = Funct3(gibi(14, 12))
    # print("opcode:", opcode, "imm:", imm, "funct3:", funct3)
    cond = False
    if funct3 == Funct3.BEQ:
      cond = regfile[rs1] == regfile[rs2]
        
    elif funct3 == Funct3.BNE:
      print("BNE", regfile[rs1], regfile[rs2], imm, hex(regfile[PC] + imm))
      cond = regfile[rs1] != regfile[rs2]
    elif funct3 == Funct3.BLT:
      cond = sign_extend(regfile[rs1], 32) < sign_extend(regfile[rs2], 32)
    elif funct3 == Funct3.BLTU:
      cond = regfile[rs1] < regfile[rs2]
    elif funct3 == Funct3.BGE:
      cond = sign_extend(regfile[rs1], 32) >= sign_extend(regfile[rs2], 32)
    elif funct3 == Funct3.BGEU:
      cond = regfile[rs1] >= regfile[rs2]
    else:
      raise Exception("%r: Unknown funct3: %r" % (opcode, funct3))
    if cond:
      regfile[PC] += imm
      return True
  elif opcode == Ops.STORE:
    imm = gibi(31, 25) << 5 | gibi(11, 7)
    rs2 = gibi(24, 20)
    rs1 = gibi(19, 15)
    funct3 = Funct3(gibi(14, 12))
    print("imm:", imm, "funct3:", funct3, "rs2:", rs2, "rs1:", rs1)
  elif opcode == Ops.SYSTEM:
    funct3 = Funct3(gibi(14, 12))
    csr = gibi(31, 20)
    rs1 = gibi(19, 15)
    rd = gibi(11, 7)
    if funct3 == Funct3.ECALL or funct3 == Funct3.EBREAK:
      funct12 = gibi(31, 20)
      if funct12 == 0:
        print("ECALL")
      elif funct12 == 1:
        print("EBREAK")
      else:
        pass
    elif funct3 == Funct3.CSRRW:
      print("csr:", csr, "rs1:", rs1)
      # regfile[csr] = regfile[rs1]
    elif funct3 == Funct3.CSRRS:
      print("csr:", csr, "rs1:", rs1)
      # regfile[csr] = regfile[csr] | regfile[rs1]
    elif funct3 == Funct3.CSRRC:
      print("csr:", csr, "rs1:", rs1)
      # regfile[csr] = regfile[csr] & ~regfile[rs1]
    elif funct3 == Funct3.CSRRWI:
      print("csr:", csr, "rs1:", rs1)
      # regfile[csr] = rs1
    elif funct3 == Funct3.CSRRSI:
      print("csr:", csr, "rs1:", rs1)
      # regfile[csr] = regfile[csr] | rs1
    elif funct3 == Funct3.CSRRCI:
      print("csr:", csr, "rs1:", rs1)
      # regfile[csr] = regfile[csr] & ~rs1
    # if imm == 0: # ECALL
    #     print("ECALL - Program terminated")
    #     return False  # 结束程序执行
    # else: # EBREAK
    #     print("EBREAK")
  elif opcode == Ops.OP:
    # R-type instruction
    funct3 = Funct3(gibi(14, 12))
    rs2 = gibi(24, 20)
    rs1 = gibi(19, 15)
    rd = gibi(11, 7)
    regfile[rd] = arith(funct3, regfile[rs1], regfile[rs2])
  elif opcode == Ops.LOAD:
    imm = gibi(31, 20)
    rs1 = gibi(19, 15)
    funct3 = Funct3(gibi(14, 12))
    rd = gibi(11, 7)
    if funct3 == Funct3.LB:
      imm = sign_extend(imm, 12)
      regfile[rd] = r32(regfile[rs1] + imm) & 0xff
    elif funct3 == Funct3.LBU:
      regfile[rd] = r32(regfile[rs1] + imm) & 0xff
    elif funct3 == Funct3.LH:
      imm = sign_extend(imm, 12)
      regfile[rd] = r32(regfile[rs1] + imm) & 0xffff
    elif funct3 == Funct3.LHU:
      regfile[rd] = r32(regfile[rs1] + imm) & 0xffff
    elif funct3 == Funct3.LW:
      imm = sign_extend(imm, 12)
      regfile[rd] = r32(regfile[rs1] + imm) & 0xffffffff
    else:
      raise Exception("%r: Unknown funct3: %r" % (opcode, funct3))
  elif opcode == Ops.LUI:
    imm = gibi(31, 12) << 12
    rd = gibi(11, 7)
    # regfile[rd] = sign_extend(imm, 32)
    regfile[rd] = imm
  elif opcode == Ops.MISC:
    pass
  else:
    dump()
    raise Exception("Unknown opcode: %r" % opcode)
  


    
  # Execute
  # Access
  # Write Back
  regfile[PC] += 4
  return True

if __name__ == "__main__":
  i = 0
  for f in glob.glob("./riscv-tests/isa/rv32ui-p-*"):
      if f.endswith(".dump"):
        continue
      if "fence_i" in f:
        continue
      print(f)
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
  dump()