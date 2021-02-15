# do not import anything else from loss_socket besides LossyUDP
from lossy_socket import LossyUDP
# do not import anything else from socket except INADDR_ANY
from socket import INADDR_ANY
from struct import *


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

    def send(self, data_bytes: bytes) -> None:
        """Note that data_bytes can be larger than one packet."""
        # Your code goes here!  The code below should be changed!
        length = len(data_bytes)
        max_packet = int(1472 - calcsize('i'))
        if length <= max_packet:
            print('send size', len(pack(str(length) + 'si', data_bytes, self.seq)), 'sending:', data_bytes)
            self.socket.sendto(pack(str(length) + 'si', data_bytes, self.seq), (self.dst_ip, self.dst_port))
            self.seq = self.seq + 1
        else:
            chunk = max_packet
            while chunk < length:
                print('send size', len(pack(str(max_packet) + 'si', data_bytes[chunk - max_packet:chunk], self.seq)))
                self.socket.sendto(pack(str(max_packet) + 'si', data_bytes[chunk - max_packet:chunk], self.seq), (self.dst_ip, self.dst_port))
                self.seq = self.seq + 1
                chunk = chunk + max_packet
            print('send size', len(pack(str(max_packet) + 'si', data_bytes[chunk - max_packet:], self.seq)))
            self.socket.sendto(pack(str(max_packet) + 'si', data_bytes[chunk - max_packet:], self.seq), (self.dst_ip, self.dst_port))
            self.seq = self.seq + 1



    def recv(self) -> bytes:
        """Blocks (waits) if no data is ready to be read from the connection."""
        # your code goes here!  The code below should be changed!
        
        # this sample code just calls the recvfrom method on the LossySocket
        if str(self.prev_recv + 1) in self.buffer:
            print('didnt receive it, but found it in here', self.buffer)
            self.prev_recv = self.prev_recv + 1
            return self.buffer.pop(str(self.prev_recv))
        data, addr = self.socket.recvfrom()
        # For now, I'll just pass the full UDP payload to the app
        print(unpack(str(len(data) - 4) + 'si', data))
        data_bytes, seq_num = unpack(str(len(data) - 4) + 'si', data)
        data_bytes = bytes(data_bytes.decode('utf-8').rstrip('\0x00'), encoding='utf-8')
        print('looking for', self.prev_recv + 1)
        if seq_num == self.prev_recv + 1:
            self.prev_recv = self.prev_recv + 1
            print('received it')
            return data_bytes
        else:
            self.buffer[str(seq_num)] = data_bytes
            if str(self.prev_recv + 1) in self.buffer:
                print('didnt receive it, but found it in here', self.buffer)
                self.prev_recv = self.prev_recv + 1
                return self.buffer.pop(str(self.prev_recv))
            print('did not find it in here', self.buffer)
            return self.recv()


    def close(self) -> None:
        """Cleans up. It should block (wait) until the Streamer is done with all
           the necessary ACKs and retransmissions"""
        # your code goes here, especially after you add ACKs and retransmissions.
        pass
