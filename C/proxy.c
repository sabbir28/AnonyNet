#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <pthread.h>
#include <signal.h>
#include <time.h>
#include <errno.h>
#include <netdb.h>

#define BUFFER_SIZE 8192
#define MAX_CONNECTIONS 100
#define DEFAULT_HOST "0.0.0.0"
#define DEFAULT_PORT 8000

int server_socket = -1;
int shutdown_flag = 0;
pthread_mutex_t connections_mutex = PTHREAD_MUTEX_INITIALIZER;
int *all_connections = NULL;
int connection_count = 0;

// ========== Colored Logging ==========

void get_timestamp(char *buffer, size_t size) {
    time_t now = time(NULL);
    struct tm *tm_info = localtime(&now);
    strftime(buffer, size, "%Y-%m-%d %H:%M:%S", tm_info);
}

void log_info(const char *msg) {
    char timestamp[20];
    get_timestamp(timestamp, sizeof(timestamp));
    printf("\033[92m[%s] [INFO]\033[0m %s\n", timestamp, msg);
}

void log_warn(const char *msg) {
    char timestamp[20];
    get_timestamp(timestamp, sizeof(timestamp));
    printf("\033[93m[%s] [WARN]\033[0m %s\n", timestamp, msg);
}

void log_error(const char *msg) {
    char timestamp[20];
    get_timestamp(timestamp, sizeof(timestamp));
    printf("\033[91m[%s] [ERROR]\033[0m %s\n", timestamp, msg);
}

void log_http(const char *msg) {
    char timestamp[20];
    get_timestamp(timestamp, sizeof(timestamp));
    printf("\033[94m[%s] [HTTP]\033[0m %s\n", timestamp, msg);
}

void log_https(const char *msg) {
    char timestamp[20];
    get_timestamp(timestamp, sizeof(timestamp));
    printf("\033[95m[%s] [HTTPS]\033[0m %s\n", timestamp, msg);
}

// ========== Forwarder ==========

void *forward(void *arg) {
    int *sockets = (int *)arg;
    int src = sockets[0];
    int dst = sockets[1];
    char buffer[BUFFER_SIZE];
    ssize_t bytes;

    while (!shutdown_flag) {
        bytes = recv(src, buffer, BUFFER_SIZE, 0);
        if (bytes <= 0) break;
        if (send(dst, buffer, bytes, 0) <= 0) break;
    }

    close(src);
    close(dst);
    free(sockets);
    return NULL;
}

// ========== Client Handler ==========

void *handle_client(void *arg) {
    int client_socket = *(int *)arg;
    free(arg);
    struct sockaddr_in client_addr;
    socklen_t addr_len = sizeof(client_addr);
    getpeername(client_socket, (struct sockaddr *)&client_addr, &addr_len);
    char client_ip[INET_ADDRSTRLEN];
    inet_ntop(AF_INET, &client_addr.sin_addr, client_ip, INET_ADDRSTRLEN);
    int client_port = ntohs(client_addr.sin_port);

    // Add to connections
    pthread_mutex_lock(&connections_mutex);
    all_connections = realloc(all_connections, (connection_count + 1) * sizeof(int));
    all_connections[connection_count++] = client_socket;
    pthread_mutex_unlock(&connections_mutex);

    char buffer[BUFFER_SIZE];
    ssize_t bytes = recv(client_socket, buffer, BUFFER_SIZE - 1, 0);
    if (bytes <= 0) {
        close(client_socket);
        return NULL;
    }
    buffer[bytes] = '\0';

    // Parse first line
    char *first_line = strtok(buffer, "\n");
    if (!first_line) {
        close(client_socket);
        return NULL;
    }

    char method[16], path[256], protocol[16];
    if (sscanf(first_line, "%15s %255s %15s", method, path, protocol) != 3) {
        close(client_socket);
        return NULL;
    }

    if (strcmp(method, "CONNECT") == 0) {
        char host[256];
        int port;
        if (sscanf(path, "%255[^:]:%d", host, &port) != 2) {
            close(client_socket);
            return NULL;
        }

        char log_msg[512];
        snprintf(log_msg, sizeof(log_msg), "%s:%d -> CONNECT %s:%d", client_ip, client_port, host, port);
        log_https(log_msg);

        struct hostent *he = gethostbyname(host);
        if (!he) {
            log_error("Failed to resolve host");
            close(client_socket);
            return NULL;
        }

        struct sockaddr_in remote_addr = {0};
        remote_addr.sin_family = AF_INET;
        remote_addr.sin_port = htons(port);
        memcpy(&remote_addr.sin_addr, he->h_addr_list[0], he->h_length);

        int remote_socket = socket(AF_INET, SOCK_STREAM, 0);
        if (remote_socket < 0 || connect(remote_socket, (struct sockaddr *)&remote_addr, sizeof(remote_addr)) < 0) {
            log_error("Failed to connect to remote host");
            close(client_socket);
            return NULL;
        }

        const char *response = "HTTP/1.1 200 Connection Established\r\n\r\n";
        send(client_socket, response, strlen(response), 0);

        int *sockets1 = malloc(2 * sizeof(int));
        int *sockets2 = malloc(2 * sizeof(int));
        sockets1[0] = client_socket; sockets1[1] = remote_socket;
        sockets2[0] = remote_socket; sockets2[1] = client_socket;

        pthread_t t1, t2;
        pthread_create(&t1, NULL, forward, sockets1);
        pthread_create(&t2, NULL, forward, sockets2);
        pthread_detach(t1);
        pthread_detach(t2);
    } else {
        // Handle HTTP
        if (strcmp(method, "GET") == 0 && strcmp(path, "/") == 0) {
            char log_msg[512];
            snprintf(log_msg, sizeof(log_msg), "%s:%d -> health check", client_ip, client_port);
            log_info(log_msg);

            const char *response = "HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Length: 2\r\n\r\nOK";
            send(client_socket, response, strlen(response), 0);
            close(client_socket);
            return NULL;
        }

        char *host_line = strstr(buffer, "Host:");
        if (!host_line) {
            char log_msg[512];
            snprintf(log_msg, sizeof(log_msg), "%s:%d -> No Host header", client_ip, client_port);
            log_warn(log_msg);
            close(client_socket);
            return NULL;
        }

        char host[256];
        sscanf(host_line, "Host: %255s", host);
        char log_msg[512];
        snprintf(log_msg, sizeof(log_msg), "%s:%d -> %s http://%s%s", client_ip, client_port, method, host, path);
        log_http(log_msg);

        struct hostent *he = gethostbyname(host);
        if (!he) {
            log_error("Failed to resolve host");
            close(client_socket);
            return NULL;
        }

        struct sockaddr_in remote_addr = {0};
        remote_addr.sin_family = AF_INET;
        remote_addr.sin_port = htons(80);
        memcpy(&remote_addr.sin_addr, he->h_addr_list[0], he->h_length);

        int remote_socket = socket(AF_INET, SOCK_STREAM, 0);
        if (remote_socket < 0 || connect(remote_socket, (struct sockaddr *)&remote_addr, sizeof(remote_addr)) < 0) {
            log_error("Failed to connect to remote host");
            close(client_socket);
            return NULL;
        }

        send(remote_socket, buffer, bytes, 0);

        int *sockets1 = malloc(2 * sizeof(int));
        int *sockets2 = malloc(2 * sizeof(int));
        sockets1[0] = client_socket; sockets1[1] = remote_socket;
        sockets2[0] = remote_socket; sockets2[1] = client_socket;

        pthread_t t1, t2;
        pthread_create(&t1, NULL, forward, sockets1);
        pthread_create(&t2, NULL, forward, sockets2);
        pthread_detach(t1);
        pthread_detach(t2);
    }

    return NULL;
}

