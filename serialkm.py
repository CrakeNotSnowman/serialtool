#!/home/keith/anaconda2/bin/python
from __future__ import print_function

import Queue
import argparse
import glob
import sys
import textwrap
import threading
import time

import serial

"""
adding folder to path
INFO: http://stackoverflow.com/questions/15587877/run-a-python-script-in-terminal-without-the-python-command

export PATH=/home/keith/Documents/filesForProgramming/Libraries/runScripts/:$PATH

Keeping folder in path
INFO: http://superuser.com/questions/678113/how-to-add-a-line-to-bash-profile
sudo echo 'export PATH=/home/keith/Documents/filesForProgramming/Libraries/runScripts/:$PATH' >>~/.bashrc

"""


class PrintQueueThread(threading.Thread):
    def __init__(self, q, mode):
        threading.Thread.__init__(self)
        self._stop = threading.Event()
        self.name = 'SerialPrinter'
        self.q = q
        self.daemon = True
        self.mode = mode

    def run(self):
        just_print_it(self.q, self.mode)

    def stop(self):
        self._stop.set()

    def stopped(self):
        return self._stop.isSet()


class SerialReadThread(threading.Thread):
    def __init__(self, ser, q):
        threading.Thread.__init__(self)
        self._stop = threading.Event()
        self.name = 'SerialReader'
        self.q = q
        self.ser = ser
        self.daemon = True

    def run(self):
        my_serial_read(self.ser, self.q)

    def stop(self):
        self._stop.set()

    def stopped(self):
        return self._stop.isSet()


class SerialWriteThread(threading.Thread):
    def __init__(self, ser, q, mode_w):
        threading.Thread.__init__(self)
        self._stop = threading.Event()
        self.name = 'SerialWriter'
        self.q = q
        self.ser = ser
        self.mode = mode_w
        self.daemon = True

    def run(self):
        my_serial_write(self.ser, self.q, self.mode)

    def stop(self):
        self._stop.set()

    def stopped(self):
        return self._stop.isSet()


def interface():
    try:
        def_port = serial_ports().pop()
    except IndexError:
        def_port = '/dev/ttyACM0'

    args = argparse.ArgumentParser(
        prog='SerialModuleKM.py',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description='This is a simple python based serial monitor')
    args.add_argument(
        '-p',
        '--port',
        default=def_port,
        help='Serial Port')
    args.add_argument(
        '-b',
        '--baudrate',
        type=int,
        default=9600,
        help='Baudrate')
    args.add_argument(
        '-t',
        '--time-out',
        type=float,
        default=0.01,
        help='Time Out')
    args.add_argument(
        '-m',
        '--mode',
        default='s',
        help="Mode for Incoming Data: 's':String, 'b':Binary, 'h':Hex")
    args.add_argument(
        '-w',
        '--write-mode',
        default='s',
        help="Mode for User Input Data: 's':String, 'b':Binary, 'h':Hex")
    args = args.parse_args()
    return args


def serial_ports():
    """
    http://stackoverflow.com/questions/12090503
        Author: http://stackoverflow.com/users/300783/thomas
    Lists serial ports
    :raises EnvironmentError:
        On unsupported or unknown platforms
    :returns:
        A list of available serial ports
    """
    if sys.platform.startswith('win'):
        ports = ['COM' + str(i) for i in xrange(1, 257)]
    elif sys.platform.startswith('linux') or sys.platform.startswith('cygwin'):
        # this is to exclude your current terminal '/dev/tty'
        ports = glob.glob('/dev/tty[A-Za-z]*')
    elif sys.platform.startswith('darwin'):
        ports = glob.glob('/dev/tty.*')
    else:
        raise EnvironmentError('Unsupported platform')
    result = []
    for port in ports:
        try:
            s = serial.Serial(port)
            s.close()
            result.append(port)
        except (OSError, serial.SerialException):
            pass
    return result


