from socket import *
import socket
import time
import sys
import logging
import multiprocessing
from concurrent.futures import ThreadPoolExecutor
from http import HttpServer
import select

class BackendList:
	def __init__(self):
		self.servers=[]
		self.servers.append(('127.0.0.1',8889))
		self.servers.append(('127.0.0.1',8890))
		self.servers.append(('127.0.0.1',8891))
#		self.servers.append(('127.0.0.1',9005))
		self.current=0
	def getserver(self):
		s = self.servers[self.current]
		print(s)
		self.current=self.current+1
		if (self.current>=len(self.servers)):
			self.current=0
		return s




def ProcessTheClient(connection, address, backend_sock):
    try:
        sockets = [connection, backend_sock]
        while True:
            readable, _, exceptional = select.select(sockets, [], sockets, 1)
            if exceptional:
                break
            for sock in readable:
                try:
                    data = sock.recv(4096)
                    if not data:
                        return
                    if sock is connection:
                        backend_sock.sendall(data)
                    else:
                        connection.sendall(data)
                except Exception as e:
                    logging.warning(f"Socket error: {e}")
                    return
    except Exception as ee:
        logging.warning(f"error {str(ee)}")
    finally:
        connection.close()
        backend_sock.close()
    return



def Server():
	the_clients = []
	my_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	my_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
	backend = BackendList()

	my_socket.bind(('0.0.0.0', 44444))
	my_socket.listen(1)

	with ThreadPoolExecutor(20) as executor:
		while True:
				connection, client_address = my_socket.accept()
				backend_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
				backend_sock.settimeout(1)
				backend_address = backend.getserver()
				logging.warning(f"{client_address} connecting to {backend_address}")
				try:
					backend_sock.connect(backend_address)
					fut = executor.submit(ProcessTheClient, connection, client_address, backend_sock)
					the_clients.append(fut)
				except Exception as err:
					logging.error(err)
					connection.close()
					backend_sock.close()
					pass





def main():
	Server()

if __name__=="__main__":
	main()
