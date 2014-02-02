#!/usr/bin/python

# A python script to dump to stdout the data recieved on serial port.
# Tested on Max OSX 10.8.5 with python 2.7.2.
#
# Based on example from pySerial.
#
# NOTE: Opening the serial port may cause a DTR level change that on
# some Arduinos cause a CPU reset.

import getopt
import optparse
import os
import re
import select
import sys
import termios
import time

# Set later when parsing args.
FLAGS = None

# Pattern to parse a frame line.
# NOTE: excluding frames with ERR suffix.
kFrameRegex = re.compile('^([0-9a-f]{2})((?: [0-9a-f]{2})+) ([0-9a-f]{2})$')

# Represents a parsed LIN frame
class LinFrame:
  def __init__(self, id, data, checksum):
    self.id = id
    self.data = data
    self.checksum = checksum
 
  def __str__(self):
    return "[" + self.id + "] [" + " ".join(self.data) + "] [" + self.checksum + "]"

  __repr__ = __str__

# Convert a list of two hex digits strings to a list of a single binary digit
# strings.
def hexListToBitList(hex_list):
  result = []
  for hex_str in hex_list:
    as_int = int(hex_str, 16)
    bin_str = bin(as_int)[2:].zfill(8)
    result.extend(list(bin_str))
  return result

# If a valid frame return a LinFrame, otherwise 
# returns None.
def parseLine(line):
  m = kFrameRegex.match(line)
  if not m:
    return None
  return LinFrame(m.group(1), m.group(2).split(), m.group(3))

# Parse args and set FLAGS.
def parseArgs(argv):
  global FLAGS
  parser = optparse.OptionParser()
  parser.add_option(
      "-p", "--port", dest="port",
      default="/dev/cu.usbserial-A600dOYP",
      help="serial port to read", metavar="PORT")
  parser.add_option(
      "-d", "--diff", dest="diff",
      default=False,
      help="show only data changes")
  parser.add_option(
      "-s", "--speed", dest="speed",
      default=115200,
      help="set baud rate, 0 for default")
  (FLAGS, args) = parser.parse_args()
  if args:
    print "Uexpected arguments:", args
    print "Aborting"
    sys.exit(1)
  print "Flags:"
  print "  --port:  ", FLAGS.port
  print "  --diff:  ", FLAGS.diff
  print "  --speed: ", FLAGS.speed

# Return time now in millis. We use it to comptute relative time.
def timeMillis():
  return int(round(time.time() * 1000))

# Format relative time in millis as "sssss.mmm".
def formatRelativeTimeMillis(millis):
  seconds = int(millis / 1000)
  millis_fraction = millis % 1000
  return "%05d.%03d" % (seconds, millis_fraction)

# Clear pending chars until no more.
def clearPendingChars(fd):
  while (True):
    ready,_,_ = select.select([fd],[],[], 1e-10)
    if not ready:
      return;
    os.read(fd, 1)

# Wait for next input character and return it as a single
# char string.
def readChar(fd):
  # Wait for rx data ready. Timeout of 0 indicates wait forever.
  ready,_,_ = select.select([fd],[],[], 0)
  # Read and output one character
  return os.read(fd, 1)

# Read and return a single line, without the eol charcater.
def readLine(fd):
  line = [] 
  while True:
    char = readChar(fd)
    if (char == "\n"):
      return "".join(line)
    line.append(char)

# Open the serial port for reading at the specified speed.
# Returns the port's fd.
def openPort():
  while True:
    try:
      # Open port in read only mode. Call is blocking.
      print "Opening port"
      fd = os.open(FLAGS.port, os.O_RDONLY | os.O_NOCTTY )
      print "Done"
      break
    except Exception:
      print "Exception, will retry"
      time.sleep(1)

  # If speed requested, setup the port.
  if FLAGS.speed != 0:
    print "Setting port speed to", FLAGS.speed
    iflag, oflag, cflag, lflag, ispeed, ospeed, cc = termios.tcgetattr(fd) 
    ispeed = FLAGS.speed
    ospeed = FLAGS.speed
    termios.tcsetattr(fd, termios.TCSANOW, [iflag, oflag, cflag, lflag, ispeed, ospeed, cc])
    print "Done"
  else:
    print "Using default speed"
  print "Clearing pending chars"
  clearPendingChars(fd)
  print "Done"
  return fd

# For now, assuming both are of same size.
# Return a list of '0', '1' and '-', one per data bit.
def diffBitLists(old_bit_list, new_bit_list):
  result = []
  for idx, new_val in enumerate(new_bit_list):
    if new_val != old_bit_list[idx]:
      result.append(new_val)
    else:
      result.append("-")
  return result

# Insert a seperator every n  charaters.
def insertSeperators(str, n, sep):
  return sep.join(str[i: i+n] for i in range(0, len(str), n))

def main(argv):
  parseArgs(argv)  
  fd = openPort()
  start_time_millis = timeMillis();
  last_bit_lists = {}
  while True:
    line = readLine(fd);
    rel_time_millis = timeMillis() - start_time_millis
    timestamp = formatRelativeTimeMillis(rel_time_millis);
    # Dump raw lines
    if not FLAGS.diff:
      out_line = "%s  %s\n" % (timestamp, line)
      sys.stdout.write(out_line)
      sys.stdout.flush()
      continue
    # Parse and dump diffs only
    frame = parseLine(line)
    if not frame:
      continue
    id = frame.id
    new_bit_list = hexListToBitList(frame.data)
    if id not in last_bit_lists:
      last_bit_lists[id] = new_bit_list
      continue
    old_bit_list = last_bit_lists[id]
    last_bit_lists[id] = new_bit_list
    if new_bit_list == old_bit_list:
      continue
    diff_bit_list = diffBitLists(old_bit_list, new_bit_list)
    diff_str = insertSeperators("".join(diff_bit_list), 4, " ")
    diff_str = insertSeperators(diff_str, 10, "| ")
    out_line = "%s  %s: | %s |\n" % (timestamp, id, diff_str)
    sys.stdout.write(out_line)
    sys.stdout.flush()

if __name__ == "__main__":
  main(sys.argv[1:])


