# Include the libraries for socket and system calls
import socket
import sys
import os
import argparse
import re
import time

# =============================================================================
# PROXY FEATURES IMPLEMENTATION
# =============================================================================
# 1. Cache expiration time processing:
#    - The proxy implements HTTP/1.1 cache freshness validation based on RFC 2616,
#    supporting two mechanisms: Cache-Control max-age and Expires.
#    - For max-age, the proxy stores a cache timestamp, calculates the age of the cached response,
#    and compares it with the max-age value; for Expires, it parses the date and compares it with
#    the current time. When both are present, max-age takes precedence.
#
# =============================================================================

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
            # check cache file by last modified time and max-age in Cache-Control
            cache_mtime = os.path.getmtime(cacheLocation_hdr)
            current_time = time.time()

            # get cache head
            with open(cacheLocation_hdr, "rb") as cacheFile_hdr:
                cached_headers = cacheFile_hdr.read()
            headers_str = cached_headers.decode('utf-8', errors='ignore')
            valid_cache = False

            # check max-age  in Cache-Control
            for line in headers_str.splitlines():
                if line.lower().startswith('cache-control:') and 'max-age=' in line.lower():
                    try:
                        max_age = int(line.lower().split('max-age=')[1].split()[0])
                        if (current_time - cache_mtime) <= max_age:
                            valid_cache = True
                    except:
                        valid_cache = False
                    break

            # if there is no max-age, check Expires
            if not valid_cache:
                for line in headers_str.splitlines():
                    if line.lower().startswith('expires:'):
                        expires_str = line.split(":", 1)[1].strip()
                        try:
                            expires_time_struct = time.strptime(expires_str, "%a, %d %b %Y %H:%M:%S %Z")
                            expires_time = time.mktime(expires_time_struct)
                            if current_time <= expires_time:
                                valid_cache = True
                        except Exception as e:
                            valid_cache = False
                        break

            if valid_cache:
                with open(cacheLocation_body, "rb") as cacheFile_body:
                    cached_body = cacheFile_body.read()
                cached_response = cached_headers + b"\r\n\r\n" + cached_body
                print('Cache hit! Loading from cache files:')
                print('> Headers:', headers_str)
                print('> Body: <binary data, length {}>'.format(len(cached_body)))
                clientSocket.sendall(cached_response)
            else:
                raise FileNotFoundError
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
        originServerSocket.settimeout(10)
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

            # originServerRequest = ''
            # originServerRequestHeader = ''
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
            print("origin_response===",origin_response)
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

            # Parse Cache-Control header and determine caching
            headers_str = headers.decode('latin-1', errors='replace')
            header_lines = headers_str.split('\r\n')
            if len(header_lines) == 0:
                break
            status_line = header_lines[0]
            try:
                status_code = int(status_line.split()[1])
            except Exception as e:
                print("Failed to parse status code:", e)
                break
            # Redirection handling block
            max_redirects = 5
            redirect_count = 0
            # Check if response is a redirect (HTTP 3xx)
            if 300 <= status_code < 400:
                print("Redirect response detected:", status_line)
                location = None
                # Look for the "Location" header
                for line in header_lines:
                    if line.lower().startswith('location:'):
                        location = line.split(":", 1)[1].strip()
                        break
                if location:
                    print("Redirect location:", location)
                    # Assume location is an absolute URL; parse new hostname and resource
                    parsed = re.sub('^http(s?)://', '', location, count=1)
                    resourceParts = parsed.split('/', 1)
                    hostname = resourceParts[0]
                    resource = '/'
                    if len(resourceParts) == 2:
                        resource += resourceParts[1]
                    print("New request - hostname:", hostname, "resource:", resource)

                    # Close the current origin server socket and create a new one
                    try:
                        originServerSocket.close()
                    except:
                        pass
                    try:
                        originServerSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        originServerSocket.settimeout(10)
                        address = socket.gethostbyname(hostname)
                        originServerSocket.connect((address, 80))
                        print("Connected to new origin server:", hostname)
                    except Exception as e:
                        print("Failed to connect to new origin server:", e)
                        break

                    # Reconstruct the request for the new URL
                    originServerRequest = f'GET {resource} HTTP/1.1'
                    originServerRequestHeader = f'Host: {hostname}\r\nConnection: close'
                    request = originServerRequest + '\r\n' + originServerRequestHeader + '\r\n\r\n'
                    print("Forwarding new request:")
                    for line in request.split('\r\n'):
                        if line:
                            print('> ' + line)
                    try:
                        originServerSocket.sendall(request.encode())
                        # originServerSocket.shutdown(socket.SHUT_WR)
                    except socket.error:
                        print("Failed to send new request")
                        break

                    # Receive the new response from the origin server
                    origin_response = b""
                    while True:
                        chunk = originServerSocket.recv(BUFFER_SIZE)
                        if not chunk:
                            break
                        origin_response += chunk

                    redirect_count += 1
                    print(f"Redirect count: {redirect_count}")
                    # Continue loop to check if further redirection is needed
                else:
                    print("Redirect response did not contain a Location header.")
                    break

            cache_control = None
            max_age = None
            should_cache = True
            should_redirect = False
            for line in headers_str.split('\r\n'):
                if line.lower().startswith('cache-control:'):
                    cache_control = line
                    # If Cache-Control contains 'private', do not cache.
                    if 'private' in line.lower():
                        print("Cache-Control is private, not caching the response")
                        should_cache = False
                    if 'max-age=' in line.lower():
                        max_age_part = line.lower().split('max-age=')[1]
                        max_age = int(max_age_part.split(',')[0].strip())
                        print(f"Found max-age directive: {max_age} seconds")
                        # Do not cache responses with max-age=0
                        if max_age == 0:
                            print("Response has max-age=0, not caching")
                            should_cache = False
                    break

            # Save origin server response in the cache files if allowed
            # As long as caching is allowed
            if len(lines) > 0 and should_cache:
                # Ensure that cache directories exist.
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
                print("Not caching response or cache not allowed.")
            # ~~~~ END CODE INSERT ~~~~

            print('cache file closed')

            # finished communicating with origin server - shutdown socket writes

            print('origin response received. Closing sockets')
            originServerSocket.close()
            # Send the response to the client
            clientSocket.sendall(origin_response)
            clientSocket.shutdown(socket.SHUT_WR)
            print('client socket shutdown for writing')
        except OSError as err:
            print('origin server request failed. ' + err.strerror)

    try:
        clientSocket.close()
    except:
        print('Failed to close client socket')
