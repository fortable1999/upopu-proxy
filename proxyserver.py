#!/usr/bin/env python3

import asynchat, asyncore, socket, sys, re, ssl, time

if sys.version[0] == '3':
	from http.client import HTTPConnection, HTTPSConnection
	HTTP_TERMINATOR = b'\r\n'
	HTTP_EMPTY_BUFF = b''
	requestSplitter = lambda s: s.decode('utf-8').split(None, 2)
	headerSplitter = lambda s: s.decode('utf-8').split(': ', 1)
	HTTP404MSG = b"HTTP/1.1 404 Not Found\r\n"
	hostportSplitter = lambda s: s.decode('utf-8').split(':', 1)
	HTTP1_1 = b'HTTP/1.0'
	HTTP1_1 = b'HTTP/1.1'
	HTTP_RN = b'\r\n'
	HTTP_0RN = b'0\r\n'
	HTTP_RESPONSE = lambda version, status, reason: bytes("HTTP/1.%s %d %s\r\n" % (str(version)[1], status, reason), 'utf-8') 
	HTTP_HEADER = lambda item: bytes("%s: %s\r\n" % item, 'utf-8')
else:
	from httplib import HTTPConnection, HTTPSConnection
	HTTP_TERMINATOR = '\r\n'
	HTTP_EMPTY_BUFF = ''
	requestSplitter = lambda s: s.split(None, 2)
	headerSplitter = lambda s: s.split(': ', 1)
	HTTP404MSG = "HTTP/1.1 404 Not Found\r\n"
	hostportSplitter = lambda s: s.split(':', 1)
	HTTP1_1 = 'HTTP/1.1'
	HTTP1_1 = 'HTTP/1.0'
	HTTP_RN = '\r\n'
	HTTP_0RN = '0\r\n'
	HTTP_RESPONSE = lambda version, status, reason: "HTTP/1.%s %d %s\r\n" % (str(version)[1], status, reason)
	HTTP_HEADER = lambda item: "%s: %s\r\n" % item

class TunnelHandler(asyncore.dispatcher):
	# get packet from endpoint, send to startpoint.
	def __init__(self, startpoint, endpoint_addr):
		asyncore.dispatcher.__init__(self)
		self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
		self.socket.setblocking(1)
		self.connect(endpoint_addr)
		self.startpoint = startpoint
	
	def handle_read(self):
		data = self.recv(4096)
		if data:
			self.startpoint.send(data)

class ProxyHandler(asynchat.async_chat):
	def __init__(self, sock, addr):
		asynchat.async_chat.__init__(self, sock)
		self.reset_status()
		self.socket.setblocking(1)
	
	def reset_status(self):
		self.set_terminator(HTTP_TERMINATOR)
		self.request = None # example: ["CONNECT", "www.google.com:80", "HTTP/1.1"]
		self.method = None			# example: ['GET', 'POST', 'CONNECT']
		self.path = None			# example: '/index.html', 'www.google.com:443'
		self.version = None	# 'HTTP/1.1', 'HTTP1.0'
		self.headers = {}
		self.data = HTTP_EMPTY_BUFF
		self.is_headers = False
		self.is_tunneling = False # for http tunneling. use for https proxy
		self.is_posting = False

	def handle_read(self):
		if not self.is_tunneling: # use asyncore default handle_read method
			if sys.version[0] == '2':
				asynchat.async_chat.handle_read(self) # for python 2 old-style 
			else:
				super().handle_read()
		else:
			data = self.recv(self.ac_in_buffer_size)
			if data:
				self.endpoint.socket.send(data)

	def collect_incoming_data(self, data):
		if self.method and self.method.lower() == 'post' and self.is_posting: 
			self.data += data
			self.data += HTTP_RN

			url = re.sub(r'^http://', '', self.path)
			domain, path = url.split('/', 1)
			path = '/' + path
			self.HTTPProxy(domain, self.method, path, self.headers, data)
			self.reset_status()

		else:
			self.data += data
	
	def found_terminator(self):								 
		if not self.request and self.data:				#		request not parsed, data not empty
			self.request =  requestSplitter(self.data)
			self.method, self.path, self.version = self.request
			self.data = HTTP_EMPTY_BUFF
		else:
			if self.method in ['CONNECT']:					# HTTPS	request parsed, waiting for extra headers
				if self.data:
					header = headerSplitter(self.data)
					self.headers[header[0]] = header[1]
					self.data = HTTP_EMPTY_BUFF
				else:										# HTTPS request parsed. headers parsed. create tunnel
					i = self.path.find(':')
					if i == -1:
						host, port = self.path, 80
					else:
						host, port = self.path[:i], int(self.path[i+1:])
					self.connectToRemoteHost(host, port)
					self.is_tunneling = True
			else:											# HTTP	request parsed, waiting for extra headers
				if self.data:
					header = headerSplitter(self.data)
					self.headers[header[0]] = header[1]
					self.data = HTTP_EMPTY_BUFF
				else:										# HTTP request parsed. headers parsed. create tunnel
					if self.method and self.method.lower() == 'post' and not self.is_posting:
						self.data = HTTP_EMPTY_BUFF
						self.is_posting = True
						self.is_tunneling = True
					else:
						url = re.sub(r'^http://', '', self.path)
						domain, path = url.split('/', 1)
						path = '/' + path
						self.HTTPProxy(domain, self.method, path, self.headers)
						self.reset_status()
	
	def connectToRemoteHost(self, host, port):
		self.send(b'HTTP/1.1 200 Connection established\r\n\r\n')
		print("%s %s %s:%d" % (self.version, self.method, host, port))
		self.endpoint = TunnelHandler(self, (host, port))

	def HTTPProxy(self, domain, method, path, headers, post_data = None):
		conn = HTTPConnection(domain)
		conn.request(method, path, post_data, headers)
		response = conn.getresponse()
		response_headers = response.getheaders()
		data = response.read()
		if 'Content-Length' not in dict(response_headers).keys() and 'content-length' not in dict(response_headers).keys():
			response_headers.append(('Content-Length', len(data)))

		for item in response_headers:
			if item[0].lower() == 'transfer-encoding' and item[1].lower() ==  'chunked':
				response_headers[response_headers.index(item)] = ('Transfer-Encoding', 'text/html; charset=utf-8')
		
		self.push(HTTP_RESPONSE(response.version, response.status, response.reason))
		for item in response_headers:
			self.push(HTTP_HEADER(item))
		self.push(HTTP_RN)
		self.push(data)
		self.push(HTTP_RN)
		print("%s %s %s %d %s %d" % (self.version, method, path, response.status, response.reason, len(data)))

		for item in response_headers:
			if item[0].lower() == 'connection' and item[1].lower() == 'keep-alive':
				self.push(HTTP_0RN + HTTP_RN)
				return 
		self.close_when_done()

	def HTTP404(self):
		self.push(HTTP404MSG)
		self.close_when_done()
	
class Server(asyncore.dispatcher):
	def __init__(self):
		asyncore.dispatcher.__init__(self)
		self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
		self.bind(('localhost', int(sys.argv[1])))
		self.listen(5)
	
	def handle_accept(self):
		conn, addr = self.accept()
		ProxyHandler(conn, addr)
		
server = Server()
asyncore.loop()

