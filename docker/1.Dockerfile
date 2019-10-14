# Since we're only running a binary, we can probably use scratch
FROM scratch

# This almost never changes so should be moved up
ENTRYPOINT ["mybin"]

# COPY instead of ADD
COPY mybin .
