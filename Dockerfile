FROM gliderlabs/alpine
COPY ./build/linux/powerstrip /bin/powerstrip
ENV PORT 2375
CMD ["/bin/powerstrip"]
