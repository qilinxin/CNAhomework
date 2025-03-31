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
#      supporting two mechanisms: Cache-Control max-age and Expires.
#    - For max-age, the proxy stores a cache timestamp, calculates the age of the cached response,
#      and compares it with the max-age value; for Expires, it parses the date and compares it with
#      the current time. When both are present, max-age takes precedence.
# 2. Pre-fetch resources
#     - Content-Type Check: It verifies that the response is HTML by checking if the
#       headers contain "Content-Type:" and "text/html".
#     - Extracting Links: The HTML body is decoded and regular expressions extract all
#       links from href and src attributes.
#     - Caching Check: It constructs cache file paths for the resource and skips prefetching if the
#       files already exist.
#     - Fetching and Caching: For uncached resources, a socket connection is opened to the target host,
#       an HTTP GET request is sent, and the response is received and split into headers and body.
#       The response is then saved to cache files in the appropriate directories.
# 3. Handle ports in the url
#     - Port Extraction: Right after splitting the URI, the code checks if hostname contains a colon.
#       If so, it extracts the port number (defaulting to 80 if parsing fails) and assigns it to origin_port.
#     - Cache File Naming: When defining cache file locations, if origin_port is not 80, the port is appended
#       to the hostname (e.g., hostname_8080) to avoid cache collisions.
#     - Using the Extracted Port: When connecting to the origin server (and during redirections),
#       the code uses origin_port instead of hardcoded 80.
# =============================================================================

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

    # --- Modification for Port Handling ---
    # Check if the hostname includes a port number (e.g., hostname:portnumber)
    origin_port = 80  # default port
    if ':' in hostname:
        hostname, port_str = hostname.split(':', 1)
        try:
            origin_port = int(port_str)
        except ValueError:
            origin_port = 80

    print("Requested Resource:\t" + resource)

    # Define cache file locations: one for header and one for body.
    # Include port info in cache file naming if not default.
    cache_host = hostname if origin_port == 80 else f"{hostname}_{origin_port}"
    cacheLocation_hdr = './' + cache_host + resource + ".hdr"
    cacheLocation_body = './' + cache_host + resource + ".body"
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

            # Check max-age in Cache-Control header
            for line in headers_str.splitlines():
                if line.lower().startswith('cache-control:') and 'max-age=' in line.lower():
                    try:
                        max_age = int(line.lower().split('max-age=')[1].split()[0])
                        if (current_time - cache_mtime) <= max_age:
                            valid_cache = True
                    except:
                        valid_cache = False
                    break

            # If no valid max-age, check the Expires header
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

        print('Connecting to:\t\t' + hostname + " on port " + str(origin_port) + '\n')
        try:
            # Get the IP address for a hostname
            address = socket.gethostbyname(hostname)
            # Connect to the origin server
            # ~~~~ INSERT CODE ~~~~
            originServerSocket.connect((address, origin_port))
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
            print("origin_response===", origin_response)
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
            try:
                status_code = int(header_lines[0].split()[1])
            except Exception as e:
                print("Failed to parse status code:", e)
                break

            # Redirection handling block (if HTTP 3xx)
            max_redirects = 5
            redirect_count = 0
            # Check if response is a redirect (HTTP 3xx)
            # if 300 <= status_code < 400:
            #     print("Redirect response detected:", status_line)
            #     location = None
            #     # Look for the "Location" header
            #     for line in header_lines:
            #         if line.lower().startswith('location:'):
            #             location = line.split(":", 1)[1].strip()
            #             break
            #     if location:
            #         print("Redirect location:", location)
            #         # Assume location is an absolute URL; parse new hostname and resource
            #         parsed = re.sub('^http(s?)://', '', location, count=1)
            #         resourceParts = parsed.split('/', 1)
            #         hostname = resourceParts[0]
            #         resource = '/'
            #         if len(resourceParts) == 2:
            #             resource += resourceParts[1]
            #         print("New request - hostname:", hostname, "resource:", resource)
            #
            #         # Parse port from the new hostname, if specified
            #         origin_port = 80
            #         if ':' in hostname:
            #             hostname, port_str = hostname.split(':', 1)
            #             try:
            #                 origin_port = int(port_str)
            #             except ValueError:
            #                 origin_port = 80
            #
            #         try:
            #             originServerSocket.close()
            #         except:
            #             pass
            #         try:
            #             originServerSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            #             originServerSocket.settimeout(10)
            #             address = socket.gethostbyname(hostname)
            #             originServerSocket.connect((address, origin_port))
            #             print("Connected to new origin server:", hostname, "on port", origin_port)
            #         except Exception as e:
            #             print("Failed to connect to new origin server:", e)
            #             break
            #
            #         # Reconstruct the request for the new URL
            #         originServerRequest = f'GET {resource} HTTP/1.1'
            #         originServerRequestHeader = f'Host: {hostname}\r\nConnection: close'
            #         request = originServerRequest + '\r\n' + originServerRequestHeader + '\r\n\r\n'
            #         print("Forwarding new request:")
            #         for line in request.split('\r\n'):
            #             if line:
            #                 print('> ' + line)
            #         try:
            #             originServerSocket.sendall(request.encode())
            #             # originServerSocket.shutdown(socket.SHUT_WR)
            #         except socket.error:
            #             print("Failed to send new request")
            #             break
            #
            #         # Receive the new response from the origin server
            #         origin_response = b""
            #         while True:
            #             chunk = originServerSocket.recv(BUFFER_SIZE)
            #             if not chunk:
            #                 break
            #             origin_response += chunk
            #
            #         redirect_count += 1
            #         print(f"Redirect count: {redirect_count}")
            #         # Continue loop to check if further redirection is needed
            #     else:
            #         print("Redirect response did not contain a Location header.")
            #         break

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

            # Save origin server response in cache if allowed
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

            # --- Added: Prefetch associated files for HTML pages ---
            # only save caches when Content-Type is HTML
            if 'Content-Type:' in headers_str and 'text/html' in headers_str.lower():
                print("start Pre-fetch------- ")
                try:
                    html_text = body.decode('utf-8', errors='ignore')
                    # Find links in the HTML body from href and src attributes
                    links = re.findall(r'href="([^"]+)"', html_text) + re.findall(r'src="([^"]+)"', html_text)
                    for link in links:
                        print("Pre-fetch links-------:", links)

                        # create absolute URL
                        if not link.startswith("http"):
                            if link.startswith('/'):
                                absolute_url = f"http://{hostname}{link}"
                            else:
                                base_dir = os.path.dirname(resource)
                                absolute_url = f"http://{hostname}{base_dir}/{link}"
                        else:
                            absolute_url = link

                        # Parse URL to get host, port and resource path
                        url_without_scheme = re.sub(r'^http(s?)://', '', absolute_url, count=1)
                        if '/' in url_without_scheme:
                            host_and_port, resource_path = url_without_scheme.split('/', 1)
                            resource_path = '/' + resource_path
                        else:
                            host_and_port = url_without_scheme
                            resource_path = '/'
                        prefetch_port = 80
                        if ':' in host_and_port:
                            host_pref, port_pref = host_and_port.split(':', 1)
                            try:
                                prefetch_port = int(port_pref)
                            except:
                                prefetch_port = 80
                        else:
                            host_pref = host_and_port

                        # Create cache file paths for the prefetch resource
                        cache_host_pref = host_pref if prefetch_port == 80 else f"{host_pref}_{prefetch_port}"
                        prefetch_cache_hdr = './' + cache_host_pref + resource_path + ".hdr"
                        prefetch_cache_body = './' + cache_host_pref + resource_path + ".body"

                        # Skip prefetch if cache exists
                        if os.path.isfile(prefetch_cache_hdr) and os.path.isfile(prefetch_cache_body):
                            continue

                        try:
                            prefetch_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                            prefetch_socket.settimeout(10)
                            prefetch_address = socket.gethostbyname(host_pref)
                            prefetch_socket.connect((prefetch_address, prefetch_port))
                            prefetch_request = f"GET {resource_path} HTTP/1.1\r\nHost: {host_pref}\r\nConnection: close\r\n\r\n"
                            prefetch_socket.sendall(prefetch_request.encode())
                            prefetch_response = b""
                            while True:
                                chunk = prefetch_socket.recv(BUFFER_SIZE)
                                if not chunk:
                                    break
                                prefetch_response += chunk
                            prefetch_socket.close()

                            prefetch_parts = prefetch_response.split(b'\r\n\r\n', 1)
                            if len(prefetch_parts) == 2:
                                prefetch_hdr, prefetch_body = prefetch_parts
                            else:
                                prefetch_hdr = prefetch_response
                                prefetch_body = b""

                            # Ensure the cache directories exist
                            prefetch_dir_hdr, _ = os.path.split(prefetch_cache_hdr)
                            prefetch_dir_body, _ = os.path.split(prefetch_cache_body)
                            if not os.path.exists(prefetch_dir_hdr):
                                os.makedirs(prefetch_dir_hdr)
                            if not os.path.exists(prefetch_dir_body):
                                os.makedirs(prefetch_dir_body)
                            with open(prefetch_cache_hdr, 'wb') as f:
                                f.write(prefetch_hdr)
                            with open(prefetch_cache_body, 'wb') as f:
                                f.write(prefetch_body)
                            print("Prefetched and cached:", absolute_url)
                        except Exception as e:
                            print("Prefetch failed for", absolute_url, ":", e)
                except Exception as e:
                    print("Error during prefetching:", e)
        except OSError as err:
            print('origin server request failed. ' + err.strerror)
    try:
        clientSocket.close()
    except:
        print('Failed to close client socket')
