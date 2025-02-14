FROM golang:alpine AS builder
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 go build -o custom-k8s-scheduler .
FROM alpine:latest
COPY --from=builder /app/custom-k8s-scheduler /usr/local/bin/custom-k8s-scheduler
COPY ./pods_and_nodes_map.csv /usr/local/bin/pod_node_mapping.csv
RUN chmod +x /usr/local/bin/custom-k8s-scheduler
RUN ls -la /usr/local/bin/
ENTRYPOINT ["/usr/local/bin/custom-k8s-scheduler"]
