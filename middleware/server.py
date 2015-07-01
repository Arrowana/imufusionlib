import SocketServer
import json

class MyTCPServer(SocketServer.ThreadingTCPServer):
    allow_reuse_address = True

data_queue=[{'return': 2.0124 }, {'two': 4556.4 }]

class MyTCPServerHandler(SocketServer.BaseRequestHandler):
    def handle(self):
        for i in range(10):
            try:
                if data_queue:
                    #data = json.loads(self.request.recv(1024).strip())
                    # process the data, i.e. print it:
                    print data_queue[0]
                    # send some 'ok' back
                    self.request.sendall(json.dumps(data_queue[0]))
                    data_queue.pop(0)
            except Exception, e:
                print "Exception wile receiving message: ", e

server = MyTCPServer(('0.0.0.0', 13373), MyTCPServerHandler)
server.serve_forever()