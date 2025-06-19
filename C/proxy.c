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
#define MAX_CONNECTIONS 1000
#define DEFAULT_HOST "0.0.0.0"
#define DEFAULT_PORT 8000

static int server_socket = -1;
static volatile sig_atomic_t shutdown_flag = 0;
static pthread_mutex_t connections_mutex = PTHREAD_MUTEX_INITIALIZER;
static int *all_connections = NULL;
static int connection_count = 0;

void get_timestamp(char *buffer, size_t size) {
    time_t now = time(NULL);
    struct tm *tm_info = localtime(&now);
    strftime(buffer, size, "%Y-%m-%d %H:%M:%S", tm_info);
}

void log_msg(const char *level_color, const char *level, const char *msg) {
    char timestamp[20];
    get_timestamp(timestamp, sizeof(timestamp));
    printf("%s[%s] [%s]\033[0m %s\n", level_color, timestamp, level, msg);
}

#define LOG_INFO(msg) log_msg("\033[92m", "INFO", msg)
#define LOG_WARN(msg) log_msg("\033[93m", "WARN", msg)
#define LOG_ERROR(msg) log_msg("\033[91m", "ERROR", msg)
#define LOG_HTTP(msg) log_msg("\033[94m", "HTTP", msg)
#define LOG_HTTPS(msg) log_msg("\033[95m", "HTTPS", msg)

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

void cleanup_connection(int client_socket) {
    pthread_mutex_lock(&connections_mutex);
    for (int i = 0; i < connection_count; i++) {
        if (all_connections[i] == client_socket) {
            all_connections[i] = all_connections[--connection_count];
            break;
        }
    }
    pthread_mutex_unlock(&connections_mutex);
    shutdown(client_socket, SHUT_RDWR);
    close(client_socket);
}

void *handle_client(void *arg) {
    int client_socket = *(int *)arg;
    free(arg);

    struct sockaddr_in client_addr;
    socklen_t addr_len = sizeof(client_addr);
    getpeername(client_socket, (struct sockaddr *)&client_addr, &addr_len);
    char client_ip[INET_ADDRSTRLEN];
    inet_ntop(AF_INET, &client_addr.sin_addr, client_ip, INET_ADDRSTRLEN);
    int client_port = ntohs(client_addr.sin_port);

    pthread_mutex_lock(&connections_mutex);
    all_connections = realloc(all_connections, (connection_count + 1) * sizeof(int));
    all_connections[connection_count++] = client_socket;
    pthread_mutex_unlock(&connections_mutex);

    char buffer[BUFFER_SIZE];
    ssize_t bytes = recv(client_socket, buffer, BUFFER_SIZE - 1, 0);
    if (bytes <= 0) {
        cleanup_connection(client_socket);
        return NULL;
    }
    buffer[bytes] = '\0';

    char *first_line = strtok(buffer, "\n");
    if (!first_line) {
        cleanup_connection(client_socket);
        return NULL;
    }

    char method[16], path[256], protocol[16];
    if (sscanf(first_line, "%15s %255s %15s", method, path, protocol) != 3) {
        cleanup_connection(client_socket);
        return NULL;
    }

    if (strcmp(method, "CONNECT") == 0) {
        char host[256];
        int port;
        if (sscanf(path, "%255[^:]:%d", host, &port) != 2) {
            cleanup_connection(client_socket);
            return NULL;
        }

        char log_msg_buf[512];
        snprintf(log_msg_buf, sizeof(log_msg_buf), "%s:%d -> CONNECT %s:%d", client_ip, client_port, host, port);
        LOG_HTTPS(log_msg_buf);

        struct hostent *he = gethostbyname(host);
        if (!he) {
            LOG_ERROR("Failed to resolve host");
            cleanup_connection(client_socket);
            return NULL;
        }

        struct sockaddr_in remote_addr = {0};
        remote_addr.sin_family = AF_INET;
        remote_addr.sin_port = htons(port);
        memcpy(&remote_addr.sin_addr, he->h_addr_list[0], he->h_length);

        int remote_socket = socket(AF_INET, SOCK_STREAM, 0);
        if (remote_socket < 0 || connect(remote_socket, (struct sockaddr *)&remote_addr, sizeof(remote_addr)) < 0) {
            LOG_ERROR("Failed to connect to remote host");
            cleanup_connection(client_socket);
            return NULL;
        }

        const char *response = "HTTP/1.1 200 Connection Established\r\n\r\n";
        send(client_socket, response, strlen(response), 0);

        int *s1 = malloc(2 * sizeof(int));
        int *s2 = malloc(2 * sizeof(int));
        s1[0] = client_socket; s1[1] = remote_socket;
        s2[0] = remote_socket; s2[1] = client_socket;

        pthread_t t1, t2;
        pthread_create(&t1, NULL, forward, s1);
        pthread_create(&t2, NULL, forward, s2);
        pthread_detach(t1);
        pthread_detach(t2);
    } else {
        if (strcmp(method, "GET") == 0 && strcmp(path, "/") == 0) {
            char log_msg_buf[256];
            snprintf(log_msg_buf, sizeof(log_msg_buf), "%s:%d -> health check", client_ip, client_port);
            LOG_INFO(log_msg_buf);

            const char *response = "HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Length: 2\r\n\r\nOK";
            send(client_socket, response, strlen(response), 0);
            cleanup_connection(client_socket);
            return NULL;
        }

        char *host_line = strstr(buffer, "Host:");
        if (!host_line) {
            LOG_WARN("No Host header");
            cleanup_connection(client_socket);
            return NULL;
        }

        char host[256];
        sscanf(host_line, "Host: %255s", host);

        struct hostent *he = gethostbyname(host);
        if (!he) {
            LOG_ERROR("Failed to resolve host");
            cleanup_connection(client_socket);
            return NULL;
        }

        struct sockaddr_in remote_addr = {0};
        remote_addr.sin_family = AF_INET;
        remote_addr.sin_port = htons(80);
        memcpy(&remote_addr.sin_addr, he->h_addr_list[0], he->h_length);

        int remote_socket = socket(AF_INET, SOCK_STREAM, 0);
        if (remote_socket < 0 || connect(remote_socket, (struct sockaddr *)&remote_addr, sizeof(remote_addr)) < 0) {
            LOG_ERROR("Failed to connect to remote host");
            cleanup_connection(client_socket);
            return NULL;
        }

        send(remote_socket, buffer, bytes, 0);

        int *s1 = malloc(2 * sizeof(int));
        int *s2 = malloc(2 * sizeof(int));
        s1[0] = client_socket; s1[1] = remote_socket;
        s2[0] = remote_socket; s2[1] = client_socket;

        pthread_t t1, t2;
        pthread_create(&t1, NULL, forward, s1);
        pthread_create(&t2, NULL, forward, s2);
        pthread_detach(t1);
        pthread_detach(t2);
    }

    return NULL;
}

