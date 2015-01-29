FROM gliderlabs/alpine
RUN apk-install bash jq
ADD https://get.docker.io/builds/Linux/x86_64/docker-1.4.1 /bin/docker
RUN chmod +x /bin/docker
CMD ["/bin/bash"]
