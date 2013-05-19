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
			print("Data from Server", len(data))
			self.startpoint.send(data)

class ProxyHandler(asynchat.async_chat):
	def __init__(self, sock, addr):
		asynchat.async_chat.__init__(self, sock)
		self.set_terminator(HTTP_TERMINATOR)
		self.socket.setblocking(1)
		self.request = None # example: ["CONNECT", "www.google.com:80", "HTTP/1.1"]
		self.method = None			# example: ['GET', 'POST', 'CONNECT']
		self.path = None			# example: '/index.html', 'www.google.com:443'
		self.http_version = None	# 'HTTP/1.1', 'HTTP1.0'
		self.headers = {}
		self.data = HTTP_EMPTY_BUFF
		self.is_headers = False
		self.is_tunneling = False # for http tunneling. use for https proxy

	def handle_read(self):
		if not self.is_tunneling:
			super(ProxyHandler, self).handle_read()
		else:
			data = self.recv(self.ac_in_buffer_size)
			if data:
				self.endpoint.socket.send(data)

	def collect_incoming_data(self, data):
		self.data += data
	
	def found_terminator(self):								 
		# print("Terminator", self.request, self.data, not self.request, not self.data)
		if not self.request and self.data:				#		request not parsed, data not empty
			self.request =  requestSplitter(self.data)
			self.method, self.path, self.version = self.request
			self.data = HTTP_EMPTY_BUFF
			print("Request received", self.request)
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

			if self.method in ['GET', 'POST']:				# HTTP	request parsed, waiting for extra headers
				if self.data:
					header = headerSplitter(self.data)
					self.headers[header[0]] = header[1]
					self.data = HTTP_EMPTY_BUFF
				else:										# HTTPS request parsed. headers parsed. create tunnel
					url = re.sub(r'^http://', '', self.path)
					domain, path = url.split('/', 1)
					self.HTTPProxy(domain, self.method, path, self.headers)
	
	def connectToRemoteHost(self, host, port):
		print("Connect to ", host, port)
		self.endpoint = TunnelHandler(self, (host, port))
		self.send(b'HTTP/1.1 200 Connection established\r\n\r\n')

	def HTTPProxy(self, domain, method, path, headers):
		try:
			conn = HTTPConnection(domain)
			conn.request(method, path)
			response = conn.getresponse()
			self.push(response.read())
			self.close_when_done()
		except Exception:
			self.HTTP404()

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