void shutdown_server(int sig) {
    (void)sig;
    shutdown_flag = 1;
    LOG_WARN("Shutting down server...");

    if (server_socket >= 0) close(server_socket);

    pthread_mutex_lock(&connections_mutex);
    for (int i = 0; i < connection_count; i++) {
        if (all_connections[i] >= 0) {
            shutdown(all_connections[i], SHUT_RDWR);
            close(all_connections[i]);
        }
    }
    free(all_connections);
    all_connections = NULL;
    connection_count = 0;
    pthread_mutex_unlock(&connections_mutex);

    LOG_INFO("Proxy shutdown complete.");
    exit(0);
}

void start_proxy(const char *host, int port) {
    struct sockaddr_in server_addr = {0};

    server_socket = socket(AF_INET, SOCK_STREAM, 0);
    if (server_socket < 0) {
        perror("socket");
        exit(EXIT_FAILURE);
    }

    int opt = 1;
    setsockopt(server_socket, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt));

    server_addr.sin_family = AF_INET;
    server_addr.sin_port = htons(port);
    inet_pton(AF_INET, host, &server_addr.sin_addr);

    if (bind(server_socket, (struct sockaddr *)&server_addr, sizeof(server_addr)) < 0) {
        perror("bind");
        exit(EXIT_FAILURE);
    }

    if (listen(server_socket, MAX_CONNECTIONS) < 0) {
        perror("listen");
        exit(EXIT_FAILURE);
    }

    char msg[128];
    snprintf(msg, sizeof(msg), "Proxy server running on %s:%d", host, port);
    LOG_INFO(msg);

    signal(SIGINT, shutdown_server);
    signal(SIGTERM, shutdown_server);

    while (!shutdown_flag) {
        struct sockaddr_in client_addr;
        socklen_t addr_len = sizeof(client_addr);
        int client_socket = accept(server_socket, (struct sockaddr *)&client_addr, &addr_len);
        if (client_socket < 0) {
            if (shutdown_flag) break;
            perror("accept");
            continue;
        }

        int *client_ptr = malloc(sizeof(int));
        if (!client_ptr) {
            LOG_ERROR("Memory allocation failed");
            close(client_socket);
            continue;
        }

        *client_ptr = client_socket;
        pthread_t tid;
        if (pthread_create(&tid, NULL, handle_client, client_ptr) != 0) {
            LOG_ERROR("Thread creation failed");
            free(client_ptr);
            close(client_socket);
            continue;
        }
        pthread_detach(tid);
    }

    shutdown_server(0);
}

int main(int argc, char *argv[]) {
    const char *host = DEFAULT_HOST;
    int port = DEFAULT_PORT;

    for (int i = 1; i < argc; i++) {
        if ((strcmp(argv[i], "-H") == 0 || strcmp(argv[i], "--host") == 0) && i + 1 < argc) {
            host = argv[++i];
        } else if ((strcmp(argv[i], "-p") == 0 || strcmp(argv[i], "--port") == 0) && i + 1 < argc) {
            port = atoi(argv[++i]);
        }
    }

    start_proxy(host, port);
    return 0;
}
