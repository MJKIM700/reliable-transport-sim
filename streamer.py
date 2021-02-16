# do not import anything else from loss_socket besides LossyUDP
from lossy_socket import LossyUDP
# do not import anything else from socket except INADDR_ANY
from socket import INADDR_ANY
from struct import *
import time
from datetime import datetime, timedelta
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
        self.sent = dict()
        self.received = []
        self.prev_recv = -1
        self.closed = False
        self.ack = False
        executor = ThreadPoolExecutor(max_workers=1)
        executor.submit(self.listener)

    def hasher(self, incoming: bytes) -> bytes:
        h = hashlib.md5(incoming).digest()
        return h

    def send_helper(self, data_bytes:bytes, retransmit, retransmit_seq=-1):
        length = len(data_bytes)
        #i'm changing the packet structure to fit the hash [16 byte s for storing hash]
        max_packet = int(1400 - calcsize('ic16s'))

        if length <= max_packet:
            #print(calcsize('sic16s'))
            #print('send size', len(pack(str(length) + 'sic16s', data_bytes, self.seq, b'd', self.hasher(data_bytes))))



            if not retransmit:
                self.socket.sendto(
                    pack(str(length) + 'sic16s', data_bytes, self.seq, b'd', self.hasher(pack(str(length) + 'sic',
                                                                                              data_bytes, self.seq,
                                                                                              b'd'))),
                                                                            (self.dst_ip, self.dst_port))
                self.sent[str(self.seq)] = data_bytes
                self.seq = self.seq + 1
            #     self.wait_ack(data_bytes)
            else:
                self.socket.sendto(
                    pack(str(length) + 'sic16s', data_bytes, retransmit_seq, b'd', self.hasher(pack(str(length) + 'sic',
                                                                                              data_bytes, retransmit_seq,
                                                                                              b'd'))),
                    (self.dst_ip, self.dst_port))
                print('resending', data_bytes)

        else:
            chunk = max_packet
            while chunk < length:
                # print('send size', len(pack(str(max_packet) + 'sic', data_bytes[chunk - max_packet:chunk], self.seq, b'd')))


                if not retransmit:
                #     self.wait_ack(data_bytes[chunk - max_packet:chunk])
                    self.socket.sendto(pack(str(max_packet) + 'sic16s', data_bytes[chunk - max_packet:chunk], self.seq, b'd',self.hasher(
                                    pack(str(max_packet) + 'sic', data_bytes[chunk - max_packet:chunk], self.seq, b'd'))), (self.dst_ip, self.dst_port))
                    self.sent[str(self.seq)] = data_bytes[chunk - max_packet:chunk]
                self.seq = self.seq + 1
                chunk = chunk + max_packet
            # print('send size', len(pack(str(max_packet) + 'sic', data_bytes[chunk - max_packet:], self.seq, b'd')))


            if not retransmit:
            #     self.wait_ack(data_bytes[chunk - max_packet:])
                self.socket.sendto(pack(str(max_packet) + 'sic16s', data_bytes[chunk - max_packet:], self.seq, b'd',
                                    self.hasher(pack(str(max_packet) + 'sic',
                                                     data_bytes[chunk - max_packet:], self.seq, b'd'))),
                               (self.dst_ip, self.dst_port))
                self.sent[str(self.seq)] = data_bytes[chunk - max_packet:]
            self.seq = self.seq + 1

    def wait_ack(self, data_bytes:bytes):
        while not self.ack:
            time.sleep(0.25)
            print(self.ack)
            if not self.ack:
                self.send_helper(data_bytes, True)
                print("sending {} again bc dropped".format(data_bytes))
                continue
            else:
                break
        self.ack = False

    def go_back(self):
        while len(self.received) == 0:
            continue
        while len(self.sent) > 0:
            for acked in self.received:
                if str(acked) in self.sent:
                    self.sent.pop(str(acked))
            for data in self.sent.items():
                if int(data[0]) not in self.received:
                    self.send_helper(data[1], True, retransmit_seq=int(data[0]))
        self.received.clear()
        self.sent.clear()


    def send(self, data_bytes: bytes) -> None:
        """Note that data_bytes can be larger than one packet."""
        # Your code goes here!  The code below should be changed!
        window_size = 100
        if len(self.sent) > window_size:
            self.go_back()
        self.send_helper(data_bytes, False)






    def recv(self) -> bytes:
        """Blocks (waits) if no data is ready to be read from the connection."""
        # your code goes here!  The code below should be changed!

        # this sample code just calls the recvfrom method on the LossySocket
        while not str(self.prev_recv + 1) in self.buffer:
            print("Looking for", self.prev_recv + 1)
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
                ref_hash = self.hasher(pack(str(len(data) - 21) + 'sic', data_bytes, seq_num, packet_type))
                self.received.append(seq_num)

                if ref_hash != data_hash:
                    #corrupted packet is dropped here
                    continue
                elif str(packet_type)[2] == 'a':
                    print('ack received', self.ack)
                    self.received.append(seq_num)
                elif str(packet_type)[2] == 'd':
                    self.socket.sendto(pack('2sic16s', b'aa', seq_num, b'a', self.hasher(pack('2sic', b'aa', self.prev_recv, b'a'))), (self.dst_ip, self.dst_port))
                    data_bytes = bytes(data_bytes.decode('utf-8').rstrip('\0x00'), encoding='utf-8')
                    self.buffer[str(seq_num)] = data_bytes
                else:
                    self.socket.sendto(pack('2sic16s', b'aa', seq_num, b'a', self.hasher(pack('2sic', b'aa', seq_num, b'a'))), (self.dst_ip, self.dst_port))
                print('new buffer', self.buffer)
            except Exception as e:
                print("listener died!")
                print(e)

    def close(self) -> None:
        """Cleans up. It should block (wait) until the Streamer is done with all
           the necessary ACKs and retransmissions"""
        # your code goes here, especially after you add ACKs and retransmissions.
        self.socket.sendto(pack('2sic16s', b'ff', self.seq, b'f', self.hasher(pack('2sic', b'ff', self.seq, b'f'))), (self.dst_ip, self.dst_port))
        self.sent[str(self.seq)] = b'ff'
        time.sleep(5)
        if len(self.sent) > 0:
            self.go_back()
        time.sleep(2)
        self.received.clear()
        self.closed = True
        self.socket.stoprecv()
        return