def just_print_it(q, mode):
    i = 3
    recent_message = False
    while True:
        if not q.empty():
            msg = q.get()
            if msg[0] == 'E':
                sys.stdout.write(str(msg[1]))
            else:
                msg = msg[1]
                if mode == 's':
                    sys.stdout.write(str(msg))
                elif mode == 'b':
                    bin_msg = ''.join(
                        '{:08b}'.format(ord(c), 'b') for c in str(msg))
                    sys.stdout.write(str(bin_msg))
                    sys.stdout.write(':')
                elif mode == 'h':
                    hex_msg = ':'.join(
                        '{:02x}'.format(ord(c)) for c in str(msg))
                    sys.stdout.write(str(hex_msg))
                    sys.stdout.write(':')
            q.task_done()
            recent_message = True
            i = 0
        else:
            time.sleep(0.01)
            i += 1
            if recent_message is True and i > 3:
                recent_message = False
                i = 0
                sys.stdout.write('\n')


def my_serial_read(ser, q):
    i = 3
    recent_message = False
    while True:
        try:
            msg = ser.read()
        except:
            msg = ''
        if msg != '':
            q.put(('R', msg))
            recent_message = True
            i = 0
        else:
            i += 1
            time.sleep(0.001)
            if recent_message is True and i > 3:
                recent_message = False
                i = 0
                # q.put('\n')


def hex_parse(raw_msg):
    # Parsing
    temp_msg = ''.join(raw_msg.upper().split('0X'))
    temp_msg = ''.join(temp_msg.split('\X'))
    if len(temp_msg) > 2 and temp_msg.startswith('0X'):
        temp_msg = temp_msg[2:]
    hex_vals = set('0123456789ABCDEF')
    temp_msg = "".join(c for c in temp_msg if c in hex_vals)

    # Variables used
    byte_hold = 0x00
    byte_arr = []

    hex_str_to_int = {'0': 0x00, '1': 0x01, '2': 0x02, '3': 0x03, '4': 0x04,
                      '5': 0x05, '6': 0x06, '7': 0x07, '8': 0x08, '9': 0x09,
                      'A': 0x0A, 'B': 0x0B, 'C': 0x0C, 'D': 0x0D, 'E': 0x0E,
                      'F': 0x0F}
    # Start with most sig byte
    sig_byte_point = len(temp_msg) % 2
    if sig_byte_point == 1:
        # Pack the first Byte
        try:
            val = hex_str_to_int[temp_msg[0]]
        except KeyError:
            pass
        else:
            byte_hold <<= 4
            byte_hold |= val

        byte_arr.append(byte_hold)
    # Rest of string/bytes
    byte_hold = 0x00

    action = 0
    for i in xrange(sig_byte_point, len(temp_msg)):
        try:
            val = hex_str_to_int[temp_msg[i]]
        except KeyError:
            pass
        else:
            byte_hold <<= 4
            byte_hold |= val

        action += 1
        if action == 2:
            byte_arr.append(byte_hold)
            byte_hold = 0x00
            action = 0

    hex_msg = ''.join(chr(x) for x in byte_arr)
    return hex_msg


def bin_parse(raw_msg):
    # Parsing Input string
    temp_msg = ''.join(raw_msg.upper().split('0B'))
    if len(temp_msg) > 2 and temp_msg.startswith('0B'):
        temp_msg = temp_msg[2:]
    temp_msg = ''.join(c for c in temp_msg if c in '01')

    # Variables used
    # bin_msg = ''
    byte_hold = 0x00
    byte_arr = []

    bin_str_to_int = {'0': 0x00, '1': 0x01}

    # Start with most sig byte
    sig_byte_point = len(temp_msg) % 8
    if sig_byte_point != 0:
        # first len(temp_msg) % 8 will be stuffed into own byte
        # Packing the first byte
        for i in xrange(sig_byte_point):
            try:
                val = bin_str_to_int[temp_msg[i]]
            except KeyError:
                pass
            else:
                byte_hold <<= 1
                byte_hold |= val

        byte_arr.append(byte_hold)
    # Rest of sting/bytes
    byte_hold = 0x00
    for i in xrange(sig_byte_point, len(temp_msg)):
        try:
            val = bin_str_to_int[temp_msg[i]]
        except KeyError:
            pass
        else:
            byte_hold <<= 1
            byte_hold |= val

        if (i - sig_byte_point + 1) % 8 == 0:
            byte_arr.append(byte_hold)
            byte_hold = 0x00

    bin_msg = ''.join(chr(x) for x in byte_arr)
    # print hex(binMsg)
    return bin_msg


