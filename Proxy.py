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
# print("parser-----", parser)
parser.add_argument('hostname', help='the IP Address Of Proxy Server')
parser.add_argument('port', help='the port number of the proxy server')
args = parser.parse_args()
print("args-----", args)
proxyHost = args.hostname
proxyPort = int(args.port)

# Create a server socket, bind it to a port and start listening
try:
    # Create a server socket
    # ~~~~ INSERT CODE ~~~~
    serverSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    serverSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    # ~~~~ END CODE INSERT ~~~~
    print('Created socket')
except:
    print('Failed to create socket')
    sys.exit()

try:
    # Bind the the server socket to a host and port
    # ~~~~ INSERT CODE ~~~~
    serverSocket.bind((proxyHost, proxyPort))
    # ~~~~ END CODE INSERT ~~~~
    print('Port is bound')
except:
    print('Port is already in use')
    sys.exit()

try:
    # Listen on the server socket
    # ~~~~ INSERT CODE ~~~~
    # Begin listening for incoming connections with a backlog of 10.
    serverSocket.listen(10)
    # ~~~~ END CODE INSERT ~~~~
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
        # ~~~~ INSERT CODE ~~~~
        # Accept a new connection; clientSocket is the new socket object
        # for this connection, and addr is the client address.
        clientSocket, addr = serverSocket.accept()
        # ~~~~ END CODE INSERT ~~~~
        print('Received a connection')
    except:
        print('Failed to accept connection')
        sys.exit()

    # Get HTTP request from client
    # and store it in the variable: message_bytes
    # ~~~~ INSERT CODE ~~~~
    message_bytes = clientSocket.recv(BUFFER_SIZE)
    # ~~~~ END CODE INSERT ~~~~
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
        # Resource is absolute URI with hostname and resource
        resource = resource + resourceParts[1]

    print('Requested Resource:\t' + resource)

    # Define cache file locations: one for header and one for body
    cacheLocation_hdr = './' + hostname + resource + ".hdr"
    cacheLocation_body = './' + hostname + resource + ".body"
    # If path ends with '/' then add default file name for header and body
    if cacheLocation_hdr.endswith('/.hdr'):
        cacheLocation_hdr = cacheLocation_hdr.replace('/.hdr', '/default.hdr')
    if cacheLocation_body.endswith('/.body'):
        cacheLocation_body = cacheLocation_body.replace('/.body', '/default.body')

    print('Cache header location:\t' + cacheLocation_hdr)
    print('Cache body location:\t' + cacheLocation_body)

    # Check if resource is in cache
    try:
        if os.path.isfile(cacheLocation_hdr) and os.path.isfile(cacheLocation_body):
            # Cache hit: read header and body from cache files and combine
            cacheFile_hdr = open(cacheLocation_hdr, "rb")
            cached_headers = cacheFile_hdr.read()
            cacheFile_hdr.close()

            cacheFile_body = open(cacheLocation_body, "rb")
            cached_body = cacheFile_body.read()
            cacheFile_body.close()

            cached_response = cached_headers + b"\r\n\r\n" + cached_body
            print('Cache hit! Loading from cache files:')
            print('> Headers:', cached_headers.decode('utf-8', errors='ignore'))
            print('> Body: <binary data, length {}>'.format(len(cached_body)))
            clientSocket.sendall(cached_response)
        else:
            # cache miss, continue to get resource from origin server
            raise FileNotFoundError
    except:
        # cache miss.  Get resource from origin server
        # originServerSocket = None
        # Create a socket to connect to origin server
        # and store in originServerSocket
        # ~~~~ INSERT CODE ~~~~
        originServerSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        originServerSocket.settimeout(10)  # 可设置超时，避免无限阻塞
        # ~~~~ END CODE INSERT ~~~~

        print('Connecting to:\t\t' + hostname + '\n')
        try:
            # Get the IP address for a hostname
            address = socket.gethostbyname(hostname)
            # Connect to the origin server
            # ~~~~ INSERT CODE ~~~~
            originServerSocket.connect((address, 80))

            # ~~~~ END CODE INSERT ~~~~
            print('Connected to origin Server')

            originServerRequest = ''
            originServerRequestHeader = ''
            # Create origin server request line and headers to send
            # and store in originServerRequestHeader and originServerRequest
            # originServerRequest is the first line in the request and
            # originServerRequestHeader is the second line in the request
            # ~~~~ INSERT CODE ~~~~
            # Create origin server request line and headers to send.
            # originServerRequest is the request line, e.g., "GET /path HTTP/1.1".
            originServerRequest = f'GET {resource} HTTP/1.1'
            # originServerRequestHeader includes necessary headers, e.g., Host and Connection.
            originServerRequestHeader = f'Host: {hostname}\r\nConnection: close'
            # ~~~~ END CODE INSERT ~~~~

            # Construct the request to send to the origin server
            request = originServerRequest + '\r\n' + originServerRequestHeader + '\r\n\r\n'

            # Request the web resource from origin server
            print('Forwarding request to origin server:')
            for line in request.split('\r\n'):
                print('> ' + line)

            try:
                # ~~~~ INSERT CODE ~~~~
                # Send the request to the origin server.
                originServerSocket.sendall(request.encode())
                # Signal that the request has been fully sent.
                originServerSocket.shutdown(socket.SHUT_WR)
                # ~~~~ END CODE INSERT ~~~~
            except socket.error:
                print('Forward request to origin failed')
                sys.exit()
            print('Request sent to origin server\n')

            # ~~~~ INSERT CODE ~~~~
            # Get the response from the origin server.
            origin_response = b""
            while True:
                chunk = originServerSocket.recv(BUFFER_SIZE)
                if not chunk:
                    break
                origin_response += chunk
            # ~~~~ END CODE INSERT ~~~~

            # Send the response to the client
            clientSocket.sendall(origin_response)

            # split body and header to check the image is received correctly
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

            # ~~~~ INSERT CODE ~~~~
            # Only cache the response if the status code is 200.
            if len(lines) > 0 and "200" in lines[0]:
                # Ensure that the cache directories exist.
                cacheDir_hdr, _ = os.path.split(cacheLocation_hdr)
                cacheDir_body, _ = os.path.split(cacheLocation_body)
                if not os.path.exists(cacheDir_hdr):
                    os.makedirs(cacheDir_hdr)
                if not os.path.exists(cacheDir_body):
                    os.makedirs(cacheDir_body)
                # Save the headers and body into separate cache files.
                with open(cacheLocation_hdr, 'wb') as f_hdr:
                    f_hdr.write(headers)
                with open(cacheLocation_body, 'wb') as f_body:
                    f_body.write(body)
                print("Response cached.")
            else:
                print("Not caching response (status not 200).")
            # ~~~~ END CODE INSERT ~~~~

            print('cache file closed')

            # finished communicating with origin server - shutdown socket writes
            print('origin response received. Closing sockets')
            originServerSocket.close()

            clientSocket.shutdown(socket.SHUT_WR)
            print('client socket shutdown for writing')
        except OSError as err:
            print('origin server request failed. ' + err.strerror)

    try:
        clientSocket.close()
    except:
        print('Failed to close client socket')