// ========== Server ==========

void shutdown_server(int signum) {
    log_warn("Shutting down server...");
    shutdown_flag = 1;

    if (server_socket >= 0) {
        close(server_socket);
    }

    pthread_mutex_lock(&connections_mutex);
    for (int i = 0; i < connection_count; i++) {
        if (all_connections[i] >= 0) {
            shutdown(all_connections[i], SHUT_RDWR);
            close(all_connections[i]);
        }
    }
    free(all_connections);
    connection_count = 0;
    pthread_mutex_unlock(&connections_mutex);

    log_info("Goodbye 👋");
    exit(0);
}

void start_proxy(const char *host, int port) {
    server_socket = socket(AF_INET, SOCK_STREAM, 0);
    if (server_socket < 0) {
        log_error("Failed to create server socket");
        exit(1);
    }

    int opt = 1;
    setsockopt(server_socket, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt));

    struct sockaddr_in server_addr = {0};
    server_addr.sin_family = AF_INET;
    server_addr.sin_port = htons(port);
    inet_pton(AF_INET, host, &server_addr.sin_addr);

    if (bind(server_socket, (struct sockaddr *)&server_addr, sizeof(server_addr)) < 0) {
        log_error("Failed to bind server socket");
        close(server_socket);
        exit(1);
    }

    if (listen(server_socket, MAX_CONNECTIONS) < 0) {
        log_error("Failed to listen on server socket");
        close(server_socket);
        exit(1);
    }

    char log_msg[256];
    snprintf(log_msg, sizeof(log_msg), "Proxy running on %s:%d", host, port);
    log_info(log_msg);

    signal(SIGINT, shutdown_server);
    signal(SIGTERM, shutdown_server);

    while (!shutdown_flag) {
        struct sockaddr_in client_addr;
        socklen_t addr_len = sizeof(client_addr);
        int client_socket = accept(server_socket, (struct sockaddr *)&client_addr, &addr_len);
        if (client_socket < 0) {
            if (shutdown_flag) break;
            log_error("Failed to accept connection");
            continue;
        }

        char client_ip[INET_ADDRSTRLEN];
        inet_ntop(AF_INET, &client_addr.sin_addr, client_ip, INET_ADDRSTRLEN);
        snprintf(log_msg, sizeof(log_msg), "New connection from %s:%d", client_ip, ntohs(client_addr.sin_port));
        log_info(log_msg);

        int *client_sock_ptr = malloc(sizeof(int));
        *client_sock_ptr = client_socket;
        pthread_t thread;
        pthread_create(&thread, NULL, handle_client, client_sock_ptr);
        pthread_detach(thread);
    }

    shutdown_server(0);
}

// ========== CLI ==========

int main(int argc, char *argv[]) {
    const char *host = DEFAULT_HOST;
    int port = DEFAULT_PORT;

    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "-H") == 0 || strcmp(argv[i], "--host") == 0) {
            if (i + 1 < argc) host = argv[++i];
        } else if (strcmp(argv[i], "-p") == 0 || strcmp(argv[i], "--port") == 0) {
            if (i + 1 < argc) port = atoi(argv[++i]);
        }
    }

    start_proxy(host, port);
    return 0;
}
