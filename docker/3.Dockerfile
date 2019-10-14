# We can probably use alpine instead of ubuntu
FROM alpine

# Since the executable is self-contained and doesn't require this CWD, we can remove it from this file, instead we use the absolute dest path in the COPY below
# WORKDIR /app

CMD ["/app/src/bin/run"]

COPY src/ /app/src