def parse_all(raw_msg):
    if len(raw_msg) > 2:
        if raw_msg[0] == '0':
            if raw_msg[1] in 'bB':
                clean_msg = bin_parse(raw_msg)
            elif raw_msg[1] in 'xX':
                clean_msg = hex_parse(raw_msg)
            else:
                clean_msg = raw_msg
        else:
            clean_msg = raw_msg
    else:
        clean_msg = raw_msg
    return clean_msg


def my_serial_write(ser, q, mode):
    while True:
        my_msg = raw_input()  # If in python 3, change raw_input() to input()
        if my_msg != '':
            if mode == 'a':
                my_msg = parse_all(my_msg)
            elif mode == 'h':
                my_msg = hex_parse(my_msg)
            elif mode == 'b':
                my_msg = bin_parse(my_msg)
            # else:
            #     try:
            #         print 'KM'#ser.write(myMsg)
            #     except:
            #     q.put(('E', str('Could not Send: ' + str(myMsg))))
            ser.write(my_msg)

        else:
            time.sleep(0.001)


def initialize(args):
    q = Queue.Queue()
    port = args.port
    val_ports = serial_ports()
    my_baud = args.baudrate
    my_time_out = args.time_out

    # Verify that the input mode is valid, if not, treat RX as a char
    mode = args.mode.lower()
    mode_dict = {'s': 's', 'str': 's', 'string': 's',
                 'b': 'b', 'bin': 'b', 'binary': 'b',
                 'h': 'h', 'hex': 'h', 'hexadecimal': 'h'}
    try:
        mode = mode_dict[mode]
    except KeyError:
        mode = 's'
        print('   *** RX is being treated as characters, Your input was invalid                *')
        print("   *** Please use either  's' for String, 'b' for Binary, or 'h' for Hexadecimal *")

    wmode = args.write_mode.lower()
    mode_dict.update({'a': 'a', 'all': 'a', 'any': 'a', 'anything': 'a'})

    try:
        wmode = mode_dict[wmode]
    except KeyError:
        wmode = 's'
        print('   *** TX is being treated as characters, Your input was invalid                *')
        print("   *** Please use either  's' for String, 'b' for Binary, or 'h' for Hexadecimal *")

    # Catch Error of wrong port: display all open ports instead
    if port.lower() in ('?', 'who', 'whois'):
        if not val_ports:
            print('\tNo valid ports found')
        else:
            print('\tValid ports:')
            for port in val_ports:
                print('\t\t{}'.format(port))
        return

    try:
        ser = serial.Serial(port, baudrate=my_baud, timeout=my_time_out)
    except (ValueError, serial.SerialException):
        # https://pythonhosted.org/pyserial/pyserial_api.html?highlight=serial#serial.Serial
        print('Could not connect to Serial Port')
        if not val_ports == 0:
            print('\tNo valid ports found')
        else:
            print('\tValid ports:')
            for port in val_ports:
                print('\t\t{}'.format(port))
        return

    # Start up
    connected = False
    print(textwrap.dedent("""\
        \t*****************************************
        \t* Opening Serial Port Communication\t*
        \t*\tPort:      \t{}\t*
        \t*\tBaudrate:  \t{}\t\t*
        \t*\tTime Out:  \t{}\t\t*
        \t*\tPrint Mode:\t'{}'\t\t*
        \t*\tWrite Mode:\t'{}'\t\t*
        """.format(port, my_baud, my_time_out, mode, wmode)))

    while not connected:
        ser.read()
        connected = True
    print(textwrap.dedent("""\
        \t*\tSerial Communication Open\t*
        \t*****************************************
        """))

    print_thread = PrintQueueThread(q, mode)
    read_thread = SerialReadThread(ser, q)
    write_thread = SerialWriteThread(ser, q, wmode)

    try:
        print_thread.start()
        read_thread.start()
        write_thread.start()
        while True:
            time.sleep(1)
    except(KeyboardInterrupt, SystemExit):
        # Allows for clean exiting
        write_thread.stop()
        read_thread.stop()
        print_thread.stop()
        ser.close()
        time.sleep(0.001)
        print(textwrap.dedent("""\
            \t*****************************************
            \t* Exited Serial Port Communication\t*
            \t*****************************************
            """))

    return


if __name__ == '__main__':
    initialize(interface())
