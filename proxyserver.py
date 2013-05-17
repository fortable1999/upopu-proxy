import asynchat, asyncore, socket, sys, re

if sys.version[0] == '3':
	from http.client import HTTPConnection, HTTPSConnection
	HTTP_TERMINATOR = b'\r\n'
	HTTP_EMPTY_BUFF = b''
	requestSplitter = lambda s: s.decode('utf-8').split(None, 2)
	headerSplitter = lambda s: s.decode('utf-8').split(': ', 1)
	HTTP404MSG = b"HTTP/1.1 404 Not Found\r\n"
else:
	from httplib import HTTPConnection, HTTPSConnection
	HTTP_TERMINATOR = '\r\n'
	HTTP_EMPTY_BUFF = ''
	requestSplitter = lambda s: s.split(None, 2)
	headerSplitter = lambda s: s.split(': ', 1)
	HTTP404MSG = "HTTP/1.1 404 Not Found\r\n"

# class HTTPSHandler(asynchat.async_chat):
# 	def __init__(self, conn, addr):
# 		asynchat.async_chat.__init__(self, conn)
# 
# 	
# 	def collect_incoming_data(self, data):
# 		pass


class HTTPHandler(asynchat.async_chat):
	def __init__(self, sock, addr):
		asynchat.async_chat.__init__(self, sock)
		self.set_terminator(HTTP_TERMINATOR)
		self.request = None # example: ["GET", "/", "HTTP/1.1"]
		self.headers = {}
		self.data = HTTP_EMPTY_BUFF
		self.is_payload = False
	
	def collect_incoming_data(self, data):
		self.data += data
	
	def found_terminator(self):
		if self.data == HTTP_EMPTY_BUFF and not self.request:
			print("RequestError")
			self.HTTP404()
		if not self.request:
			# self.request = self.data.decode('utf-8').split(None, 2)
			self.request = requestSplitter(self.data)
			self.data = HTTP_EMPTY_BUFF
		elif self.data == HTTP_EMPTY_BUFF:
			if not re.match(r'^(http://|https://)', self.request[1]):
				print("ProtocolError")
				self.HTTP404()
			if re.match(r'^https', self.request[1]):
				protocol = "https"
			else:
				protocol = 'http'
			# print(self.request)
			pattern = re.compile(r'(http://|https://)')
			host_path = re.sub(pattern, "", self.request[1]).split("/", 1)
			if len(host_path) < 2:
				path = "/"
			else:
				path = '/' + host_path[1]
			host = host_path[0]
			self.HTTPProxy(protocol, host, self.request[0], path, self.headers)
		else:
			header = headerSplitter(self.data)
			self.headers[header[0]] = header[1]
			self.data = HTTP_EMPTY_BUFF
	
	def HTTP404(self):
		# print("Raise 404")
		self.push(HTTP404MSG)
		self.close_when_done()
	
	def HTTPProxy(self, protocol, domain, method, path, headers):
		try:
			print(method, protocol, domain, path)
			if protocol == "http":
				conn = HTTPConnection(domain)
			else:
				conn = HTTPSConnection(domain)

			conn.request(method, path)
			response = conn.getresponse()
			self.push(response.read())
			self.close_when_done()
		# except Exception as e:
		except Exception:
			self.HTTP404()

	
class Server(asyncore.dispatcher):
	def __init__(self):
		asyncore.dispatcher.__init__(self)
		self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
		self.bind(('localhost', int(sys.argv[1])))
		self.listen(5)
	
	def handle_accept(self):
		conn, addr = self.accept()
		HTTPHandler(conn, addr)

		
server = Server()
asyncore.loop()

