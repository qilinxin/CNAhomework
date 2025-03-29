# Include the libraries for socket and system calls
import socket
import sys
import os
import argparse
import re

# 1MB buffer size
BUFFER_SIZE = 1000000

# Get the IP address and Port number to use for this web proxy server
parser = argparse.ArgumentParser()
parser.add_argument('hostname', help='the IP Address Of Proxy Server')
parser.add_argument('port', help='the port number of the proxy server')
args = parser.parse_args()
print("args-----", args)
proxyHost = args.hostname
proxyPort = int(args.port)

# Create a server socket, bind it to a port and start listening
try:
    serverSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    serverSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    print('Created socket')
except:
    print('Failed to create socket')
    sys.exit()

try:
    serverSocket.bind((proxyHost, proxyPort))
    print('Port is bound')
except:
    print('Port is already in use')
    sys.exit()

try:
    serverSocket.listen(10)
    print('Listening to socket')
except:
    print('Failed to listen')
    sys.exit()

# continuously accept connections
while True:
    print('Waiting for connection...')
    clientSocket = None

    # Accept connection from client and store in the clientSocket
    try:
        clientSocket, addr = serverSocket.accept()
        print('Received a connection')
    except:
        print('Failed to accept connection')
        sys.exit()

    # Get HTTP request from client and store it in message_bytes
    message_bytes = clientSocket.recv(BUFFER_SIZE)
    message = message_bytes.decode('utf-8')
    print('Received request:')
    print('< ' + message)

    # Extract the method, URI and version of the HTTP client request
    requestParts = message.split()
    method = requestParts[0]
    URI = requestParts[1]
    version = requestParts[2]

    print('Method:\t\t' + method)
    print('URI:\t\t' + URI)
    print('Version:\t' + version)
    print('')

    # Get the requested resource from URI
    # Remove http protocol from the URI
    URI = re.sub('^(/?)http(s?)://', '', URI, count=1)

    # Remove parent directory changes - security
    URI = URI.replace('/..', '')

    # Split hostname from resource name
    resourceParts = URI.split('/', 1)
    hostname = resourceParts[0]
    resource = '/'
    if len(resourceParts) == 2:
        resource = resource + resourceParts[1]

    print('Requested Resource:\t' + resource)

    # Define cache file locations: one for header and one for body
    cacheLocation_hdr = './' + hostname + resource + ".hdr"
    cacheLocation_body = './' + hostname + resource + ".body"
    if cacheLocation_hdr.endswith('/.hdr'):
        cacheLocation_hdr = cacheLocation_hdr.replace('/.hdr', '/default.hdr')
    if cacheLocation_body.endswith('/.body'):
        cacheLocation_body = cacheLocation_body.replace('/.body', '/default.body')

    print('Cache header location:\t' + cacheLocation_hdr)
    print('Cache body location:\t' + cacheLocation_body)

    # Check if resource is in cache
    try:
        if os.path.isfile(cacheLocation_hdr) and os.path.isfile(cacheLocation_body):
            with open(cacheLocation_hdr, "rb") as f_hdr:
                cached_headers = f_hdr.read()
            with open(cacheLocation_body, "rb") as f_body:
                cached_body = f_body.read()
            cached_response = cached_headers + b"\r\n\r\n" + cached_body
            print('Cache hit! Loading from cache files:')
            print('> Headers:', cached_headers.decode('utf-8', errors='ignore'))
            print('> Body: <binary data, length {}>'.format(len(cached_body)))
            clientSocket.sendall(cached_response)
        else:
            # cache miss, continue to get resource from origin server
            raise FileNotFoundError
    except:
        # cache miss: Get resource from origin server
        originServerSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        originServerSocket.settimeout(10)
        print('Connecting to:\t\t' + hostname + '\n')
        try:
            # Get the IP address for a hostname and connect to the origin server (port 80)
            address = socket.gethostbyname(hostname)
            originServerSocket.connect((address, 80))
            print('Connected to origin Server')

            # Create origin server request line and headers to send
            originServerRequest = f'GET {resource} HTTP/1.1'
            originServerRequestHeader = f'Host: {hostname}\r\nConnection: close'

            # Construct the request to send to the origin server
            request = originServerRequest + '\r\n' + originServerRequestHeader + '\r\n\r\n'
            print('Forwarding request to origin server:')
            for line in request.split('\r\n'):
                print('> ' + line)

            try:
                originServerSocket.sendall(request.encode())
                originServerSocket.shutdown(socket.SHUT_WR)
            except socket.error:
                print('Forward request to origin failed')
                sys.exit()
            print('Request sent to origin server\n')

            # Get the response from the origin server
            origin_response = b""
            while True:
                try:
                    chunk = originServerSocket.recv(BUFFER_SIZE)
                except socket.timeout:
                    print("Socket timeout reached")
                    break
                if not chunk:
                    break
                origin_response += chunk

            # Send the complete response to the client
            clientSocket.sendall(origin_response)

            # Split response into headers and body for caching and debugging
            parts = origin_response.split(b'\r\n\r\n', 1)
            if len(parts) == 2:
                headers, body = parts
            else:
                headers = b""
                body = origin_response

            print("Response Headers (repr):", repr(headers))
            lines = headers.decode('utf-8', errors='ignore').splitlines()
            if len(lines) > 0:
                status_line = lines[0]
                print("Origin server response status:", status_line)
            else:
                print("No headers found!")

            # Save origin server response in the cache files (only cache if status is 200)
            if len(lines) > 0 and "200" in lines[0]:
                cacheDir_hdr, _ = os.path.split(cacheLocation_hdr)
                cacheDir_body, _ = os.path.split(cacheLocation_body)
                if not os.path.exists(cacheDir_hdr):
                    os.makedirs(cacheDir_hdr)
                if not os.path.exists(cacheDir_body):
                    os.makedirs(cacheDir_body)
                with open(cacheLocation_hdr, 'wb') as f_hdr:
                    f_hdr.write(headers)
                with open(cacheLocation_body, 'wb') as f_body:
                    f_body.write(body)
                print("Response cached.")
            else:
                print("Not caching response (status not 200).")
            print('Finished caching origin response.')

            print('Origin response received. Closing sockets.')
            originServerSocket.close()

            clientSocket.shutdown(socket.SHUT_WR)
            print('Client socket shutdown for writing.')
        except OSError as err:
            print('Origin server request failed. ' + err.strerror)

    try:
        clientSocket.close()
    except:
        print('Failed to close client socket')
