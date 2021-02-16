# do not import anything else from loss_socket besides LossyUDP
from lossy_socket import LossyUDP
# do not import anything else from socket except INADDR_ANY
from socket import INADDR_ANY
from struct import *
import time
import hashlib
from concurrent.futures.thread import ThreadPoolExecutor


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
        self.hash = hashlib.md5()

    def get_hash(self, data:bytes):
        self.hash.update(data)
        return self.hash.digest(), self.hash.digest_size

    def send_helper(self, data_bytes:bytes) -> int:
        length = len(data_bytes)
        max_packet = int(1300 - calcsize('ic'))
        packets_sent = 0
        if length <= max_packet:
            # print('send size', len(pack(str(length) + 'sic', data_bytes, self.seq, b'd')))
            self.socket.sendto(pack(str(length) + 'sic', data_bytes, self.seq, b'd'), (self.dst_ip, self.dst_port))
            self.seq = self.seq + 1
            packets_sent += 1
        else:
            chunk = max_packet
            while chunk < length:
                # print('send size', len(pack(str(max_packet) + 'sic', data_bytes[chunk - max_packet:chunk], self.seq, b'd')))
                self.socket.sendto(pack(str(max_packet) + 'sic', data_bytes[chunk - max_packet:chunk], self.seq, b'd'), (self.dst_ip, self.dst_port))
                self.seq = self.seq + 1
                packets_sent += 1
                chunk = chunk + max_packet
            # print('send size', len(pack(str(max_packet) + 'sic', data_bytes[chunk - max_packet:], self.seq, b'd')))
            self.socket.sendto(pack(str(max_packet) + 'sic', data_bytes[chunk - max_packet:], self.seq, b'd'), (self.dst_ip, self.dst_port))
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
                continue
            else:
                break
        self.ack = False




    def recv(self) -> bytes:
        """Blocks (waits) if no data is ready to be read from the connection."""
        # your code goes here!  The code below should be changed!
        
        # this sample code just calls the recvfrom method on the LossySocket
        while not str(self.prev_recv + 1) in self.buffer:
            time.sleep(0.005)
            continue

        print('found it in here', self.buffer)
        self.prev_recv = self.prev_recv + 1
        return self.buffer.pop(str(self.prev_recv))

        # data, addr = self.socket.recvfrom()
        # print(unpack(str(len(data) - 4) + 'si', data))
        # data_bytes, seq_num = unpack(str(len(data) - 4) + 'si', data)
        # data_bytes = bytes(data_bytes.decode('utf-8').rstrip('\0x00'), encoding='utf-8')
        # print('looking for', self.prev_recv + 1)
        # if seq_num == self.prev_recv + 1:
        #     self.prev_recv = self.prev_recv + 1
        #     print('received it')
        #     return data_bytes
        # else:
        #     self.buffer[str(seq_num)] = data_bytes
        #     if str(self.prev_recv + 1) in self.buffer:
        #         print('didnt receive it, but found it in here', self.buffer)
        #         self.prev_recv = self.prev_recv + 1
        #         return self.buffer.pop(str(self.prev_recv))
        #     print('did not find it in here', self.buffer)
        #     return self.recv()

    def listener(self):
        while not self.closed:  # a later hint will explain self.closed
            try:
                data, addr = self.socket.recvfrom()
                if len(data) == 0:
                    continue
                # store the data in the receive buffer
                print('received', unpack(str(len(data) - 5) + 'sic', data))
                data_bytes, seq_num, packet_type = unpack(str(len(data) - 5) + 'sic', data)
                if str(packet_type)[2] == 'a':
                    self.ack = True
                elif str(packet_type)[2] == 'd':
                    self.socket.sendto(pack('2sic', b'aa', self.seq, b'a'), (self.dst_ip, self.dst_port))
                    data_bytes = bytes(data_bytes.decode('utf-8').rstrip('\0x00'), encoding='utf-8')
                    self.buffer[str(seq_num)] = data_bytes
                else:
                    self.socket.sendto(pack('2sic', b'aa', self.seq, b'a'), (self.dst_ip, self.dst_port))
            except Exception as e:
                print("listener died!")
                print(e)

    def close(self) -> None:
        """Cleans up. It should block (wait) until the Streamer is done with all
           the necessary ACKs and retransmissions"""
        # your code goes here, especially after you add ACKs and retransmissions.
        self.ack = False
        while not self.ack:
            self.socket.sendto(pack('2sic', b'ff', self.seq, b'f'), (self.dst_ip, self.dst_port))
            time.sleep(0.25)
        time.sleep(2)
        self.closed = True
        self.socket.stoprecv()
        return
