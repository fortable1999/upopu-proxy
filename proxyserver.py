import asynchat, asyncore, socket, sys, httplib, re

class HTTPHandler(asynchat.async_chat):
	def __init__(self, sock, addr):
		asynchat.async_chat.__init__(self, sock)
		self.set_terminator('\r\n')
		self.request = None # example: ["GET", "/", "HTTP/1.1"]
		self.headers = {}
		self.data = ""
		self.is_payload = False
	
	def collect_incoming_data(self, data):
		self.data += data
	
	def found_terminator(self):
		if self.data == "" and not self.request:
			print "RequestError"
			self.HTTP404()
		if not self.request:
			self.request = self.data.split(None, 2)
			self.data = ""
		elif self.data == "":
			if not re.match(r'^(http://|https://)', self.request[1]):
				print "ProtocolError"
				self.HTTP404()
			if re.match(r'^https', self.request[1]):
				protocol = "https"
			else:
				protocol = 'http'
			# print self.request
			pattern = re.compile(r'(http://|https://)')
			host_path = re.sub(pattern, "", self.request[1]).split("/", 1)
			if len(host_path) < 2:
				path = "/"
			else:
				path = '/' + host_path[1]
			host = host_path[0]
			self.HTTPProxy(protocol, host, self.request[0], path, self.headers)
		else:
			header = self.data.split(": ", 1)
			self.headers[header[0]] = header[1]
			self.data = ""
	
	def HTTP404(self):
		# print "Raise 404"
		self.push("HTTP/1.1 404 Not Found\r\n")
		self.close_when_done()
	
	def HTTPProxy(self, protocol, domain, method, path, headers):
		try:
			print method, protocol, domain, path
			if protocol == "http":
				conn = httplib.HTTPConnection(domain)
			else:
				conn = httplib.HTTPSConnection(domain)

			conn.request(method, path)
			response = conn.getresponse()
			# print "%s %s" % ( response.version, response.status)
			self.push(response.read())
			self.close_when_done()
		except Exception, e:
			print Exception.message, e
			self.HTTP404()

	
class Server(asyncore.dispatcher):
	def __init__(self):
		asyncore.dispatcher.__init__(self)
		self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
		self.bind(('', int(sys.argv[1])))
		self.listen(5)
	
	def handle_accept(self):
		conn, addr = self.accept()
		HTTPHandler(conn, addr)

		
server = Server()
asyncore.loop()




