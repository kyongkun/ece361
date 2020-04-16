#
# Copyright 2020 University of Toronto
#
# Permission is hereby granted, to use this software and associated
# documentation files (the "Software") in course work at the University
# of Toronto, or for personal use. Other uses are prohibited, in
# particular the distribution of the Software either publicly or to third
# parties.
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#

import select
import sys
from senderbase import SenderBase
from ece361.frame import Frame, unpack_data
from enum import Enum
import socket
import struct
import time

class FlowControlSlidingWindowSender(SenderBase):

	def __init__(self, file, destination, frame_size, timeout, maxseqnum, window_size, keepalive_timeout, use_flowcontrol, args):
		super().__init__(file, destination, frame_size, maxseqnum)

		self.args = args

		# Send window size
		self.send_window_size = window_size

		# Send Queue
		self.send_queue = []
		self.send_queue_byte_length = 0

		# RTT and RTO timer info
		self.rtt = None
		self.rtt_max = 0
		self.rtt_timer_status = SenderBase.TimerStatus.notsent
		self.rtt_timer_seqnum = None # the expected seqnum for calculating RTT
		self.rtt_timer = None

		self.rto_timer_status = SenderBase.TimerStatus.notsent
		self.rto_timer = None
		self.rto = timeout

		# end of file is reached for the file to send
		self.end_of_file_reached = False

		# Flow control
		self.use_flowcontrol = use_flowcontrol

		# Keep alive
		self.keepalive_timeout = keepalive_timeout
		self.keepalive_last_time = time.time()

		self.avail_receiver_window = window_size # initialized to same as the sender window size
		self.maxseqnum = maxseqnum

		# Socket
		self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)


	def _calcualte_rto_from_rtt(self, rtt):
		# Fixed RTO for now
		return self.rto


	'''
	Update the send queue based on the ACK number
	ack_seqnum: ACK sequence number
	@return: frames confirmed
	'''
	def _update_send_queue(self, ack_seqnum):
		''' remember to update the rto timer '''
		frames_confirmed = 0
		#update_queue= ack_seqnum - self.frames_delivered #% 8
		#if frames_confirmed > 0:
			#frames_confirmed + 8
		#	while update_queue > 0:
		#		self.send_queue.pop(0)
		#		update_queue -= 1
		#		frames_confirmed += 1
		self.rtt_timer_seqnum = ack_seqnum
		#	self.rto_timer = None
		frames_confirmed = ack_seqnum
		self.rto_timer_status = SenderBase.TimerStatus.sent
		#else: frames_confirmed = 0
		''' your code here '''

		return frames_confirmed

	def _recv_from(self):
		message, _ = self.sock.recvfrom(struct.calcsize('ii'))
		if message != b'':
			ack_seqnum, flow_control_window = struct.unpack("ii", message)
			return ack_seqnum, flow_control_window

	'''
	Get the frame size
	'''
	def _get_next_frame_size(self):
		return self.frame_size

	'''
	append a frame to the queue
	'''
	def _append_to_queue(self, current_frame):
		if SenderBase.ENABLE_DEBUG:
			# print("DEBUG - %s INSERTED TO BUFFER" % (current_frame.seqnum))
			print("DEBUG - %s %s INSERTED TO BUFFER" % (current_frame.seqnum, current_frame.data))
		self.send_queue.append(current_frame)
		self.send_queue_byte_length += current_frame.length

	'''
	send frame
	'''
	def _send_frame(self, frame):
		packed_frame = frame.get_frame()
		self.sock.sendto(packed_frame, self.destination)
		frame.set_sent()

	'''
	fill the buffer based on the available window size
	'''
	def fill_buffer(self, window_size):
		end_of_file_reached = False
		while self.send_queue_byte_length + self._get_next_frame_size() <= window_size:
			# fill up the sending window
			current_frame = self.get_next_frame()
			# add frame to queue
			if current_frame is not None:
				self._append_to_queue(current_frame)
			else: # End of File
				end_of_file_reached = True
				break
		return end_of_file_reached

	'''
	Calculate the sender window size
	'''
	def calc_window_size(self):
		''' calculate the sender window based on wether flow control is turned on '''
		''' return the actual window size '''
		actual_window_size = 0
		if self.use_flowcontrol:
			''' Your code here '''
			actual_window_size = self.send_window_size- self.frame_size -1
			pass
		else:
			''' Your code here'''
			actual_window_size = self.avail_receiver_window
			pass

		return actual_window_size

	'''
	send frames in queue
	max_frames: maximum number of frames to send, None means no limit
	@return: number of frame sent
	'''
	def _send_frames_in_queue(self, max_frames=None):
		''' send the frames in queue, start from the oldest unACKed frame '''
		''' you should update the rto timer here and self.frames_sent'''
		frame_sent_count=0
		recv_info = self._recv_from()
		if recv_info is None:
			return 0
		ack_seqnum, flow_control_window = recv_info
		self.rto_timer = time.time()
		while ack_seqnum < self.maxseqnum:
			recv_info = self._recv_from()
			if recv_info is not None:
				ack_seqnum, flow_control_window = recv_info        
				frame =  Frame(0,"", ack = ack_seqnum)
				_send_frame(self,frame)
				frame_sent_count = frame_sent_count + _update_send_queue(self,ack_seqnum)
			else:
				break
			
		#for i in self.send_queue:
		#	self._send_frame(self,i)
		#	self.frames_sent += 1
		#	frame_sent_count +=1
		''' your code here '''
		#self.rto_timer_status = SenderBase.TimerStatus.inflight
		return frame_sent_count

	def _check_received_data_from_socket(self):
		while True:
			waiting_sockets = [self.sock]
			readable, _, exceptional = select.select(waiting_sockets, [], waiting_sockets, 0)

			''' Step 3: Receive ack'''
			if len(readable) >= 1:
				recv_info = self._recv_from()
				if recv_info is not None:
					ack_seqnum, flow_control_window = recv_info
					if SenderBase.ENABLE_DEBUG:
						print('DEBUG - Received control message from receiver. ack seqnum: %s flow_control_window: %s' % (ack_seqnum, flow_control_window))

					frame_confirmed = self._update_send_queue(ack_seqnum)
					self.frames_delivered += frame_confirmed


					if flow_control_window != self.avail_receiver_window:
						if SenderBase.ENABLE_DEBUG:
							print('DEBUG - Updated flow control window from %s to %s' % (self.avail_receiver_window, flow_control_window))
						self.avail_receiver_window = flow_control_window


			elif len(exceptional) >= 1:
				# should never be here
				print("socket exception", file=sys.stderr)
			else:
				break

	''' Check if timeout occurs '''
	def _check_timeout(self):
		''' check if there is a timeout'''
		''' You should probably update the rto_timer_status and resend the last ACKed frame'''
		''' Only a single timer is used '''
		''' Your code here '''
	#	while  time.time() - self.rto_timer < self.rto:
		if self.rto == timeout:
			rto_timer_status = SenderBase.TimerStatus.notsent
			recv_info =self._recv_from()
			if recv_info is not None:
				ack_seqnum, flow_control_window = recv_info
				frame =  Frame(0,"", ack = ack_seqnum)
				_send_frame(self,frame)

	def __del__(self):
		if self.sock:
			self.sock.close()
		if self.fp:
			self.fp.close()


	def _arqsend(self):
		# For verbose printing
		print_time = time.time()

		# implementation of the Sliding Window ARQ protocol
		# a queue is the perfect data structure for implementing sliding window
		while True:

			''' Step 1: push frames to the send queue'''
			# initially assume receive window is infinite until the first control message is received
			self.end_of_file_reached = self.fill_buffer(self.calc_window_size())
			if self.end_of_file_reached and self.send_queue_byte_length == 0: #finished all the sending and receiving ack for all the packets
				break

			''' Step 2: Send all frames in the send queue'''

			self._send_frames_in_queue()

			''' Step 3: check timeout'''

			self._check_timeout()


			''' Step 4: check Receive data from socket'''

			self._check_received_data_from_socket()


			# Keep alive for handling the TCP stall issue
			if time.time() - self.keepalive_last_time > self.keepalive_timeout:
				keepalive_frame = Frame(0, "", ack=1)
				self._send_frame(keepalive_frame)
				self.keepalive_last_time = time.time()


			if self.args.verbose:
				if time.time() - print_time > 5:
					print("-------------------")
					print("Periodic Printing:")
					print("Send queue length: %s" % self.send_queue_byte_length)
					print("Flow control receiving window: %s" % self.avail_receiver_window)
					print("Frames sent: %s" % self.frames_sent)
					print("Frames delivered: %s" % self.frames_delivered)
					print("")
					print_time = time.time()

			# Uncomment this line if your code takes up too much, but make sure you comment it out when you submit
			# time.sleep(0.0001)


