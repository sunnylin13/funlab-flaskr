
# waitress.conf.py
# Server Settings
import multiprocessing
# _quiet = False  # for debug information purpose set False
# _profile = True  # for debug profiling purpose set True
# will use FunlabFlase's config.toml setting
# host = '0.0.0.0'
# port = 5000
# url_scheme = 'https'
ident = None  # An optional identifier string that can be used to differentiate between multiple instances of Waitress serving the same application.

# Concurrency Settings
threads = multiprocessing.cpu_count() * 2 + 1  # 4  # The number of threads to use for handling requests.
backlog = 2048  # The maximum number of pending connections in the server's listen queue.

# Connection Settings
channel_timeout = 60  # he maximum time (in seconds) the server waits for a new request before closing the connection.
connection_limit = 1000  # The maximum number of concurrent connections the server will accept.

# URL Prefix
url_prefix = ''  # An optional prefix that is added to every URL path.

# Trusted Proxies
trusted_proxy = []  #  A list of trusted proxy IP addresses.

# Additional Waitress settings can be added here
# For example:
# max_request_header_size = 8192
# max_request_body_size = 1048576
