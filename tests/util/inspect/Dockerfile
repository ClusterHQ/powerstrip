FROM gliderlabs/alpine
RUN apk-install go
COPY ./inspect.go /inspect.go
RUN go build -o /bin/inspect
EXPOSE 80
ENV POWERSTRIP_ADAPTER inspect
ENTRYPOINT ["/bin/inspect"]