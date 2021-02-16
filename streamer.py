# do not import anything else from loss_socket besides LossyUDP
from lossy_socket import LossyUDP
# do not import anything else from socket except INADDR_ANY
from socket import INADDR_ANY
from struct import *
import time
import hashlib
from concurrent.futures.thread import ThreadPoolExecutor
import hashlib

class Streamer:
    def __init__(self, dst_ip, dst_port,
                 src_ip=INADDR_ANY, src_port=0):
        """Default values listen on all network interfaces, chooses a random source port,
           and does not introduce any simulated packet loss."""
        self.socket = LossyUDP()
        self.socket.bind((src_ip, src_port))
        self.dst_ip = dst_ip
        self.dst_port = dst_port
        self.seq = 0
        self.buffer = dict()
        self.prev_recv = -1
        self.closed = False
        self.ack = False
        executor = ThreadPoolExecutor(max_workers=1)
        executor.submit(self.listener)
    
    def hasher(self, incoming: bytes) -> bytes:
        h = hashlib.md5(incoming).digest()
        return h

    def send_helper(self, data_bytes:bytes) -> int:
        length = len(data_bytes)
        #i'm changing the packet structure to fit the hash [16 byte s for storing hash]
        max_packet = int(1400 - calcsize('ic16s'))
        
        packets_sent = 0
        if length <= max_packet:
            #print(calcsize('sic16s'))
            #print('send size', len(pack(str(length) + 'sic16s', data_bytes, self.seq, b'd', self.hasher(data_bytes))))

            self.socket.sendto(pack(str(length) + 'sic16s', data_bytes, self.seq, b'd', self.hasher(data_bytes)), (self.dst_ip, self.dst_port))
            self.seq = self.seq + 1
            packets_sent += 1
        else:
            chunk = max_packet
            while chunk < length:
                # print('send size', len(pack(str(max_packet) + 'sic', data_bytes[chunk - max_packet:chunk], self.seq, b'd')))
                self.socket.sendto(pack(str(max_packet) + 'sic16s', data_bytes[chunk - max_packet:chunk], self.seq, b'd', self.hasher(data_bytes[chunk - max_packet:chunk])), (self.dst_ip, self.dst_port))
                self.seq = self.seq + 1
                packets_sent += 1
                chunk = chunk + max_packet
            # print('send size', len(pack(str(max_packet) + 'sic', data_bytes[chunk - max_packet:], self.seq, b'd')))
            self.socket.sendto(pack(str(max_packet) + 'sic16s', data_bytes[chunk - max_packet:], self.seq, b'd', self.hasher(data_bytes[chunk - max_packet:])), (self.dst_ip, self.dst_port))
            self.seq = self.seq + 1
            packets_sent += 1
        return packets_sent

    def send(self, data_bytes: bytes) -> None:
        """Note that data_bytes can be larger than one packet."""
        # Your code goes here!  The code below should be changed!
        packets_sent = self.send_helper(data_bytes)
        while not self.ack:
            time.sleep(0.25)
            print(self.ack)
            if not self.ack:
                self.seq = self.seq - packets_sent
                packets_sent = self.send_helper(data_bytes)
                print("sending {} again bc dropped".format(data_bytes))
                continue
            else:
                break
        self.ack = False




    def recv(self) -> bytes:
        """Blocks (waits) if no data is ready to be read from the connection."""
        # your code goes here!  The code below should be changed!
        
        # this sample code just calls the recvfrom method on the LossySocket
        print("Looking for", self.prev_recv + 1)
        while not str(self.prev_recv + 1) in self.buffer:
            time.sleep(0.1)
            continue

        print('found it in here', self.buffer)
        self.prev_recv = self.prev_recv + 1
        return self.buffer.pop(str(self.prev_recv))


    def listener(self):
        while not self.closed:  # a later hint will explain self.closed
            try:
                data, addr = self.socket.recvfrom()
                if len(data) == 0:
                    continue
                # store the data in the receive buffer #len(data) - 5 --> - (5+16)
                print('received', unpack(str(len(data) - 21) + 'sic16s', data)[0:3])
                data_bytes, seq_num, packet_type, data_hash = unpack(str(len(data) - 21) + 'sic16s', data)
                
                #check corrupted data
                ref_hash = self.hasher(data_bytes.rstrip(b'\x00'))
                
                if ref_hash != data_hash:
                    #corrupted packet is dropped here
                    self.prev_recv = self.prev_recv - 1
                    continue
                elif str(packet_type)[2] == 'a':
                    self.ack = True
                elif str(packet_type)[2] == 'd':
                    self.socket.sendto(pack('2sic16s', b'aa', self.prev_recv, b'a', self.hasher(b'aa')), (self.dst_ip, self.dst_port))
                    data_bytes = bytes(data_bytes.decode('utf-8').rstrip('\0x00'), encoding='utf-8')
                    self.buffer[str(seq_num)] = data_bytes
                else:
                    self.socket.sendto(pack('2sic16s', b'aa', self.prev_recv, b'a', self.hasher(b'aa')), (self.dst_ip, self.dst_port))
                print('new buffer', self.buffer)
            except Exception as e:
                print("listener died!")
                print(e)

    def close(self) -> None:
        """Cleans up. It should block (wait) until the Streamer is done with all
           the necessary ACKs and retransmissions"""
        # your code goes here, especially after you add ACKs and retransmissions.
        self.ack = False
        while not self.ack:
            self.socket.sendto(pack('2sic16s', b'ff', self.seq, b'f', self.hasher(b'ff')), (self.dst_ip, self.dst_port))
            time.sleep(0.25)
        time.sleep(2)
        self.closed = True
        self.socket.stoprecv()
        return
