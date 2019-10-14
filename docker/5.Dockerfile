FROM golang:1.9-alpine

COPY main.go /go/src/github.com/chrishiestand/docker-go-hello-world/

RUN cd /go/src/github.com/chrishiestand/docker-go-hello-world && \
    go get && \
    CGO_ENABLED=0 GOOS=linux go build -a -o /go/bin/hello main.go

FROM scratch
CMD ["/app"]
COPY --from=0 /go/bin/hello /app
