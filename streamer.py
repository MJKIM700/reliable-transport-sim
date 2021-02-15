# do not import anything else from loss_socket besides LossyUDP
from lossy_socket import LossyUDP
# do not import anything else from socket except INADDR_ANY
from socket import INADDR_ANY
from struct import *
from concurrent.futures import *
import time
import sys

class Streamer:
    def __init__(self, dst_ip, dst_port,
                 src_ip=INADDR_ANY, src_port=0):
        """Default values listen on all network interfaces, chooses a random source port,
           and does not introduce any simulated packet loss."""
        self.socket = LossyUDP()
        self.socket.bind((src_ip, src_port))
        self.dst_ip = dst_ip
        self.dst_port = dst_port
        #Part 2 Reordering
        self.seqnum = 0
        self.rcvdnum = 0
        #dict with key=seq#, val=packet
        self.recvbuffer = {}
        #Part 3A
        self.closed = 0
        executor = ThreadPoolExecutor(max_workers=1)
        executor.submit(self.listener)
        self.ack = 0 #0 is data, 1 is ack
        self.fin = 0 #0 is normal, 1 is fin
        self.state = 0 #0 is recv, 1 is send


    #manages the receive buffer
    def listener(self):
        while not self.closed: # a later hint will explain self.closed
            try:
                # store the data in the receive buffer
                data, addr = self.socket.recvfrom()
                msg_size = len(data) - 6
                incoming = unpack('ibb{}s'.format(msg_size), data)

                #check pkt ack
                if incoming[1] == 0:
                    #send an ACK to sender
                    print("ack for {} sent".format(incoming[3]))
                    self.socket.sendto(self.headify(b'',1), (self.dst_ip, self.dst_port))
                elif incoming[1] == 1:
                    #let send know it can proceed
                    self.ack = 1
                #if fin
                if incoming[2] == 0:
                    #ordinary packet
                    pass
                elif incoming[2] == 1:
                    self.fin = 1
                
                #save to buffer
                self.recvbuffer[incoming[0]] = incoming[3] 
                

            except Exception as e:
                print("listener died!")
                print(e)
    
    def headify(self, data_bytes, ack=0, fin=0):
            """ returns packed version of data with seq num and ACK bit
                default not ack, if ack, ack=1"""
            #Part 1 Chunking
            if len(data_bytes) > 1472:
                i = 0
                chunks = []    #leave 4B for seqnum, 1B for ACK, 1B for FIN (1472-4-1-1 = 1466)
                for i in range(0, len(data_bytes), 1466): #each msg has 1466 size
                    chunks.append(pack('ibb{}s'.format(1467), self.seqnum, data_bytes[i:i+1466]))
                    self.seqnum += 1
                #handle remaining part 
                chunks.append(pack('ibb{}s'.format(len(data_bytes[i:])), self.seqnum, ack, fin, data_bytes[i:]))
                self.seqnum += 1
                return chunks
            else:
                pkt = pack('ibb{}s'.format(len(data_bytes)), self.seqnum, ack, fin, data_bytes)
                self.seqnum += 1
                return pkt
    
    # 0.25s timer for acks, repeats msg if not acked
    def wait_ack(self, message):
        start_time = time.time()
        while True:
            cur_time = time.time()
            if not self.ack: #didn't get ack
                time.sleep(0.001)
                #print('stuck here')
                if (cur_time - start_time) > 0.25:
                    print("lost packet so resent packet: {}".format(message))
                    self.send_msg(message)
                    #wipe time
                    start_time = time.time()
            elif (cur_time - start_time) > 0.25:
                print("resent packet")
                self.send_msg(message)
                #wipe time
                start_time = time.time()
            else: #got an ack
                self.ack = 0
                break
    
    #assumes message has been headed
    def send_msg(self, message):
        if message is list:
            #was split into chunks
            for pkt in message:
                self.socket.sendto(pkt, (self.dst_ip, self.dst_port))
        else:
            self.socket.sendto(message, (self.dst_ip, self.dst_port))
            print("sent")

        
    def send(self, data_bytes: bytes) -> None:
        """Note that data_bytes can be larger than one packet."""   
        #reset
        if self.state != 1:
            self.state = 1
            self.seqnum = 0
            self.rcvdnum = 0

        #normally just sending data
        headed = self.headify(data_bytes)
    
        self.send_msg(headed)
        self.wait_ack(headed)


    def recv(self) -> bytes:
        """Blocks (waits) if no data is ready to be read from the connection."""
        #reset
        if self.state != 0:
            self.state = 0
            self.seqnum = 0
            self.rcvdnum = 0

        print("my seq num right now!!!!!!!!!!!!! {}".format(self.seqnum))
        print("recvd number: {}".format(self.rcvdnum))
        while not self.recvbuffer or self.rcvdnum not in self.recvbuffer:
            #if buffer empty, wait
            time.sleep(0.01)
        
        #buffer is not empty

        if self.rcvdnum in self.recvbuffer:
            to_send = self.recvbuffer.pop(self.rcvdnum)
            print("sending {}".format(to_send))
            self.rcvdnum += 1
            print(to_send)
            #dropped packet led to none type
            if to_send is None:
                to_send = self.headify(b'', 0, 0)
            return to_send#.rstrip(b'\x00')

        #return b' ' #.rstrip(b'\x00')

    def close(self) -> None:
        """Cleans up. It should block (wait) until the Streamer is done with all
           the necessary ACKs and retransmissions"""
        
        #send a fin
        fin_msg = self.headify(b' ', 0, 1)
        self.socket.sendto(fin_msg, (self.dst_ip, self.dst_port))
        self.wait_ack(fin_msg)
        while not self.fin:
            #what if we never get a fin from the other side? i think we will...
            time.sleep(0.01)
        #self.fin has been set to 1, we break out of while
        time.sleep(2)
        self.closed = True
        self.socket.stoprecv()
        return